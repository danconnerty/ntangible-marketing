"""Pillow-based in-process image renderer.

Implements :class:`BaseCanvaRenderer` so it is a drop-in replacement for the
Canva HTTP / mock renderers. A dispatch table maps ``template_family`` names
to pure layout functions in :mod:`app.renderers.pillow_templates`.

Design notes
------------
* No network calls. Rendering is deterministic and fast (<100 ms for Phase 1
  templates).
* Output is written via :func:`app.services.asset_storage.save_png`, which
  currently returns a local ``file://`` URL. Phase 4 swaps the body of that
  helper for an S3 upload without touching this file.
* The renderer is tolerant of missing Canva-specific fields
  (``canva_template_id``, ``image_references``) since it ignores them.
"""

from __future__ import annotations

import logging

from app.config import get_brand_palette
from app.renderers.base import (
    BaseCanvaRenderer,
    CanvaRenderRequest,
    CanvaRenderResult,
    RenderedAsset,
)
from app.renderers.pillow_templates import FAMILY_RENDERERS
from app.services.asset_storage import save_png


logger = logging.getLogger(__name__)

DEFAULT_SIZE = (1080, 1080)


class PillowRenderer(BaseCanvaRenderer):
    """Pure-Python image renderer."""

    def render(self, request: CanvaRenderRequest) -> CanvaRenderResult:
        family = request.template_family
        renderer_fn = FAMILY_RENDERERS.get(family)
        if renderer_fn is None:
            # Graceful fallback: families that don't have a Pillow template yet
            # delegate to the legacy Canva renderer so existing X / LinkedIn
            # pipelines keep working while Phase 1 focuses on leaderboards.
            logger.info(
                "No Pillow template for family %s; delegating to Canva renderer",
                family,
            )
            from app.renderers.canva_factory import get_canva_renderer

            return get_canva_renderer().render(request)

        size = self._resolve_size(request)
        palette = get_brand_palette()

        try:
            image = renderer_fn(
                text_fields=request.text_fields,
                structured_data=request.structured_data,
                size=size,
                palette=palette,
            )
        except Exception as exc:  # defensive: templates raise on bad input
            logger.exception("Pillow render failed for family %s", family)
            return CanvaRenderResult(success=False, error=f"{type(exc).__name__}: {exc}")

        storage_path, url = save_png(image, prefix=family)
        asset = RenderedAsset(
            asset_role=(request.output_asset_roles or ["primary"])[0],
            storage_path=storage_path,
            url=url,
        )
        return CanvaRenderResult(success=True, assets=[asset])

    @staticmethod
    def _resolve_size(request: CanvaRenderRequest) -> tuple[int, int]:
        dims = request.output_dimensions or {}
        width = int(dims.get("width", DEFAULT_SIZE[0]))
        height = int(dims.get("height", DEFAULT_SIZE[1]))
        return (width, height)
