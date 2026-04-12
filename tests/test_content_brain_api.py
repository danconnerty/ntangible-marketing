import json

from fastapi.testclient import TestClient

from app.main import app


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_content_brain_overview_reads_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTENT_BRAIN_STORAGE_ROOT", str(tmp_path))

    _write_json(
        tmp_path / "runs/20260407T021121Z.json",
        {
            "started_at": "2026-04-07T02:11:18+00:00",
            "finished_at": "2026-04-07T02:11:21+00:00",
            "target_count": 2,
            "success_count": 1,
            "failure_count": 1,
            "results": [
                {"target_slug": "ntangible_youtube_feed", "item_count": 15},
                {"target_slug": "ntangible_team", "error": "404"},
            ],
        },
    )
    _write_json(
        tmp_path / "normalized/2026-04-07/ntangible_youtube_feed.json",
        {
            "target_slug": "ntangible_youtube_feed",
            "source_url": "https://www.youtube.com/feeds/videos.xml?channel_id=123",
            "item_count": 1,
            "items": [
                {
                    "canonical_key": "youtube:video:abc123",
                    "platform": "youtube",
                    "item_type": "video",
                    "url": "https://www.youtube.com/watch?v=abc123",
                    "title": "What is NTelligence?",
                    "published_at": "2026-02-01T03:13:26+00:00",
                    "summary": None,
                    "assets": [{"asset_type": "thumbnail", "url": "https://img.youtube.com/vi/abc123/hqdefault.jpg"}],
                    "metrics": [{"payload": {"views": 4}}],
                    "metadata": {"source_slug": "ntangible_youtube_feed"},
                }
            ],
        },
    )

    with _client() as client:
        response = client.get("/content-brain/api/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["latest_run"]["target_count"] == 2
    assert payload["counts"]["normalized_files"] == 1
    assert payload["counts"]["items"] == 1
    assert payload["sources"][0]["target_slug"] == "ntangible_youtube_feed"
    assert payload["items"][0]["canonical_key"] == "youtube:video:abc123"


def test_content_brain_source_detail_returns_latest_payload(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTENT_BRAIN_STORAGE_ROOT", str(tmp_path))

    _write_json(
        tmp_path / "normalized/2026-04-07/ntangible_youtube_feed.json",
        {
            "target_slug": "ntangible_youtube_feed",
            "source_url": "https://www.youtube.com/feeds/videos.xml?channel_id=123",
            "item_count": 1,
            "items": [{"canonical_key": "youtube:video:abc123", "title": "What is NTelligence?"}],
        },
    )

    with _client() as client:
        response = client.get("/content-brain/api/source/ntangible_youtube_feed")

    assert response.status_code == 200
    payload = response.json()
    assert payload["target_slug"] == "ntangible_youtube_feed"
    assert payload["items"][0]["title"] == "What is NTelligence?"


def test_content_brain_dashboard_page_renders(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTENT_BRAIN_STORAGE_ROOT", str(tmp_path))
    _write_json(
        tmp_path / "runs/20260407T021121Z.json",
        {"target_count": 0, "success_count": 0, "failure_count": 0, "results": []},
    )

    with _client() as client:
        response = client.get("/content-brain")

    assert response.status_code == 200
    assert "NTangible Content Brain" in response.text
    assert "/content-brain/api/overview" in response.text
