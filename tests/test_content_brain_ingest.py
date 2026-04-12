from datetime import UTC, datetime

import httpx

from app.content_brain.bootstrap import ingest_targets
from app.content_brain.types import SourceTarget


def test_ingest_targets_respects_per_source_headers(tmp_path):
    target = SourceTarget(
        slug="future_stars_ntangible_article",
        display_name="Future Stars Series NTangible Article",
        url="https://futurestarsseries.com/ntangible-adds-unique-clutch-performance-angle-to-player-evaluation-development-for-future-stars-series-events/",
        parser="generic_document",
        platform="web",
        source_kind="partner_page",
        metadata={"headers": {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}},
    )

    class StubClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, str] | None]] = []

        def get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
            self.calls.append((url, headers))
            return httpx.Response(
                200,
                request=httpx.Request("GET", url),
                headers={"content-type": "text/html; charset=utf-8"},
                text="<html><head><title>Future Stars</title></head><body>NTangible partnership.</body></html>",
            )

    client = StubClient()
    summary = ingest_targets([target], storage_root=tmp_path, client=client)

    assert client.calls[0][1] == {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
    }
    assert summary["results"][0]["status_code"] == 200
    assert summary["results"][0]["item_count"] == 1


def test_ingest_targets_uses_rendered_fetch_mode(tmp_path, monkeypatch):
    target = SourceTarget(
        slug="ntangible_instagram_profile",
        display_name="NTangible Instagram",
        url="https://www.instagram.com/ntangiblesports",
        parser="instagram_profile_rendered",
        platform="instagram",
        source_kind="social",
        metadata={"fetch_mode": "rendered"},
    )

    def fake_render(url: str) -> dict[str, str]:
        assert url == "https://www.instagram.com/ntangiblesports"
        return {
            "final_url": url,
            "title": "(@ntangiblesports) • Instagram photos and videos",
            "content_type": "text/html; charset=utf-8",
            "html": """\
<!doctype html>
<html>
  <head>
    <title>(@ntangiblesports) • Instagram photos and videos</title>
    <meta name="description" content='908 Followers, 241 Following, 140 Posts - @ntangiblesports on Instagram: "NTangible™ - The Pressure Test"' />
  </head>
  <body>
    <span><span>140</span></span> posts
    <span><span>909</span></span> followers
    <span><span>239</span></span> following
    <a href="/ntangiblesports/p/DOJIVUqEXmr/" role="link"><img alt="Photo by @ntangiblesports on September 03, 2025." src="https://instagram.example.com/photo.jpg" /></a>
  </body>
</html>
""",
        }

    monkeypatch.setattr("app.content_brain.browser_capture.render_html_via_playwright", fake_render)

    summary = ingest_targets(
        [target],
        storage_root=tmp_path,
    )

    assert summary["results"][0]["target_slug"] == "ntangible_instagram_profile"
    assert summary["results"][0]["rendered"] is True
    assert summary["results"][0]["item_count"] == 2
    normalized_path = tmp_path / summary["results"][0]["normalized_path"]
    assert normalized_path.exists()
    assert "instagram:profile:ntangiblesports" in normalized_path.read_text(encoding="utf-8")


def test_ingest_targets_passes_render_options_to_rendered_fetch(tmp_path, monkeypatch):
    target = SourceTarget(
        slug="ntangible_instagram_profile",
        display_name="NTangible Instagram",
        url="https://www.instagram.com/ntangiblesports",
        parser="instagram_profile_rendered",
        platform="instagram",
        source_kind="social",
        metadata={
            "fetch_mode": "rendered",
            "render_options": {"scroll_profile": True, "max_scrolls": 8},
        },
    )

    def fake_render(url: str, *, render_options: dict | None = None) -> dict[str, str]:
        assert url == "https://www.instagram.com/ntangiblesports"
        assert render_options == {"scroll_profile": True, "max_scrolls": 8}
        return {
            "final_url": url,
            "title": "(@ntangiblesports) • Instagram photos and videos",
            "content_type": "text/html; charset=utf-8",
            "html": """\
<!doctype html>
<html>
  <head>
    <title>(@ntangiblesports) • Instagram photos and videos</title>
    <meta name="description" content='908 Followers, 241 Following, 140 Posts - @ntangiblesports on Instagram: "NTangible™ - The Pressure Test"' />
  </head>
  <body>
    <span><span>140</span></span> posts
    <span><span>909</span></span> followers
    <span><span>239</span></span> following
    <a href="/ntangiblesports/p/DOJIVUqEXmr/" role="link"><img alt="Photo by @ntangiblesports on September 03, 2025." src="https://instagram.example.com/photo.jpg" /></a>
  </body>
</html>
""",
        }

    monkeypatch.setattr("app.content_brain.browser_capture.render_html_via_playwright", fake_render)

    summary = ingest_targets([target], storage_root=tmp_path)

    assert summary["results"][0]["target_slug"] == "ntangible_instagram_profile"
    assert summary["results"][0]["item_count"] == 2
