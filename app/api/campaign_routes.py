from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.database import get_db
from app.services.campaign_service import CampaignService


router = APIRouter(
    prefix="/api/control-room/campaigns",
    tags=["campaigns"],
    dependencies=[Depends(verify_api_key)],
)


class RunCampaignRequest(BaseModel):
    actor: str = "planner"


@router.get("")
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = CampaignService(db).list_campaigns()
    return {"campaigns": campaigns, "count": len(campaigns)}


@router.post("/{campaign_slug}/run")
def run_campaign(campaign_slug: str, req: RunCampaignRequest, db: Session = Depends(get_db)):
    try:
        result = CampaignService(db).run_campaign_by_slug(campaign_slug, actor=req.actor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result
