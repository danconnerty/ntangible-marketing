from datetime import UTC, datetime

from app.content_brain.pdf_documents import build_research_pdf_item


def test_build_research_pdf_item_sets_full_text_metadata():
    text = "WHITEPAPER\nThe Science of Dyadic Congruence\nAbstract\nThis paper introduces the NTangible Coach/Player Alignment Index."

    item = build_research_pdf_item(
        pdf_text=text,
        source_url="https://drive.google.com/file/d/abc123/view?usp=sharing",
        source_slug="research_alignment_index_pdf",
        title="The Science of Dyadic Congruence: Quantifying Coach-Player Alignment as a Determinant of Elite Performance",
        published_at=datetime(2026, 2, 4, tzinfo=UTC),
        file_id="abc123",
    )

    assert item.canonical_key == "research_pdf:abc123"
    assert item.platform == "web"
    assert item.item_type == "research_pdf"
    assert item.title.startswith("The Science of Dyadic Congruence")
    assert item.author == "NTangible"
    assert item.published_at == datetime(2026, 2, 4, tzinfo=UTC)
    assert item.body_text == text
    assert "Coach/Player Alignment Index" in (item.summary or "")
    assert item.metadata["file_id"] == "abc123"
    assert item.metadata["source_slug"] == "research_alignment_index_pdf"
