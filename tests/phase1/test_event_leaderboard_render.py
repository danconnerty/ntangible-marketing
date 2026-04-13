"""Phase 1 smoke test for the Pillow event_leaderboard template.

These tests run the template function directly so they do not require the
full app Settings stack (database URLs, API keys, etc.). A second test
exercises the ``PillowRenderer`` dispatcher, stubbing the brand palette so
it does not depend on environment.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")

from PIL import Image  # noqa: E402  (after importorskip)

from app.renderers.pillow_templates.event_leaderboard import (  # noqa: E402
    render_event_leaderboard,
)


FIXTURE = Path(__file__).parent / "fixtures" / "top5_leaderboard.json"

_PALETTE = {
    "background": "#0B1220",
    "surface": "#111A2E",
    "primary_text": "#F5F7FA",
    "secondary_text": "#9AA3B2",
    "accent": "#F4B72E",
    "rule": "#1E2A44",
    "wordmark": "#F5F7FA",
}


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def test_event_leaderboard_renders_1080_square() -> None:
    data = _load_fixture()
    image = render_event_leaderboard(
        text_fields={"event_name": data["event_name"], "date": data["date"]},
        structured_data={"top_athletes": data["top_athletes"]},
        size=(1080, 1080),
        palette=_PALETTE,
    )
    assert isinstance(image, Image.Image)
    assert image.size == (1080, 1080)
    assert image.mode == "RGB"


def test_event_leaderboard_has_meaningful_content() -> None:
    """Proxy for 'something was actually drawn' — background + accent pixels."""
    data = _load_fixture()
    image = render_event_leaderboard(
        text_fields={"event_name": data["event_name"], "date": data["date"]},
        structured_data={"top_athletes": data["top_athletes"]},
        size=(1080, 1080),
        palette=_PALETTE,
    )
    colors = image.getcolors(maxcolors=1_000_000) or []
    # Background + surface + text + accent should yield at least a few dozen
    # distinct colors once antialiasing is accounted for.
    assert len(colors) > 50, f"Only {len(colors)} colors rendered — probably blank"

    # Accent gold should appear somewhere (ranks + scores).
    accent_rgb = (0xF4, 0xB7, 0x2E)
    has_accent = any(
        abs(r - accent_rgb[0]) < 10
        and abs(g - accent_rgb[1]) < 10
        and abs(b - accent_rgb[2]) < 10
        for _count, (r, g, b) in colors
    )
    assert has_accent, "Accent color missing — rank/score drawing likely failed"


def test_event_leaderboard_rejects_wrong_entry_count() -> None:
    with pytest.raises(ValueError, match="expects exactly 5 entries"):
        render_event_leaderboard(
            text_fields={"event_name": "Test", "date": "2026"},
            structured_data={"top_athletes": [{"rank": 1, "name": "A", "cf_score": 90}]},
            size=(1080, 1080),
            palette=_PALETTE,
        )


def test_pillow_renderer_dispatch(monkeypatch, tmp_path) -> None:
    """PillowRenderer should dispatch event_leaderboard and save a PNG."""
    from app.renderers import pillow_renderer as pillow_module
    from app.renderers.base import CanvaRenderRequest

    # Redirect storage so the test doesn't pollute the repo.
    monkeypatch.setattr(
        "app.services.asset_storage._asset_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        pillow_module, "get_brand_palette", lambda: _PALETTE
    )

    data = _load_fixture()
    request = CanvaRenderRequest(
        template_family="event_leaderboard",
        brand_mode="owned",
        canva_template_id="unused_by_pillow",
        text_fields={"event_name": data["event_name"], "date": data["date"]},
        numeric_fields={},
        image_references=[],
        structured_data={"top_athletes": data["top_athletes"]},
    )
    result = pillow_module.PillowRenderer().render(request)
    assert result.success, result.error
    assert len(result.assets) == 1

    asset = result.assets[0]
    saved = Path(asset.storage_path)
    assert saved.exists()
    assert saved.suffix == ".png"
    with Image.open(saved) as img:
        assert img.size == (1080, 1080)
