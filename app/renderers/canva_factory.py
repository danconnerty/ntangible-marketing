from app.config import get_settings
from app.renderers.base import BaseCanvaRenderer
from app.renderers.canva_http import HttpCanvaRenderer
from app.renderers.canva_mock import MockCanvaRenderer


def get_image_renderer() -> BaseCanvaRenderer:
    """Return the active image renderer based on ``IMAGE_RENDERER``.

    Supported values:
        ``pillow``      — in-process Pillow templates (default, Phase 1+).
        ``canva_http``  — legacy Canva REST autofill + export.
        ``canva_mock``  — deterministic mock for tests.
    """
    renderer_type = (get_settings().image_renderer or "pillow").lower()
    if renderer_type == "pillow":
        # Imported lazily so environments without Pillow can still load the
        # rest of the renderer package.
        from app.renderers.pillow_renderer import PillowRenderer

        return PillowRenderer()
    if renderer_type == "canva_http":
        return HttpCanvaRenderer()
    if renderer_type == "canva_mock":
        return MockCanvaRenderer()
    raise ValueError(
        f"Unknown image renderer: {renderer_type}. "
        "Use pillow, canva_http, or canva_mock."
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
        return MockCanvaRenderer()
    if renderer_type == "http":
        return HttpCanvaRenderer()
    raise ValueError(f"Unknown Canva renderer: {renderer_type}. Use mock or http.")
