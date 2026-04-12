from __future__ import annotations

import uuid
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.database import get_db
from app.services.blog_service import BlogService


try:  # pragma: no cover - fallback only matters when jinja2 is missing
    from fastapi.templating import Jinja2Templates
except ImportError:  # pragma: no cover
    Jinja2Templates = None


router = APIRouter(
    prefix="/api/control-room/blog",
    tags=["blog"],
    dependencies=[Depends(verify_api_key)],
)
web_router = APIRouter(prefix="/control-room", tags=["blog-web"])


class _FallbackTemplates:
    def TemplateResponse(self, request: Request, template_name: str, context: dict):
        result = context.get("result", {})
        if template_name == "blog.html":
            articles = "".join(
                f"<article><h3>{item['title']}</h3><p>{item['status']}</p><p>{item['word_count']} words</p></article>"
                for item in context.get("articles", [])
            )
            return HTMLResponse(f"<h1>SEO &amp; Blog</h1>{articles}")
        if template_name == "partials/blog_publish_result.html":
            canonical_url = result.get("canonical_url")
            url_markup = f"<p><a href='{canonical_url}'>{canonical_url}</a></p>" if canonical_url else ""
            failure_markup = f"<p>{result.get('failure_reason')}</p>" if result.get("failure_reason") else ""
            return HTMLResponse(
                f"<section class='campaign-run-result'><h2>{result.get('title')}</h2>"
                f"<p>Status: {result.get('status')}</p>{url_markup}{failure_markup}</section>"
            )
        return HTMLResponse("<section></section>")


templates = Jinja2Templates(directory="app/web/templates") if Jinja2Templates is not None else _FallbackTemplates()


class BlogDraftRequest(BaseModel):
    topic: str
    audience: str
    target_keywords: list[str] = Field(default_factory=list)
    angle: str | None = None
    source_notes: list[str] = Field(default_factory=list)


class BlogPublishRequest(BaseModel):
    actor: str = "editor"


@router.get("")
def blog_dashboard(db: Session = Depends(get_db)):
    return BlogService(db).list_dashboard()


def _split_form_list(raw_value: str | list[str] | None) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        values = raw_value
    else:
        values = [part.strip() for part in raw_value.split(",")]
    return [value for value in values if value]


async def _blog_payload(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
    else:
        body = (await request.body()).decode("utf-8")
        parsed = parse_qs(body, keep_blank_values=True)
        payload = {key: values[-1] if len(values) == 1 else values for key, values in parsed.items()}

    payload["target_keywords"] = _split_form_list(payload.get("target_keywords"))
    payload["source_notes"] = _split_form_list(payload.get("source_notes"))
    return payload


@router.post("/drafts")
async def generate_blog_draft(request: Request, db: Session = Depends(get_db)):
    try:
        req = BlogDraftRequest.model_validate(await _blog_payload(request))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    try:
        result = BlogService(db).generate_draft(
            topic=req.topic,
            audience=req.audience,
            target_keywords=req.target_keywords,
            angle=req.angle,
            source_notes=req.source_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(request, "partials/blog_publish_result.html", {"result": result})
    return result


@router.post("/drafts/{article_id}/publish")
async def publish_blog_draft(article_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    try:
        req = BlogPublishRequest.model_validate(await _blog_payload(request))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    try:
        result = BlogService(db).publish_article(article_id, actor=req.actor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(request, "partials/blog_publish_result.html", {"result": result})
    return result


@web_router.get("/blog")
def blog_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "blog.html",
        {
            "page": "blog",
            **BlogService(db).list_dashboard(),
        },
    )
