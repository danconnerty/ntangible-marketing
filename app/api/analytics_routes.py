import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.database import get_db
from app.services.analytics_ingest import (
    AnalyticsService,
    build_analytics_summary,
    get_publication_analytics_detail,
    list_recycle_candidates,
)


router = APIRouter(tags=["analytics"], dependencies=[Depends(verify_api_key)])


@router.get("/api/analytics/summary")
@router.get("/api/control-room/analytics/summary")
def analytics_summary(
    platform: str | None = Query(default=None),
    workflow_slug: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    if platform is None and workflow_slug is None and days == 30:
        return AnalyticsService(db).build_summary()
    try:
        return build_analytics_summary(
            db,
            platform=platform,
            workflow_slug=workflow_slug,
            days=days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/analytics/publications/{publication_id}")
def analytics_publication_detail(publication_id: str, db: Session = Depends(get_db)):
    detail = get_publication_analytics_detail(db, uuid.UUID(publication_id))
    if detail is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    return detail


@router.get("/api/analytics/recycle-candidates")
def analytics_recycle_candidates(
    platform: str | None = Query(default=None),
    days: int = Query(default=90, ge=1, le=365),
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        items = list_recycle_candidates(
            db,
            platform=platform,
            days=days,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"items": items, "count": len(items)}
