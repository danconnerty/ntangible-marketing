"""Studio: in-browser preview of HTML templates for design iteration.

Renders every registered HTML template family against its fixture data so
you can design in Chrome DevTools and see the result live. Files on disk
remain the source of truth — no write-back endpoints.

Routes
------
* ``GET /control-room/studio`` — grid of thumbnails, one per family
* ``GET /control-room/studio/{family}`` — detail view with full-size
  preview, data contract, and fixture JSON
* ``GET /control-room/studio/{family}/preview`` — raw rendered HTML,
  served as the iframe ``src`` on the pages above
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.renderers.html_renderer import render_template_html
from app.renderers.html_templates import FAMILIES, load_fixture


logger = logging.getLogger(__name__)

studio_router = APIRouter(prefix="/control-room/studio", tags=["studio"])


try:  # pragma: no cover - optional dependency in API-only environments
    from fastapi.templating import Jinja2Templates

    _templates: Jinja2Templates | None = Jinja2Templates(directory="app/web/templates")
except ImportError:  # pragma: no cover
    _templates = None


@studio_router.get("", response_class=HTMLResponse)
@studio_router.get("/", response_class=HTMLResponse)
def studio_index(request: Request) -> HTMLResponse:
    if _templates is None:
        return HTMLResponse("Studio requires Jinja2", status_code=503)

    cards = []
    for family, cfg in FAMILIES.items():
        width, height = cfg.get("default_size", (1080, 1080))
        cards.append(
            {
                "family": family,
                "description": cfg.get("description", ""),
                "width": width,
                "height": height,
                "preview_url": f"/control-room/studio/{family}/preview",
                "detail_url": f"/control-room/studio/{family}",
            }
        )

    return _templates.TemplateResponse(
        request,
        "studio.html",
        {"page": "studio", "cards": cards},
    )


@studio_router.get("/{family}", response_class=HTMLResponse)
def studio_detail(request: Request, family: str) -> HTMLResponse:
    if _templates is None:
        return HTMLResponse("Studio requires Jinja2", status_code=503)
    cfg = FAMILIES.get(family)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"Unknown family: {family}")

    width, height = cfg.get("default_size", (1080, 1080))
    fixture = load_fixture(family)

    return _templates.TemplateResponse(
        request,
        "studio_detail.html",
        {
            "page": "studio",
            "family": family,
            "description": cfg.get("description", ""),
            "width": width,
            "height": height,
            "preview_url": f"/control-room/studio/{family}/preview",
            "template_file": cfg["template_file"],
            "fixture_file": cfg["fixture_file"],
            "fixture_json": json.dumps(fixture, indent=2),
        },
    )


@studio_router.get("/{family}/preview", response_class=HTMLResponse)
def studio_preview(family: str) -> HTMLResponse:
    if family not in FAMILIES:
        raise HTTPException(status_code=404, detail=f"Unknown family: {family}")

    try:
        fixture = load_fixture(family)
        html = render_template_html(family, data=fixture)
    except Exception as exc:  # pragma: no cover - surfaced in the iframe
        logger.exception("Studio preview render failed for %s", family)
        return HTMLResponse(
            f"<pre style='padding:24px;font-family:monospace;color:#f55;'>"
            f"Render error: {type(exc).__name__}: {exc}</pre>",
            status_code=500,
        )

    # Cache-busting so iframe reloads pick up file edits immediately.
    return HTMLResponse(
        html,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )
