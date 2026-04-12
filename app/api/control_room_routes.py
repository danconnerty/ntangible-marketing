import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.database import get_db
from app.models.review import ContentJob, DraftVariant, ReviewActionType
from app.models.trigger import TriggerEvent
from app.models.workflow import DraftState, Workflow, WorkflowVersion
from app.services.automatic_control import (
    build_scheduler_status,
    list_automatic_workflow_cards,
    move_workflow_to_manual,
    set_workflow_pause_state,
)
from app.services.review_queue import ReviewQueue


router = APIRouter(prefix="/api/control-room", tags=["control-room"], dependencies=[Depends(verify_api_key)])


class ActionRequest(BaseModel):
    action: str  # post_now, schedule, reject
    actor: str = "admin"
    notes: str | None = None
    scheduled_at: datetime | None = None


def _serialize_draft(draft: DraftVariant) -> dict:
    compliance_result = draft.compliance_result or {}
    return {
        "id": str(draft.id),
        "content_job_id": str(draft.content_job_id),
        "platform": draft.platform.value,
        "content": draft.content,
        "hashtags": draft.hashtags,
        "state": draft.state.value,
        "recommended_publish_at": draft.recommended_publish_at.isoformat() if draft.recommended_publish_at else None,
        "scheduled_publish_at": draft.scheduled_publish_at.isoformat() if draft.scheduled_publish_at else None,
        "expires_at": draft.expires_at.isoformat() if draft.expires_at else None,
        "compliance_result": compliance_result,
        "newsletter_subject": compliance_result.get("subject"),
        "newsletter_preview_text": compliance_result.get("preview_text"),
        "newsletter_segment": compliance_result.get("segment"),
        "platform_post_id": draft.platform_post_id,
        "post_url": draft.post_url,
        "publish_attempted_at": draft.publish_attempted_at.isoformat() if draft.publish_attempted_at else None,
        "published_via": draft.published_via,
        "published_at": draft.published_at.isoformat() if draft.published_at else None,
        "failure_reason": draft.failure_reason,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
    }


def _serialize_workflow_card(card: dict) -> dict:
    drafts = card.get("drafts", [])
    serialized_drafts = [
        draft if isinstance(draft, dict) else _serialize_draft(draft)
        for draft in drafts
    ]
    return {
        "workflow_id": card["workflow_id"],
        "workflow_name": card["workflow_name"],
        "workflow_slug": card.get("workflow_slug"),
        "platform": card["platform"],
        "mode": card["mode"],
        "timezone": card["timezone"],
        "health_status": card["health_status"],
        "paused_at": card.get("paused_at"),
        "last_run_at": card.get("last_run_at"),
        "last_success_at": card.get("last_success_at"),
        "last_error": card.get("last_error"),
        "next_trigger_at": card.get("next_trigger_at"),
        "publish_time_label": card.get("publish_time_label"),
        "queued_draft_count": card["queued_draft_count"],
        "drafts": serialized_drafts,
    }


