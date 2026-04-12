from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.database import get_db
from app.services.revenue_service import RevenueService


router = APIRouter(
    prefix="/api/control-room/revenue",
    tags=["revenue"],
    dependencies=[Depends(verify_api_key)],
)


class RunRevenuePlaybookRequest(BaseModel):
    actor: str = "sales"
    source_kind: str = "manual"
    source_id: str = "manual-run"
    context: dict[str, Any] = Field(default_factory=dict)


class ConversionEventRequest(BaseModel):
    goal_slug: str
    external_event_id: str
    source_kind: str
    source_reference: str
    metric_value: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    partner_slug: str | None = None
    lead_account_id: str | None = None


@router.get("")
def revenue_dashboard(db: Session = Depends(get_db)):
    return RevenueService(db).list_dashboard()


@router.post("/playbooks/{playbook_slug}/run")
def run_playbook(playbook_slug: str, req: RunRevenuePlaybookRequest, db: Session = Depends(get_db)):
    try:
        result = RevenueService(db).run_playbook_by_slug(
            playbook_slug,
            actor=req.actor,
            source_kind=req.source_kind,
            source_id=req.source_id,
            context=req.context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result


@router.post("/conversions")
def record_conversion(req: ConversionEventRequest, db: Session = Depends(get_db)):
    try:
        result = RevenueService(db).record_conversion_event(
            goal_slug=req.goal_slug,
            external_event_id=req.external_event_id,
            source_kind=req.source_kind,
            source_reference=req.source_reference,
            metric_value=req.metric_value,
            metadata=req.metadata,
            partner_slug=req.partner_slug,
            lead_account_id=req.lead_account_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result
