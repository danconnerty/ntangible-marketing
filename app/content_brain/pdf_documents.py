from __future__ import annotations

from datetime import datetime

from app.content_brain.types import ParsedContentItem


def build_research_pdf_item(
    *,
    pdf_text: str,
    source_url: str,
    source_slug: str,
    title: str,
    published_at: datetime | None,
    file_id: str,
) -> ParsedContentItem:
    summary = " ".join(pdf_text.split())
    return ParsedContentItem(
        canonical_key=f"research_pdf:{file_id}",
        platform="web",
        item_type="research_pdf",
        url=source_url,
        title=title,
        author="NTangible",
        published_at=published_at,
        body_text=pdf_text,
        summary=summary[:280] if summary else None,
        external_id=file_id,
        metadata={
            "source_slug": source_slug,
            "file_id": file_id,
            "document_type": "research_pdf",
        },
    )
