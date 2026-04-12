from datetime import UTC, datetime
from pathlib import Path

from app.content_brain.browser_capture import build_playwright_command, ingest_rendered_targets
from app.content_brain.types import SourceTarget


def _target(slug: str, url: str) -> SourceTarget:
    return SourceTarget(
        slug=slug,
        display_name=slug,
        url=url,
        parser="generic_document",
        platform="web",
        source_kind="website",
    )


def test_build_playwright_command_uses_ephemeral_playwright_package():
    command = build_playwright_command(
        renderer_script=Path("scripts/render_page_with_playwright.mjs"),
        url="https://ntangible.co/team",
        playwright_module=Path("/tmp/ntangible-playwright-runner/node_modules/playwright/index.mjs"),
    )

    assert command[:2] == ["node", "scripts/render_page_with_playwright.mjs"]
    assert command[-2:] == [
        "https://ntangible.co/team",
        "/tmp/ntangible-playwright-runner/node_modules/playwright/index.mjs",
    ]


def test_build_playwright_command_serializes_render_options():
    command = build_playwright_command(
        renderer_script=Path("scripts/render_page_with_playwright.mjs"),
        url="https://www.instagram.com/ntangiblesports",
        playwright_module=Path("/tmp/ntangible-playwright-runner/node_modules/playwright/index.mjs"),
        render_options={"scroll_profile": True, "max_scrolls": 8},
    )

    assert command[-1] == '{"max_scrolls":8,"scroll_profile":true}'


def test_ingest_rendered_targets_persists_rendered_html(tmp_path, monkeypatch):
    target = _target("ntangible_team", "https://ntangible.co/team")

    def fake_render(url: str) -> dict:
        assert url == "https://ntangible.co/team"
        return {
            "final_url": url,
            "title": "NTangible Team",
            "content_type": "text/html; charset=utf-8",
            "html": "<html><head><title>NTangible Team</title></head><body><main>Dan Connerty</main></body></html>",
        }

    monkeypatch.setattr(
        "app.content_brain.browser_capture.render_html_via_playwright",
        fake_render,
    )

    summary = ingest_rendered_targets(
        [target],
        storage_root=tmp_path,
        fetched_at=datetime(2026, 4, 7, 3, 0, tzinfo=UTC),
    )

    assert summary["results"][0]["target_slug"] == "ntangible_team"
    assert summary["results"][0]["item_count"] == 1
    normalized_path = tmp_path / summary["results"][0]["normalized_path"]
    assert normalized_path.exists()
    assert "ntangible_team" in normalized_path.read_text(encoding="utf-8")
