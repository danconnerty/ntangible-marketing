from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.database import get_db
from app.services.sports_calendar_service import SportsCalendarService


router = APIRouter(
    prefix="/api/control-room/sports",
    tags=["sports"],
    dependencies=[Depends(verify_api_key)],
)
web_router = APIRouter(prefix="/control-room", tags=["sports-web"])

templates = Jinja2Templates(directory="app/web/templates")


async def _parse_payload(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        raw = (await request.body()).decode("utf-8").strip()
        if not raw:
            return {}
        return json.loads(raw)

    form = await request.form()
    payload: dict[str, Any] = {}
    for key, value in form.multi_items():
        if key == "platforms":
            payload.setdefault(key, []).extend([item for item in str(value).split(",") if item])
        else:
            payload[key] = value
    return payload


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return request.headers.get("hx-request") == "true" or "text/html" in accept


@router.get("")
def list_sports_dashboard(db: Session = Depends(get_db)):
    return SportsCalendarService(db).list_dashboard()


@router.get("/calendar")
def list_sports_calendar(days: int = Query(default=28, ge=7, le=60), db: Session = Depends(get_db)):
    service = SportsCalendarService(db)
    return {
        "days": days,
        "calendar_days": service.list_dashboard(days=days)["calendar_days"],
        "events": service.list_calendar_window(days=days),
    }


@router.post("/windows/{window_slug}/stage")
async def stage_sports_window(window_slug: str, request: Request, db: Session = Depends(get_db)):
    payload = await _parse_payload(request)
    try:
        result = SportsCalendarService(db).stage_window(
            window_slug,
            actor=payload.get("actor", "planner"),
            platforms=payload.get("platforms") or [],
            note=payload.get("note"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    if _wants_html(request):
        return templates.TemplateResponse(
            request,
            "partials/sports_stage_result.html",
            {"result": result},
        )
    return result


@web_router.get("/sports")
def sports_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "sports.html",
        {
            "page": "sports",
            **SportsCalendarService(db).list_dashboard(),
        },
    )
