from __future__ import annotations

from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.database import get_db
from app.services.science_credibility_service import ScienceCredibilityService


try:  # pragma: no cover - fallback only matters when jinja2 is missing
    from fastapi.templating import Jinja2Templates
except ImportError:  # pragma: no cover
    Jinja2Templates = None


router = APIRouter(
    prefix="/api/control-room/science",
    tags=["science"],
    dependencies=[Depends(verify_api_key)],
)
web_router = APIRouter(prefix="/control-room", tags=["science-web"])


class _FallbackTemplates:
    def TemplateResponse(self, request: Request, template_name: str, context: dict):
        result = context.get("result", {})
        if template_name == "science.html":
            records = "".join(
                f"<article><h3>{item['title']}</h3><p>{item['summary']}</p><p>{item['status']}</p></article>"
                for item in context.get("records", [])
            )
            return HTMLResponse(f"<h1>Science Credibility</h1>{records}")
        if template_name == "partials/science_run_result.html":
            return HTMLResponse(
                f"<section class='campaign-run-result'><h2>{result.get('title')}</h2>"
                f"<p>Type: {result.get('science_type')}</p><p>Status: {result.get('status')}</p>"
                f"<p>{result.get('summary')}</p></section>"
            )
        return HTMLResponse("<section></section>")


templates = Jinja2Templates(directory="app/web/templates") if Jinja2Templates is not None else _FallbackTemplates()


class ScienceGenerateRequest(BaseModel):
    science_type: str
    platform: str = "linkedin"
    actor: str = "science"
    topic: str | None = None
    audience: str | None = None
    source_focus: str | None = None
    source_notes: list[str] = Field(default_factory=list)
    advisor_name: str | None = None
    white_paper_title: str | None = None
    milestone_name: str | None = None


@router.get("")
def science_dashboard(db: Session = Depends(get_db)):
    return ScienceCredibilityService(db).list_dashboard()


def _split_form_list(raw_value: str | list[str] | None) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        values = raw_value
    else:
        values = [part.strip() for part in raw_value.split(",")]
    return [value for value in values if value]


async def _science_payload(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
    else:
        body = (await request.body()).decode("utf-8")
        parsed = parse_qs(body, keep_blank_values=True)
        payload = {key: values[-1] if len(values) == 1 else values for key, values in parsed.items()}

    payload["source_notes"] = _split_form_list(payload.get("source_notes"))
    return payload


@router.post("/generate")
async def generate_science_content(request: Request, db: Session = Depends(get_db)):
    try:
        req = ScienceGenerateRequest.model_validate(await _science_payload(request))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    try:
        result = ScienceCredibilityService(db).generate_science_content(
            req.science_type,
            platform=req.platform,
            actor=req.actor,
            topic=req.topic,
            audience=req.audience,
            source_focus=req.source_focus,
            source_notes=req.source_notes,
            advisor_name=req.advisor_name,
            white_paper_title=req.white_paper_title,
            milestone_name=req.milestone_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(request, "partials/science_run_result.html", {"result": result})
    return result


@web_router.get("/science")
def science_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "science.html",
        {
            "page": "science",
            **ScienceCredibilityService(db).list_dashboard(),
        },
    )
