#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.content_brain.bootstrap import DEFAULT_STORAGE_ROOT, _sanitize_slug, _serialize_item
from app.content_brain.parsers import parse_instagram_post_document


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich stored public social items with post-level metadata.")
    parser.add_argument(
        "--slug",
        action="append",
        help="Only enrich the provided target slug. Repeat for multiple slugs.",
    )
    parser.add_argument(
        "--storage-root",
        default=str(DEFAULT_STORAGE_ROOT),
        help="Directory where raw, normalized, and run summary files are stored.",
    )
    return parser.parse_args()


def latest_normalized_paths(storage_root: Path) -> dict[str, Path]:
    latest: dict[str, Path] = {}
    normalized_root = storage_root / "normalized"
    for path in sorted(normalized_root.rglob("*.json")) if normalized_root.exists() else []:
        latest[path.stem] = path
    return latest


def _write_raw_enrichment(
    *,
    storage_root: Path,
    target_slug: str,
    external_id: str,
    html: str,
) -> str:
    day_bucket = datetime.now(UTC).strftime("%Y-%m-%d")
    safe_name = _sanitize_slug(f"{target_slug}__{external_id}")
    raw_rel = Path("raw") / day_bucket / f"{safe_name}.html"
    raw_path = storage_root / raw_rel
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(html, encoding="utf-8")
    return raw_rel.as_posix()


def _merge_item(existing_item: dict, enriched_item: dict, *, raw_path: str) -> dict:
    merged = dict(existing_item)
    for field in ("title", "author", "published_at", "body_text", "summary", "external_id"):
        value = enriched_item.get(field)
        if value:
            merged[field] = value

    if enriched_item.get("assets"):
        merged["assets"] = enriched_item["assets"]
    if enriched_item.get("metrics"):
        merged["metrics"] = enriched_item["metrics"]

    metadata = dict(existing_item.get("metadata") or {})
    metadata.update(enriched_item.get("metadata") or {})
    metadata["enrichment_raw_path"] = raw_path
    merged["metadata"] = metadata
    return merged


def enrich_instagram_source(path: Path, *, storage_root: Path, client: httpx.Client) -> dict[str, int | str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    target_slug = payload["target_slug"]
    updated_items = 0
    items: list[dict] = []

    for item in payload.get("items", []):
        if item.get("item_type") not in {"post", "reel"}:
            items.append(item)
            continue

        response = client.get(item["url"])
        response.raise_for_status()

        external_id = item.get("external_id") or item["canonical_key"].split(":")[-1]
        raw_path = _write_raw_enrichment(
            storage_root=storage_root,
            target_slug=target_slug,
            external_id=external_id,
            html=response.text,
        )

        parsed_item = parse_instagram_post_document(
            response.text,
            source_url=str(response.url),
            source_slug=target_slug,
        )[0]
        items.append(
            _merge_item(
                item,
                _serialize_item(parsed_item),
                raw_path=raw_path,
            )
        )
        updated_items += 1

    payload["fetched_at"] = datetime.now(UTC).isoformat()
    payload["items"] = items
    payload["item_count"] = len(items)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return {"target_slug": target_slug, "updated_items": updated_items, "normalized_path": path.as_posix()}


def main() -> None:
    args = parse_args()
    storage_root = Path(args.storage_root)
    normalized_paths = latest_normalized_paths(storage_root)
    requested = set(args.slug or [])

    targets = [
        path
        for slug, path in sorted(normalized_paths.items())
        if (not requested or slug in requested) and slug.endswith("instagram_profile")
    ]

    results: list[dict[str, int | str]] = []
    with httpx.Client(follow_redirects=True, timeout=20.0, headers=DEFAULT_HEADERS) as client:
        for path in targets:
            results.append(enrich_instagram_source(path, storage_root=storage_root, client=client))

    print(json.dumps({"storage_root": storage_root.as_posix(), "results": results}, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
