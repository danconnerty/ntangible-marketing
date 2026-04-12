from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.database import get_db
from app.services.partner_delivery_service import PartnerDeliveryService
from app.services.partner_intake_service import PartnerIntakeService


router = APIRouter(
    prefix="/api/control-room/partners",
    tags=["partners"],
    dependencies=[Depends(verify_api_key)],
)


class PartnerEventRequest(BaseModel):
    event_type: str
    external_event_id: str
    athlete_name: str | None = None
    commitment_school: str | None = None
    offer_school: str | None = None
    position: str | None = None
    score: int | None = None
    score_tier: str | None = None
    event_name: str | None = None
    registration_deadline: str | None = None
    milestone_name: str | None = None
    milestone_value: int | str | None = None
    athlete_count: int | None = None
    top_performers: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PartnerBundleActionRequest(BaseModel):
    status: str = "delivered"


@router.get("")
def list_partners(db: Session = Depends(get_db)):
    service = PartnerIntakeService(db)
    partners = service.list_partners()
    events = service.list_events(limit=20)
    bundles = PartnerDeliveryService(db).list_bundles(limit=20)
    return {
        "partners": partners,
        "events": events,
        "bundles": bundles,
    }


@router.post("/{partner_slug}/events")
def ingest_partner_event(
    partner_slug: str,
    req: PartnerEventRequest,
    db: Session = Depends(get_db),
):
    try:
        result = PartnerIntakeService(db).ingest_webhook(partner_slug, req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return result


@router.get("/events")
def list_partner_events(
    partner_slug: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items = PartnerIntakeService(db).list_events(partner_slug=partner_slug, limit=limit)
    return {"events": items, "count": len(items)}


@router.get("/bundles")
def list_partner_bundles(
    partner_slug: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    bundles = PartnerDeliveryService(db).list_bundles(partner_slug=partner_slug, limit=limit)
    return {"bundles": bundles, "count": len(bundles)}


@router.post("/bundles/{bundle_id}/action")
def update_partner_bundle(
    bundle_id: uuid.UUID,
    req: PartnerBundleActionRequest,
    db: Session = Depends(get_db),
):
    try:
        result = PartnerDeliveryService(db).update_bundle_status(bundle_id, req.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result
