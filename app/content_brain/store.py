from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import get_settings


def get_storage_root() -> Path:
    return Path(get_settings().content_brain_storage_root)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sorted_json_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(path.rglob("*.json"))


def list_normalized_files() -> list[Path]:
    return _sorted_json_files(get_storage_root() / "normalized")


def list_raw_files() -> list[Path]:
    raw_root = get_storage_root() / "raw"
    if not raw_root.exists():
        return []
    return sorted(path for path in raw_root.rglob("*") if path.is_file())


def latest_run_payload() -> dict[str, Any] | None:
    run_files = _sorted_json_files(get_storage_root() / "runs")
    if not run_files:
        return None
    return _load_json(run_files[-1])


def latest_source_payload(target_slug: str) -> dict[str, Any] | None:
    candidates: list[Path] = []
    for file_path in list_normalized_files():
        if file_path.stem == target_slug:
            candidates.append(file_path)
    if not candidates:
        return None
    return _load_json(candidates[-1])


def latest_source_payloads() -> list[dict[str, Any]]:
    by_slug: dict[str, Path] = {}
    for file_path in list_normalized_files():
        by_slug[file_path.stem] = file_path
    return [_load_json(path) for _, path in sorted(by_slug.items())]


def list_items(*, query: str | None = None, platform: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    lowered_query = query.lower().strip() if query else None
    items: list[dict[str, Any]] = []

    for source_payload in latest_source_payloads():
        target_slug = source_payload.get("target_slug")
        source_url = source_payload.get("source_url")
        for item in source_payload.get("items", []):
            if platform and item.get("platform") != platform:
                continue

            haystack = " ".join(
                str(value)
                for value in [
                    item.get("title"),
                    item.get("summary"),
                    item.get("body_text"),
                    item.get("url"),
                    target_slug,
                ]
                if value
            ).lower()
            if lowered_query and lowered_query not in haystack:
                continue

            enriched = dict(item)
            enriched["target_slug"] = target_slug
            enriched["source_url"] = source_url
            items.append(enriched)

    items.sort(
        key=lambda item: (
            item.get("published_at") or "",
            item.get("title") or "",
            item.get("canonical_key") or "",
        ),
        reverse=True,
    )
    return items[:limit]


def build_overview(*, item_limit: int = 50) -> dict[str, Any]:
    normalized_payloads = latest_source_payloads()
    items = list_items(limit=item_limit)
    latest_run = latest_run_payload()

    sources: list[dict[str, Any]] = []
    for payload in normalized_payloads:
        source_items = payload.get("items", [])
        first_item = source_items[0] if source_items else {}
        normalized_path = None
        fetched_at = payload.get("fetched_at")
        if fetched_at:
            normalized_path = f"normalized/{fetched_at[:10]}/{payload.get('target_slug')}.json"
        sources.append(
            {
                "target_slug": payload.get("target_slug"),
                "source_url": payload.get("source_url"),
                "item_count": payload.get("item_count", len(source_items)),
                "title": first_item.get("title"),
                "platform": first_item.get("platform"),
                "normalized_path": normalized_path,
            }
        )

    return {
        "storage_root": get_storage_root().as_posix(),
        "counts": {
            "raw_files": len(list_raw_files()),
            "normalized_files": len(list_normalized_files()),
            "sources": len(normalized_payloads),
            "items": sum(payload.get("item_count", 0) for payload in normalized_payloads),
        },
        "latest_run": latest_run,
        "sources": sources,
        "items": items,
    }
