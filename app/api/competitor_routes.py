import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.database import get_db
from app.services.competitor_service import CompetitorService


router = APIRouter(
    prefix="/api/control-room/competitors",
    tags=["competitors"],
    dependencies=[Depends(verify_api_key)],
)


class CompetitorObservationRequest(BaseModel):
    source_slug: str
    headline: str
    url: HttpUrl | None = None
    summary: str | None = None
    platform: str = "web"
    display_name: str | None = None
    source_url: HttpUrl | None = None


class CompetitorRespondRequest(BaseModel):
    platform: str = "linkedin"
    actor: str = "analyst"


@router.get("")
def list_competitors(db: Session = Depends(get_db)):
    dashboard = CompetitorService(db).list_dashboard()
    return {
        **dashboard,
        "source_count": len(dashboard["sources"]),
        "signal_count": len(dashboard["signals"]),
    }


@router.post("/observations")
def ingest_competitor_observation(req: CompetitorObservationRequest, db: Session = Depends(get_db)):
    result = CompetitorService(db).ingest_observation(req.model_dump(mode="json"))
    db.commit()
    return result


@router.post("/signals/{signal_id}/respond")
def respond_to_competitor_signal(
    signal_id: uuid.UUID,
    req: CompetitorRespondRequest,
    db: Session = Depends(get_db),
):
    try:
        result = CompetitorService(db).create_response_trigger(
            signal_id,
            platform=req.platform,
            actor=req.actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result
