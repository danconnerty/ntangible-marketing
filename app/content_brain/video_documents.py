from __future__ import annotations

from app.content_brain.types import ParsedAsset, ParsedContentItem


def build_youtube_oembed_item(
    *,
    video_id: str,
    watch_url: str,
    title: str,
    author_name: str,
    thumbnail_url: str,
    source_slug: str,
) -> ParsedContentItem:
    return ParsedContentItem(
        canonical_key=f"youtube:video:{video_id}",
        platform="youtube",
        item_type="video",
        url=watch_url,
        title=title,
        author=author_name,
        external_id=video_id,
        metadata={"source_slug": source_slug, "document_type": "youtube_oembed"},
        assets=[ParsedAsset(asset_type="thumbnail", url=thumbnail_url)],
    )
