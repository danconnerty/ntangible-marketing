from __future__ import annotations

from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.database import get_db
from app.services.ugc_service import UGCService


try:  # pragma: no cover - fallback only matters when jinja2 is missing
    from fastapi.templating import Jinja2Templates
except ImportError:  # pragma: no cover
    Jinja2Templates = None


router = APIRouter(
    prefix="/api/control-room/ugc",
    tags=["ugc"],
    dependencies=[Depends(verify_api_key)],
)
web_router = APIRouter(prefix="/control-room", tags=["ugc-web"])


class TestimonialRequestPayload(BaseModel):
    athlete_name: str
    score: int
    athlete_email: str | None = None
    parent_name: str | None = None
    parent_email: str | None = None
    score_tier: str | None = None
    athlete_age: int | None = None
    sport: str | None = None
    context: str | None = None
    source_partner: str | None = None


class TestimonialSubmissionPayload(BaseModel):
    athlete_name: str
    score: int
    video_url: str
    testimonial_text: str | None = None
    athlete_email: str | None = None
    parent_name: str | None = None
    parent_email: str | None = None
    athlete_age: int | None = None
    consent_athlete: bool = True
    consent_parent: bool = False
    consent_share: bool = True
    score_tier: str | None = None
    request_id: str | None = None
    source_partner: str | None = None
    context: str | None = None


def _serialize_dashboard(db: Session) -> dict:
    return UGCService(db).list_dashboard()


def _render_fallback(template_name: str, context: dict) -> str:
    if template_name == "ugc.html":
        requests = "".join(
            f"<article><h3>{item['athlete_name']}</h3><p>{item['score_tier']}</p><p>{item['subject']}</p></article>"
            for item in context.get("requests", [])
        )
        submissions = "".join(
            f"<article><h3>{item['athlete_name']}</h3><p>{item['score_tier']}</p><p>{item['status']}</p></article>"
            for item in context.get("submissions", [])
        )
        return f"<h1>UGC</h1>{requests}{submissions}"
    if template_name == "partials/ugc_request_result.html":
        result = context["result"]
        return (
            f"<section><h2>{result['athlete_name']}</h2><p>{result['score_tier']}</p>"
            f"<p>{result['subject']}</p><p>{result['request_copy']}</p></section>"
        )
    if template_name == "partials/ugc_submission_result.html":
        result = context["result"]
        return (
            f"<section><h2>{result['athlete_name']}</h2><p>{result['score_tier']}</p>"
            f"<p>{result['video_url']}</p><p>{result['status']}</p></section>"
        )
    return "<h1>UGC</h1>"


class _FallbackTemplates:
    def TemplateResponse(self, request: Request, template_name: str, context: dict):
        return HTMLResponse(_render_fallback(template_name, context))


templates = Jinja2Templates(directory="app/web/templates") if Jinja2Templates is not None else _FallbackTemplates()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "on", "yes"}


@router.get("")
def list_ugc_dashboard(db: Session = Depends(get_db)):
    dashboard = _serialize_dashboard(db)
    return dashboard


@router.post("/requests")
def create_testimonial_request(req: TestimonialRequestPayload, db: Session = Depends(get_db)):
    try:
        result = UGCService(db).create_testimonial_request(
            athlete_name=req.athlete_name,
            score=req.score,
            athlete_email=req.athlete_email,
            parent_name=req.parent_name,
            parent_email=req.parent_email,
            score_tier=req.score_tier,
            athlete_age=req.athlete_age,
            sport=req.sport,
            context=req.context,
            source_partner=req.source_partner,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return result


@router.post("/submissions")
def submit_testimonial(req: TestimonialSubmissionPayload, db: Session = Depends(get_db)):
    try:
        result = UGCService(db).submit_testimonial(
            athlete_name=req.athlete_name,
            score=req.score,
            video_url=req.video_url,
            testimonial_text=req.testimonial_text,
            athlete_email=req.athlete_email,
            parent_name=req.parent_name,
            parent_email=req.parent_email,
            athlete_age=req.athlete_age,
            consent_athlete=req.consent_athlete,
            consent_parent=req.consent_parent,
            consent_share=req.consent_share,
            score_tier=req.score_tier,
            request_id=req.request_id,
            source_partner=req.source_partner,
            context=req.context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return result


@web_router.get("/ugc")
def ugc_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "ugc.html",
        {
            "page": "ugc",
            **_serialize_dashboard(db),
        },
    )


@web_router.post("/ugc/requests", response_class=HTMLResponse)
async def ugc_request_fragment(request: Request, db: Session = Depends(get_db)):
    form = parse_qs((await request.body()).decode("utf-8"))
    payload = TestimonialRequestPayload(
        athlete_name=form["athlete_name"][0],
        score=int(form["score"][0]),
        athlete_email=form.get("athlete_email", [None])[0],
        parent_name=form.get("parent_name", [None])[0],
        parent_email=form.get("parent_email", [None])[0],
        score_tier=form.get("score_tier", [None])[0],
        athlete_age=int(form["athlete_age"][0]) if form.get("athlete_age", [None])[0] else None,
        sport=form.get("sport", [None])[0],
        context=form.get("context", [None])[0],
        source_partner=form.get("source_partner", [None])[0],
    )
    try:
        result = UGCService(db).create_testimonial_request(
            athlete_name=payload.athlete_name,
            score=payload.score,
            athlete_email=payload.athlete_email,
            parent_name=payload.parent_name,
            parent_email=payload.parent_email,
            score_tier=payload.score_tier,
            athlete_age=payload.athlete_age,
            sport=payload.sport,
            context=payload.context,
            source_partner=payload.source_partner,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return templates.TemplateResponse(request, "partials/ugc_request_result.html", {"result": result})


@web_router.post("/ugc/submissions", response_class=HTMLResponse)
async def ugc_submission_fragment(request: Request, db: Session = Depends(get_db)):
    form = parse_qs((await request.body()).decode("utf-8"))
    payload = TestimonialSubmissionPayload(
        athlete_name=form["athlete_name"][0],
        score=int(form["score"][0]),
        video_url=form["video_url"][0],
        testimonial_text=form.get("testimonial_text", [None])[0],
        athlete_email=form.get("athlete_email", [None])[0],
        parent_name=form.get("parent_name", [None])[0],
        parent_email=form.get("parent_email", [None])[0],
        athlete_age=int(form["athlete_age"][0]) if form.get("athlete_age", [None])[0] else None,
        consent_athlete=_as_bool(form.get("consent_athlete", [None])[0], default=False),
        consent_parent=_as_bool(form.get("consent_parent", [None])[0], default=False),
        consent_share=_as_bool(form.get("consent_share", [None])[0], default=False),
        score_tier=form.get("score_tier", [None])[0],
        request_id=form.get("request_id", [None])[0],
        source_partner=form.get("source_partner", [None])[0],
        context=form.get("context", [None])[0],
    )
    try:
        result = UGCService(db).submit_testimonial(
            athlete_name=payload.athlete_name,
            score=payload.score,
            video_url=payload.video_url,
            testimonial_text=payload.testimonial_text,
            athlete_email=payload.athlete_email,
            parent_name=payload.parent_name,
            parent_email=payload.parent_email,
            athlete_age=payload.athlete_age,
            consent_athlete=payload.consent_athlete,
            consent_parent=payload.consent_parent,
            consent_share=payload.consent_share,
            score_tier=payload.score_tier,
            request_id=payload.request_id,
            source_partner=payload.source_partner,
            context=payload.context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return templates.TemplateResponse(request, "partials/ugc_submission_result.html", {"result": result})
