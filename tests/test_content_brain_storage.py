import json
from datetime import UTC, datetime

from app.content_brain.bootstrap import persist_fetch_result
from app.content_brain.types import ParsedAsset, ParsedContentItem


def test_persist_fetch_result_writes_raw_and_normalized_files(tmp_path):
    item = ParsedContentItem(
        canonical_key="web:page:https://ntangible.co/",
        platform="web",
        item_type="page",
        url="https://ntangible.co/",
        title="NTangible",
        body_text="Mental performance platform",
        metadata={"source_slug": "ntangible_home"},
    )

    result = persist_fetch_result(
        storage_root=tmp_path,
        target_slug="ntangible_home",
        source_url="https://ntangible.co/",
        content_type="text/html",
        raw_body="<html><title>NTangible</title></html>",
        items=[item],
        fetched_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
    )

    raw_path = tmp_path / result["raw_path"]
    normalized_path = tmp_path / result["normalized_path"]

    assert raw_path.exists()
    assert normalized_path.exists()

    normalized_payload = json.loads(normalized_path.read_text(encoding="utf-8"))
    assert normalized_payload["target_slug"] == "ntangible_home"
    assert normalized_payload["item_count"] == 1
    assert normalized_payload["items"][0]["canonical_key"] == "web:page:https://ntangible.co/"


def test_persist_fetch_result_normalizes_source_slug_paths(tmp_path):
    result = persist_fetch_result(
        storage_root=tmp_path,
        target_slug="wayback:hlt/article",
        source_url="https://web.archive.org/web/20240915171830/https://www.ntangible.co/ntangibleannouncements/hlt",
        content_type="text/html",
        raw_body="<html></html>",
        items=[],
        fetched_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
    )

    assert "wayback_hlt_article" in result["raw_path"]
    assert "wayback_hlt_article" in result["normalized_path"]


def test_persist_fetch_result_serializes_nested_assets(tmp_path):
    item = ParsedContentItem(
        canonical_key="web:page:https://example.com/article",
        platform="web",
        item_type="page",
        url="https://example.com/article",
        assets=[ParsedAsset(asset_type="image", url="https://example.com/cover.jpg")],
    )

    result = persist_fetch_result(
        storage_root=tmp_path,
        target_slug="example_article",
        source_url="https://example.com/article",
        content_type="text/html",
        raw_body="<html></html>",
        items=[item],
        fetched_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
    )

    normalized_path = tmp_path / result["normalized_path"]
    normalized_payload = json.loads(normalized_path.read_text(encoding="utf-8"))

    assert normalized_payload["items"][0]["assets"][0]["url"] == "https://example.com/cover.jpg"
