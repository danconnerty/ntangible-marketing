from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.database import get_db
from app.services.repurposing_service import RepurposingService, RepurposingSourceInput


router = APIRouter(
    prefix="/api/control-room/repurposing",
    tags=["repurposing"],
    dependencies=[Depends(verify_api_key)],
)
web_router = APIRouter(prefix="/control-room", tags=["repurposing-web"])

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
        if key == "channels":
            payload.setdefault(key, []).extend([item for item in str(value).split(",") if item])
        elif key == "source_metadata":
            payload[key] = {}
        else:
            payload[key] = value
    return payload


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return request.headers.get("hx-request") == "true" or "text/html" in accept


@router.get("")
def list_repurposing_dashboard(db: Session = Depends(get_db)):
    return RepurposingService(db).list_dashboard()


@router.post("/sources/{source_kind}/{source_id}/fanout")
async def fan_out_source(
    source_kind: str,
    source_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    payload = await _parse_payload(request)
    try:
        result = RepurposingService(db).fan_out_source(
            RepurposingSourceInput(
                source_kind=source_kind,
                source_id=source_id,
                title=payload["title"],
                source_text=payload["source_text"],
                source_platform=payload["source_platform"],
                source_url=payload.get("source_url"),
                actor=payload.get("actor", "planner"),
                channels=payload.get("channels") or [],
                source_metadata=payload.get("source_metadata") or {},
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    if _wants_html(request):
        return templates.TemplateResponse(
            request,
            "partials/repurposing_result.html",
            {"result": result},
        )
    return result


@web_router.get("/repurposing")
def repurposing_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "repurposing.html",
        {
            "page": "repurposing",
            **RepurposingService(db).list_dashboard(),
        },
    )
