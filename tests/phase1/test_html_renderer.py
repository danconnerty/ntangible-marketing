"""Phase 1 tests for the HTML-template renderer path.

Covers the parts that don't require a real Chromium install:
* Registry lookup + fixture loading.
* :func:`render_template_html` injects data, palette, width, and height.
* HtmlRenderer's graceful fallback for unknown families.
* HtmlRenderer surfaces a helpful error if Playwright fails to launch
  (first-run, missing chromium) instead of raising.

A separate test attempts a real Chromium render and is skipped cleanly
when the browser isn't installed, so CI doesn't require Playwright
browsers to be provisioned.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("jinja2")

from app.renderers.html_renderer import (  # noqa: E402
    HtmlRenderer,
    render_template_html,
)
from app.renderers.html_templates import (  # noqa: E402
    FAMILIES,
    TEMPLATE_DIR,
    list_families,
    load_fixture,
)


PALETTE = {
    "background": "#0B1220",
    "surface": "#111A2E",
    "primary_text": "#F5F7FA",
    "secondary_text": "#9AA3B2",
    "accent": "#F4B72E",
    "rule": "#1E2A44",
    "wordmark": "#F5F7FA",
}


def test_registry_lists_event_leaderboard() -> None:
    assert "event_leaderboard" in list_families()
    cfg = FAMILIES["event_leaderboard"]
    assert cfg["default_size"] == (1080, 1080)
    assert (TEMPLATE_DIR / cfg["template_file"]).exists()
    assert (TEMPLATE_DIR / cfg["fixture_file"]).exists()


def test_fixture_loads_with_expected_shape() -> None:
    fixture = load_fixture("event_leaderboard")
    assert fixture["event_name"]
    assert fixture["date"]
    assert len(fixture["top_athletes"]) == 5
    for entry in fixture["top_athletes"]:
        assert {"rank", "name", "cf_score"} <= entry.keys()


def test_render_template_html_injects_data_and_palette() -> None:
    fixture = load_fixture("event_leaderboard")
    html = render_template_html(
        "event_leaderboard",
        data=fixture,
        palette=PALETTE,
    )
    # Data injected.
    assert fixture["event_name"] in html
    assert fixture["date"] in html
    for athlete in fixture["top_athletes"]:
        assert athlete["name"] in html
    # Palette injected as CSS custom properties.
    assert PALETTE["background"] in html
    assert PALETTE["accent"] in html
    # Size from default registered for the family.
    assert "1080px" in html


def test_render_template_html_unknown_family_raises() -> None:
    with pytest.raises(ValueError, match="Unknown HTML template family"):
        render_template_html("does_not_exist", data={})


def test_html_renderer_unknown_family_falls_back_to_canva(monkeypatch) -> None:
    """Unknown families should not explode — they delegate to legacy."""
    from app.renderers.base import CanvaRenderRequest, CanvaRenderResult
    from app.renderers import canva_factory

    class _StubCanva:
        called = False

        def render(self, request):  # noqa: ARG002
            _StubCanva.called = True
            return CanvaRenderResult(success=True)

    stub = _StubCanva()
    monkeypatch.setattr(canva_factory, "get_canva_renderer", lambda: stub)

    request = CanvaRenderRequest(
        template_family="bogus_family_xyz",
        brand_mode="owned",
        canva_template_id="unused",
        text_fields={},
        numeric_fields={},
        image_references=[],
    )
    result = HtmlRenderer().render(request)
    assert result.success is True
    assert _StubCanva.called


def test_html_renderer_returns_error_when_chromium_missing(monkeypatch, tmp_path) -> None:
    """If Playwright can't launch (first-run, no chromium), surface a helpful error."""
    from app.renderers import html_renderer as html_renderer_module
    from app.renderers.base import CanvaRenderRequest

    # Redirect asset storage so any disk writes land in tmp_path.
    monkeypatch.setattr(
        "app.services.asset_storage._asset_root",
        lambda: tmp_path,
    )
    # Force the PNG step to raise as if chromium is missing.
    monkeypatch.setattr(
        HtmlRenderer,
        "_html_to_png",
        staticmethod(
            lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("Executable doesn't exist at /chromium")
            )
        ),
    )
    # Avoid hitting the real brand palette yaml.
    monkeypatch.setattr(html_renderer_module, "get_brand_palette", lambda: PALETTE)

    request = CanvaRenderRequest(
        template_family="event_leaderboard",
        brand_mode="owned",
        canva_template_id="unused",
        text_fields={},
        numeric_fields={},
        image_references=[],
        structured_data=load_fixture("event_leaderboard"),
    )
    result = HtmlRenderer().render(request)
    assert result.success is False
    assert "playwright install chromium" in (result.error or "")


def test_html_renderer_real_chromium_screenshot(monkeypatch, tmp_path) -> None:
    """End-to-end render — skipped when the chromium browser is not installed."""
    from app.renderers import html_renderer as html_renderer_module
    from app.renderers.base import CanvaRenderRequest

    playwright = pytest.importorskip("playwright.sync_api")

    # Probe for a usable browser without failing the whole test.
    try:
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
    except Exception as exc:
        pytest.skip(f"Chromium not installed for Playwright: {exc}")

    monkeypatch.setattr(
        "app.services.asset_storage._asset_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(html_renderer_module, "get_brand_palette", lambda: PALETTE)

    request = CanvaRenderRequest(
        template_family="event_leaderboard",
        brand_mode="owned",
        canva_template_id="unused",
        text_fields={},
        numeric_fields={},
        image_references=[],
        structured_data=load_fixture("event_leaderboard"),
    )
    result = HtmlRenderer().render(request)
    assert result.success, result.error
    assert len(result.assets) == 1
    saved = Path(result.assets[0].storage_path)
    assert saved.exists()
    assert saved.suffix == ".png"
    assert saved.stat().st_size > 1000
