from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.database import get_db
from app.services.workflow_editor import WorkflowEditor


router = APIRouter(
    prefix="/api/control-room/workflows",
    tags=["workflow-editor"],
    dependencies=[Depends(verify_api_key)],
)


class ImproveWorkflowRequest(BaseModel):
    feedback: str
    actor: str = "claude"
    draft_id: str | None = None


@router.get("/{workflow_slug}")
def workflow_detail(workflow_slug: str, db: Session = Depends(get_db)):
    editor = WorkflowEditor(db)
    try:
        detail = editor.get_workflow_detail(workflow_slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    workflow = detail["workflow"]
    active_version = detail["active_version"]
    versions = detail["versions"]
    return {
        "workflow": {
            "name": workflow.name,
            "slug": workflow.slug,
            "platform": workflow.platform.value,
            "mode": workflow.mode.value,
        },
        "active_version": active_version.version_number if active_version else None,
        "versions": [
            {
                "version_number": version.version_number,
                "version_note": version.version_note,
                "author": version.author,
                "is_active": version.is_active,
            }
            for version in versions
        ],
        "approved_examples": detail["approved_examples"],
        "rejected_examples": detail["rejected_examples"],
    }


@router.post("/{workflow_slug}/improve")
def improve_workflow(workflow_slug: str, req: ImproveWorkflowRequest, db: Session = Depends(get_db)):
    editor = WorkflowEditor(db)
    try:
        proposal = editor.propose_version(
            workflow_slug,
            feedback=req.feedback,
            actor=req.actor,
            draft_id=req.draft_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return proposal


@router.post("/{workflow_slug}/versions/{version_number}/activate")
def activate_workflow_version(workflow_slug: str, version_number: int, db: Session = Depends(get_db)):
    editor = WorkflowEditor(db)
    try:
        version = editor.activate_version(workflow_slug, version_number)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return {
        "workflow_slug": workflow_slug,
        "active_version": version.version_number,
    }
