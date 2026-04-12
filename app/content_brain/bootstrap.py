from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import httpx

from app.content_brain.parsers import parse_payload
from app.content_brain.types import ParsedContentItem, SourceTarget


DEFAULT_STORAGE_ROOT = Path("data/content_brain")
DEFAULT_HEADERS = {}


def _sanitize_slug(value: str) -> str:
    normalized = []
    for char in value:
        normalized.append(char if char.isalnum() or char in {"-", "_"} else "_")
    return "".join(normalized).strip("_") or "snapshot"


def _guess_extension(content_type: str, source_url: str) -> str:
    lowered_type = (content_type or "").lower()
    lowered_url = source_url.lower()
    if "xml" in lowered_type or lowered_url.endswith(".xml"):
        return "xml"
    if "json" in lowered_type or lowered_url.endswith(".json"):
        return "json"
    if "html" in lowered_type or lowered_url.endswith((".html", ".htm")):
        return "html"
    return "txt"


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if is_dataclass(value):
        return {
            field.name: _serialize_value(getattr(value, field.name))
            for field in fields(value)
        }
    if hasattr(value, "__dict__"):
        return {key: _serialize_value(item) for key, item in value.__dict__.items()}
    return value


def _serialize_item(item: ParsedContentItem) -> dict[str, Any]:
    return {
        "canonical_key": item.canonical_key,
        "platform": item.platform,
        "item_type": item.item_type,
        "url": item.url,
        "title": item.title,
        "author": item.author,
        "published_at": _serialize_value(item.published_at),
        "body_text": item.body_text,
        "summary": item.summary,
        "external_id": item.external_id,
        "metadata": _serialize_value(item.metadata),
        "assets": _serialize_value(item.assets),
        "metrics": _serialize_value(item.metrics),
    }


def persist_fetch_result(
    *,
    storage_root: Path,
    target_slug: str,
    source_url: str,
    content_type: str,
    raw_body: str,
    items: list[ParsedContentItem],
    fetched_at: datetime,
) -> dict[str, Any]:
    day_bucket = fetched_at.astimezone(UTC).strftime("%Y-%m-%d")
    safe_slug = _sanitize_slug(target_slug)
    extension = _guess_extension(content_type, source_url)
    digest = sha256(raw_body.encode("utf-8")).hexdigest()

    raw_rel = Path("raw") / day_bucket / f"{safe_slug}.{extension}"
    normalized_rel = Path("normalized") / day_bucket / f"{safe_slug}.json"

    raw_path = storage_root / raw_rel
    normalized_path = storage_root / normalized_rel
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_path.parent.mkdir(parents=True, exist_ok=True)

    raw_path.write_text(raw_body, encoding="utf-8")
    normalized_payload = {
        "target_slug": target_slug,
        "source_url": source_url,
        "fetched_at": fetched_at.astimezone(UTC).isoformat(),
        "content_type": content_type,
        "body_sha256": digest,
        "item_count": len(items),
        "items": [_serialize_item(item) for item in items],
    }
    normalized_path.write_text(
        json.dumps(normalized_payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    return {
        "target_slug": target_slug,
        "source_url": source_url,
        "content_type": content_type,
        "item_count": len(items),
        "body_sha256": digest,
        "raw_path": raw_rel.as_posix(),
        "normalized_path": normalized_rel.as_posix(),
    }


def _persist_run_summary(
    storage_root: Path,
    *,
    started_at: datetime,
    finished_at: datetime,
    results: list[dict[str, Any]],
) -> str:
    timestamp = finished_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_rel = Path("runs") / f"{timestamp}.json"
    run_path = storage_root / run_rel
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_payload = {
        "started_at": started_at.astimezone(UTC).isoformat(),
        "finished_at": finished_at.astimezone(UTC).isoformat(),
        "target_count": len(results),
        "success_count": sum(1 for result in results if not result.get("error")),
        "failure_count": sum(1 for result in results if result.get("error")),
        "results": results,
    }
    run_path.write_text(json.dumps(run_payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return run_rel.as_posix()


def ingest_targets(
    targets: list[SourceTarget],
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    own_client = client is None
    http_client = client or httpx.Client(
        follow_redirects=True,
        timeout=20.0,
        headers=DEFAULT_HEADERS,
    )

    results: list[dict[str, Any]] = []
    try:
        for target in targets:
            fetched_at = datetime.now(UTC)
            try:
                fetch_mode = target.metadata.get("fetch_mode", "http")
                rendered = False
                if fetch_mode == "rendered":
                    from app.content_brain.browser_capture import render_html_via_playwright

                    render_options = target.metadata.get("render_options")
                    if render_options:
                        rendered_payload = render_html_via_playwright(
                            target.url,
                            render_options=render_options,
                        )
                    else:
                        rendered_payload = render_html_via_playwright(target.url)
                    source_url = rendered_payload.get("final_url") or target.url
                    content_type = rendered_payload.get("content_type", "text/html; charset=utf-8")
                    raw_body = rendered_payload["html"]
                    status_code = 200
                    rendered = True
                else:
                    response_headers = {
                        **DEFAULT_HEADERS,
                        **{
                            str(key): str(value)
                            for key, value in target.metadata.get("headers", {}).items()
                        },
                    }
                    response = http_client.get(
                        target.url,
                        headers=response_headers or None,
                    )
                    response.raise_for_status()
                    source_url = str(response.url)
                    content_type = response.headers.get("content-type", "")
                    raw_body = response.text
                    status_code = response.status_code
                items = parse_payload(
                    target.parser,
                    raw_body,
                    source_url=source_url,
                    source_slug=target.slug,
                )
                result = persist_fetch_result(
                    storage_root=storage_root,
                    target_slug=target.slug,
                    source_url=source_url,
                    content_type=content_type,
                    raw_body=raw_body,
                    items=items,
                    fetched_at=fetched_at,
                )
                result["status_code"] = status_code
                result["display_name"] = target.display_name
                if rendered:
                    result["rendered"] = True
                results.append(result)
            except Exception as exc:  # pragma: no cover - exercised by live runs
                results.append(
                    {
                        "target_slug": target.slug,
                        "source_url": target.url,
                        "display_name": target.display_name,
                        "error": str(exc),
                    }
                )
    finally:
        if own_client:
            http_client.close()

    finished_at = datetime.now(UTC)
    run_summary_path = _persist_run_summary(
        storage_root,
        started_at=started_at,
        finished_at=finished_at,
        results=results,
    )
    return {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "storage_root": storage_root.as_posix(),
        "run_summary_path": run_summary_path,
        "results": results,
    }
