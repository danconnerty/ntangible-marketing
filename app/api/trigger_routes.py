"""Trigger ingestion API — partner webhooks and event feed."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.trigger_schemas import PartnerWebhookRequest
from app.auth import verify_api_key
from app.database import get_db
from app.services.partner_intake_service import PartnerIntakeService


router = APIRouter(tags=["triggers"])


def ingest_partner_webhook(
    partner_slug: str,
    payload: dict,
    db: Session,
) -> list[dict]:
    result = PartnerIntakeService(db).ingest_webhook(partner_slug, payload)
    return result["results"]


@router.post(
    "/webhooks/partners/{partner_slug}/events",
    dependencies=[Depends(verify_api_key)],
)
def partner_webhook(
    partner_slug: str,
    payload: PartnerWebhookRequest,
    db: Session = Depends(get_db),
):
    try:
        results = ingest_partner_webhook(partner_slug, payload.model_dump(), db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"partner_slug": partner_slug, "results": results}


@router.get("/triggers/events", dependencies=[Depends(verify_api_key)])
def list_trigger_events(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    engine = TriggerEngine(db)
    return {
        "items": engine.list_events(limit=limit),
        "limit": limit,
    }
