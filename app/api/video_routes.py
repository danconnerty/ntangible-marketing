from __future__ import annotations

from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.database import get_db
from app.services.video_content_service import VideoContentService


try:  # pragma: no cover - fallback only matters when jinja2 is missing
    from fastapi.templating import Jinja2Templates
except ImportError:  # pragma: no cover
    Jinja2Templates = None


router = APIRouter(
    prefix="/api/control-room/video",
    tags=["video"],
    dependencies=[Depends(verify_api_key)],
)
web_router = APIRouter(prefix="/control-room", tags=["video-web"])


class VideoBriefRequest(BaseModel):
    kind: str = "founder_raw"
    target_platform: str = "linkedin"
    context: str | None = None
    source_material: str | None = None
    source_mode: str = "manual"
    title: str | None = None
    audience: str | None = None
    cta: str | None = None


def _serialize_dashboard(db: Session) -> dict:
    return VideoContentService(db).list_dashboard()


def _render_fallback(template_name: str, context: dict) -> str:
    if template_name == "video.html":
        briefs = "".join(
            f"<article><h3>{brief['title']}</h3><p>{brief['kind']}</p><p>{brief['platform']}</p><p>{brief['hook']}</p></article>"
            for brief in context.get("briefs", [])
        )
        return f"<h1>Video</h1>{briefs}"
    if template_name == "partials/video_brief_result.html":
        brief = context["result"]
        return (
            f"<section><h2>{brief['title']}</h2><p>{brief['kind']}</p>"
            f"<p>{brief['platform']}</p><p>{brief['hook']}</p><p>{brief['script']}</p></section>"
        )
    return "<h1>Video</h1>"


class _FallbackTemplates:
    def TemplateResponse(self, request: Request, template_name: str, context: dict):
        return HTMLResponse(_render_fallback(template_name, context))


templates = Jinja2Templates(directory="app/web/templates") if Jinja2Templates is not None else _FallbackTemplates()


@router.get("")
def list_video_dashboard(db: Session = Depends(get_db)):
    dashboard = _serialize_dashboard(db)
    return dashboard


@router.get("/briefs")
def list_video_briefs(db: Session = Depends(get_db)):
    dashboard = _serialize_dashboard(db)
    return {"briefs": dashboard["briefs"], "count": dashboard["count"]}


@router.post("/briefs")
def create_video_brief(req: VideoBriefRequest, db: Session = Depends(get_db)):
    try:
        result = VideoContentService(db).create_brief(
            kind=req.kind,
            target_platform=req.target_platform,
            context=req.context,
            source_material=req.source_material,
            source_mode=req.source_mode,
            title=req.title,
            audience=req.audience,
            cta=req.cta,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return result


@web_router.get("/video")
def video_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "video.html",
        {
            "page": "video",
            **_serialize_dashboard(db),
        },
    )


@web_router.post("/video/briefs", response_class=HTMLResponse)
async def video_brief_fragment(request: Request, db: Session = Depends(get_db)):
    form = parse_qs((await request.body()).decode("utf-8"))
    payload = VideoBriefRequest(
        kind=form.get("kind", ["founder_raw"])[0],
        target_platform=form.get("target_platform", ["linkedin"])[0],
        context=form.get("context", [None])[0],
        source_material=form.get("source_material", [None])[0],
        source_mode=form.get("source_mode", ["manual"])[0],
        title=form.get("title", [None])[0],
        audience=form.get("audience", [None])[0],
        cta=form.get("cta", [None])[0],
    )
    try:
        result = VideoContentService(db).create_brief(
            kind=payload.kind,
            target_platform=payload.target_platform,
            context=payload.context,
            source_material=payload.source_material,
            source_mode=payload.source_mode,
            title=payload.title,
            audience=payload.audience,
            cta=payload.cta,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return templates.TemplateResponse(request, "partials/video_brief_result.html", {"result": result})
