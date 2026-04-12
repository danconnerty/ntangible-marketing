import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.database import get_db
from app.services.lead_nurture_service import LeadNurtureService


router = APIRouter(
    prefix="/api/control-room/leads",
    tags=["leads"],
    dependencies=[Depends(verify_api_key)],
)


class LeadGenerateContentRequest(BaseModel):
    platform: str = "linkedin"
    actor: str = "sales"


@router.get("")
def list_leads(db: Session = Depends(get_db)):
    return LeadNurtureService(db).list_dashboard()


@router.post("/{lead_id}/generate-content")
def generate_content_for_lead(
    lead_id: uuid.UUID,
    req: LeadGenerateContentRequest,
    db: Session = Depends(get_db),
):
    try:
        result = LeadNurtureService(db).generate_content(
            lead_id,
            platform=req.platform,
            actor=req.actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result