@router.get("/manual")
def list_manual_queue(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    queue = ReviewQueue(db)
    drafts = queue.list_manual(limit=limit)
    return {"drafts": [_serialize_draft(d) for d in drafts], "count": len(drafts)}


@router.get("/automatic")
def list_automatic_queue(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    queue = ReviewQueue(db)
    drafts = queue.list_automatic(limit=limit)
    return {"drafts": [_serialize_draft(d) for d in drafts], "count": len(drafts)}


@router.get("/automatic/workflows")
def list_automatic_workflows(db: Session = Depends(get_db)):
    cards = list_automatic_workflow_cards(db)
    return {"workflows": [_serialize_workflow_card(card) for card in cards], "count": len(cards)}


@router.get("/drafts/{draft_id}")
def get_draft_detail(draft_id: str, db: Session = Depends(get_db)):
    queue = ReviewQueue(db)
    detail = queue.get_draft_detail(uuid.UUID(draft_id))
    if not detail:
        raise HTTPException(status_code=404, detail="Draft not found")

    draft = detail["draft"]
    job = detail["job"]

    result = _serialize_draft(draft)

    if job:
        # Add provenance info
        trigger = db.query(TriggerEvent).filter(TriggerEvent.id == job.trigger_event_id).first()
        workflow = db.query(Workflow).filter(Workflow.id == job.workflow_id).first()
        version = db.query(WorkflowVersion).filter(WorkflowVersion.id == job.workflow_version_id).first()

        result["provenance"] = {
            "workflow_name": workflow.name if workflow else None,
            "workflow_slug": workflow.slug if workflow else None,
            "workflow_mode": workflow.mode.value if workflow else None,
            "version_number": version.version_number if version else None,
            "version_note": version.version_note if version else None,
            "trigger_type": trigger.trigger_type.value if trigger else None,
            "trigger_payload": trigger.source_payload if trigger else None,
            "prompt_snapshot": job.prompt_snapshot,
            "compliance_snapshot": job.compliance_snapshot,
        }

    return result


@router.post("/drafts/{draft_id}/action")
def draft_action(draft_id: str, req: ActionRequest, db: Session = Depends(get_db)):
    action_map = {
        "post_now": ReviewActionType.POST_NOW,
        "schedule": ReviewActionType.SCHEDULE,
        "reject": ReviewActionType.REJECT,
        "pause": ReviewActionType.PAUSE,
        "move_to_manual": ReviewActionType.MOVE_TO_MANUAL,
    }
    if req.action not in action_map:
        raise HTTPException(status_code=400, detail=f"Invalid action: {req.action}")

    queue = ReviewQueue(db)
    try:
        draft = queue.act(
            draft_id=uuid.UUID(draft_id),
            action=action_map[req.action],
            actor=req.actor,
            notes=req.notes,
            scheduled_at=req.scheduled_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    db.commit()
    return _serialize_draft(draft)


@router.post("/workflows/{workflow_id}/pause")
def pause_workflow(workflow_id: str, db: Session = Depends(get_db)):
    try:
        workflow = set_workflow_pause_state(db, workflow_id, paused=True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return {
        "workflow_id": str(workflow.id),
        "mode": workflow.mode.value,
        "health_status": workflow.health_status,
        "paused_at": workflow.paused_at.isoformat() if workflow.paused_at else None,
    }


@router.post("/workflows/{workflow_id}/resume")
def resume_workflow(workflow_id: str, db: Session = Depends(get_db)):
    try:
        workflow = set_workflow_pause_state(db, workflow_id, paused=False)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return {
        "workflow_id": str(workflow.id),
        "mode": workflow.mode.value,
        "health_status": workflow.health_status,
        "paused_at": workflow.paused_at.isoformat() if workflow.paused_at else None,
    }


@router.post("/workflows/{workflow_id}/move-to-manual")
def move_to_manual_workflow(workflow_id: str, db: Session = Depends(get_db)):
    try:
        workflow = move_workflow_to_manual(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return {
        "workflow_id": str(workflow.id),
        "mode": workflow.mode.value,
        "health_status": workflow.health_status,
        "paused_at": workflow.paused_at.isoformat() if workflow.paused_at else None,
    }


@router.get("/status")
def control_room_status(db: Session = Depends(get_db)):
    manual_count = db.query(DraftVariant).filter(DraftVariant.state == DraftState.MANUAL_READY).count()
    auto_count = db.query(DraftVariant).filter(DraftVariant.state == DraftState.AUTOMATIC_READY).count()
    published_count = db.query(DraftVariant).filter(DraftVariant.state == DraftState.PUBLISHED).count()
    rejected_count = db.query(DraftVariant).filter(DraftVariant.state == DraftState.REJECTED).count()
    expired_count = db.query(DraftVariant).filter(DraftVariant.state == DraftState.EXPIRED).count()
    failed_count = db.query(DraftVariant).filter(DraftVariant.state == DraftState.FAILED).count()

    return {
        "manual_queue": manual_count,
        "automatic_queue": auto_count,
        "published": published_count,
        "rejected": rejected_count,
        "expired": expired_count,
        "failed": failed_count,
    }


@router.get("/scheduler/status")
def scheduler_status(db: Session = Depends(get_db)):
    return build_scheduler_status(db)
