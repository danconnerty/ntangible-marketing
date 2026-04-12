from app.config import get_settings
from app.renderers.base import BaseCanvaRenderer
from app.renderers.canva_http import HttpCanvaRenderer
from app.renderers.canva_mock import MockCanvaRenderer


def get_canva_renderer() -> BaseCanvaRenderer:
    renderer_type = get_settings().canva_renderer.lower()
    if renderer_type == "mock":
        return MockCanvaRenderer()
    if renderer_type == "http":
        return HttpCanvaRenderer()
    raise ValueError(f"Unknown Canva renderer: {renderer_type}. Use mock or http.")
