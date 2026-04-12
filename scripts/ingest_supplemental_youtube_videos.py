#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.content_brain.bootstrap import DEFAULT_STORAGE_ROOT, persist_fetch_result
from app.content_brain.video_documents import build_youtube_oembed_item


EMBED_PATTERN = re.compile(r"youtube\.com/embed/([A-Za-z0-9_-]{11})")


def collect_embedded_video_ids(base: Path) -> set[str]:
    text = ""
    for path in sorted((base / "normalized").rglob("*.json")):
        text += path.read_text(encoding="utf-8")
    return set(EMBED_PATTERN.findall(text))


def collect_feed_video_ids(feed_path: Path) -> set[str]:
    if not feed_path.exists():
        return set()
    payload = json.loads(feed_path.read_text(encoding="utf-8"))
    return {item.get("external_id") for item in payload.get("items", []) if item.get("external_id")}


def ingest_video(video_id: str, *, storage_root: Path, client: httpx.Client) -> dict[str, object]:
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    response = client.get(
        "https://www.youtube.com/oembed",
        params={"url": watch_url, "format": "json"},
    )
    response.raise_for_status()
    payload = response.json()

    item = build_youtube_oembed_item(
        video_id=video_id,
        watch_url=watch_url,
        title=payload["title"],
        author_name=payload["author_name"],
        thumbnail_url=payload["thumbnail_url"],
        source_slug=f"supplemental_youtube_video_{video_id}",
    )

    result = persist_fetch_result(
        storage_root=storage_root,
        target_slug=f"supplemental_youtube_video_{video_id}",
        source_url=watch_url,
        content_type="application/json",
        raw_body=json.dumps(payload, ensure_ascii=True),
        items=[item],
        fetched_at=datetime.now(UTC),
    )
    result["display_name"] = payload["title"]
    return result


def main() -> None:
    storage_root = DEFAULT_STORAGE_ROOT
    embedded_ids = collect_embedded_video_ids(storage_root)
    feed_ids = collect_feed_video_ids(storage_root / "normalized" / "2026-04-07" / "ntangible_youtube_feed.json")
    missing_ids = sorted(embedded_ids - feed_ids)

    results: list[dict[str, object]] = []
    with httpx.Client(follow_redirects=True, timeout=20.0) as client:
        for video_id in missing_ids:
            results.append(ingest_video(video_id, storage_root=storage_root, client=client))

    print(
        json.dumps(
            {
                "storage_root": storage_root.as_posix(),
                "video_count": len(results),
                "missing_ids": missing_ids,
                "results": results,
            },
            indent=2,
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
