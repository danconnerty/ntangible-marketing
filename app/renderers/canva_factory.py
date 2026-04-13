from app.config import get_settings
from app.renderers.base import BaseCanvaRenderer


def get_image_renderer() -> BaseCanvaRenderer:
    """Return the active image renderer based on ``IMAGE_RENDERER``.

    Supported values:
        ``pillow``      — in-process Pillow templates (Phase 1 default).
        ``html``        — Jinja2 HTML templates rasterised via headless
                          Chromium (Playwright). Requires a one-time
                          ``python3 -m playwright install chromium``.
        ``canva_http``  — legacy Canva REST autofill + export.
        ``canva_mock``  — deterministic mock for tests.

    Renderer modules are imported lazily so selecting Pillow doesn't
    require httpx (for Canva HTTP), and selecting HTML doesn't require
    Pillow, etc.
    """
    renderer_type = (get_settings().image_renderer or "pillow").lower()
    if renderer_type == "pillow":
        from app.renderers.pillow_renderer import PillowRenderer

        return PillowRenderer()
    if renderer_type == "html":
        from app.renderers.html_renderer import HtmlRenderer

        return HtmlRenderer()
    if renderer_type == "canva_http":
        from app.renderers.canva_http import HttpCanvaRenderer

        return HttpCanvaRenderer()
    if renderer_type == "canva_mock":
        from app.renderers.canva_mock import MockCanvaRenderer

        return MockCanvaRenderer()
    raise ValueError(
        f"Unknown image renderer: {renderer_type}. "
        "Use pillow, html, canva_http, or canva_mock."
    )


def get_canva_renderer() -> BaseCanvaRenderer:
    """Legacy Canva selector kept for callers that explicitly want Canva.

    Phase 1 introduced :func:`get_image_renderer` as the new entry point.
    Existing call sites that still ask for a Canva renderer (e.g. the
    Instagram carousel pipeline) keep the original ``CANVA_RENDERER`` flag
    semantics so their tests and behavior are unchanged until they migrate.
    """
    renderer_type = get_settings().canva_renderer.lower()
    if renderer_type == "mock":
        from app.renderers.canva_mock import MockCanvaRenderer

        return MockCanvaRenderer()
    if renderer_type == "http":
        from app.renderers.canva_http import HttpCanvaRenderer

        return HttpCanvaRenderer()
    raise ValueError(f"Unknown Canva renderer: {renderer_type}. Use mock or http.")
