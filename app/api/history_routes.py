from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.database import get_db
from app.models.review import DraftVariant, ReviewAction, ReviewActionType
from app.models.workflow import DraftState


router = APIRouter(prefix="/api/control-room/history", tags=["history"], dependencies=[Depends(verify_api_key)])


def _serialize_history_item(draft: DraftVariant, actions: list[ReviewAction]) -> dict:
    return {
        "id": str(draft.id),
        "platform": draft.platform.value,
        "content": draft.content,
        "hashtags": draft.hashtags,
        "state": draft.state.value,
        "compliance_result": draft.compliance_result,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "actions": [
            {
                "action": a.action.value,
                "actor": a.actor,
                "notes": a.notes,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in actions
        ],
    }


@router.get("/rejected")
def list_rejected(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    drafts = (
        db.query(DraftVariant)
        .filter(DraftVariant.state == DraftState.REJECTED)
        .order_by(DraftVariant.created_at.desc())
        .limit(limit)
        .all()
    )
    results = []
    for draft in drafts:
        actions = (
            db.query(ReviewAction)
            .filter(ReviewAction.draft_variant_id == draft.id)
            .order_by(ReviewAction.created_at.desc())
            .all()
        )
        results.append(_serialize_history_item(draft, actions))
    return {"items": results, "count": len(results)}


@router.get("/expired")
def list_expired(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    drafts = (
        db.query(DraftVariant)
        .filter(DraftVariant.state == DraftState.EXPIRED)
        .order_by(DraftVariant.created_at.desc())
        .limit(limit)
        .all()
    )
    results = []
    for draft in drafts:
        actions = (
            db.query(ReviewAction)
            .filter(ReviewAction.draft_variant_id == draft.id)
            .order_by(ReviewAction.created_at.desc())
            .all()
        )
        results.append(_serialize_history_item(draft, actions))
    return {"items": results, "count": len(results)}
