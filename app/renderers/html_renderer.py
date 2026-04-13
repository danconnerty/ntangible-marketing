"""HTML-template image renderer.

Implements :class:`BaseCanvaRenderer` by rendering a Jinja2 HTML template
with the request's data, then rasterising it to PNG via headless Chromium
(Playwright).

Design notes
------------
* Pure-HTML templates live in :mod:`app.renderers.html_templates`. Each
  family has a ``<family>.html`` file plus a ``<family>.fixture.json``.
* :func:`render_template_html` is intentionally separate from the PNG
  conversion: the Studio tab calls it directly so design iteration works
  with zero Playwright dependency (the browser already renders HTML).
* :class:`HtmlRenderer` is opt-in — set ``IMAGE_RENDERER=html`` once you
  have run ``python3 -m playwright install chromium``. Until then Pillow
  stays the default.
* Unknown template families gracefully fall back to the legacy Canva
  renderer so existing X / LinkedIn pipelines keep working unchanged.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_brand_palette
from app.renderers.base import (
    BaseCanvaRenderer,
    CanvaRenderRequest,
    CanvaRenderResult,
    RenderedAsset,
)
from app.renderers.html_templates import FAMILIES, TEMPLATE_DIR
from app.services.asset_storage import _asset_root


logger = logging.getLogger(__name__)

DEFAULT_SIZE = (1080, 1080)


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_template_html(
    family: str,
    *,
    data: dict[str, Any] | None = None,
    palette: dict[str, str] | None = None,
    width: int | None = None,
    height: int | None = None,
) -> str:
    """Render a template family to an HTML string with data injected.

    Kept as a top-level function so the Studio tab can serve templates
    without instantiating the full renderer or touching Playwright.
    """
    cfg = FAMILIES.get(family)
    if cfg is None:
        raise ValueError(f"Unknown HTML template family: {family}")

    template = _jinja_env().get_template(cfg["template_file"])
    default_w, default_h = cfg.get("default_size", DEFAULT_SIZE)
    context: dict[str, Any] = {
        "palette": palette or get_brand_palette(),
        "width": width or default_w,
        "height": height or default_h,
    }
    if data:
        context.update(data)
    return template.render(**context)


class HtmlRenderer(BaseCanvaRenderer):
    """Renders HTML templates to PNG via headless Chromium (Playwright)."""

    def render(self, request: CanvaRenderRequest) -> CanvaRenderResult:
        family = request.template_family
        if family not in FAMILIES:
            logger.info(
                "No HTML template for family %s; delegating to legacy renderer",
                family,
            )
            from app.renderers.canva_factory import get_canva_renderer

            return get_canva_renderer().render(request)

        try:
            width, height = self._resolve_size(request, family)
            data = self._combine_data(request)
            html = render_template_html(
                family,
                data=data,
                width=width,
                height=height,
            )
        except Exception as exc:
            logger.exception("HTML template render failed for family %s", family)
            return CanvaRenderResult(
                success=False, error=f"{type(exc).__name__}: {exc}"
            )

        try:
            png_bytes = self._html_to_png(html, width, height)
        except Exception as exc:
            logger.exception("Playwright render failed for family %s", family)
            return CanvaRenderResult(
                success=False,
                error=(
                    f"{type(exc).__name__}: {exc}. "
                    "First-run setup: `python3 -m playwright install chromium`."
                ),
            )

        storage_path, url = self._save_png_bytes(png_bytes, family)
        return CanvaRenderResult(
            success=True,
            assets=[
                RenderedAsset(
                    asset_role=(request.output_asset_roles or ["primary"])[0],
                    storage_path=storage_path,
                    url=url,
                )
            ],
        )

    @staticmethod
    def _resolve_size(request: CanvaRenderRequest, family: str) -> tuple[int, int]:
        dims = request.output_dimensions or {}
        default = FAMILIES[family].get("default_size", DEFAULT_SIZE)
        width = int(dims.get("width", default[0]))
        height = int(dims.get("height", default[1]))
        return (width, height)

    @staticmethod
    def _combine_data(request: CanvaRenderRequest) -> dict[str, Any]:
        """Merge text/numeric/structured fields into a single Jinja context.

        Structured data keys win on collision — they're the richer shape.
        """
        data: dict[str, Any] = {}
        if request.text_fields:
            data.update(request.text_fields)
        if request.numeric_fields:
            data.update(request.numeric_fields)
        if request.structured_data:
            data.update(request.structured_data)
        return data

    @staticmethod
    def _html_to_png(html: str, width: int, height: int) -> bytes:
        # Lazy import so the module loads fine in environments without
        # Playwright installed (e.g., the Pillow-only default path).
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    device_scale_factor=2,  # retina-quality output
                )
                page = context.new_page()
                page.set_content(html, wait_until="networkidle")
                return page.screenshot(
                    type="png",
                    clip={"x": 0, "y": 0, "width": width, "height": height},
                )
            finally:
                browser.close()

    @staticmethod
    def _save_png_bytes(png_bytes: bytes, family: str) -> tuple[str, str]:
        root = Path(_asset_root())
        root.mkdir(parents=True, exist_ok=True)
        filename = f"{family}_{uuid.uuid4().hex}.png"
        path = root / filename
        path.write_bytes(png_bytes)
        absolute = str(path.resolve())
        return absolute, f"file://{absolute}"
