"""Thin API endpoints for MCP server consumption.

These supplement existing control-room routes with list/create operations
that weren't exposed via the JSON API.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.database import get_db
from app.models.workflow import Platform, Workflow, WorkflowMode, WorkflowVersion
from app.schemas.workflow_config import WorkflowVersionConfig
from app.services.trigger_engine import TriggerEngine
from app.services.workflow_engine import WorkflowEngine


router = APIRouter(
    prefix="/api/mcp",
    tags=["mcp"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("/workflows")
def list_workflows(db: Session = Depends(get_db)):
    workflows = db.query(Workflow).order_by(Workflow.name).all()
    return {
        "workflows": [
            {
                "id": str(wf.id),
                "name": wf.name,
                "slug": wf.slug,
                "description": wf.description,
                "platform": wf.platform.value,
                "mode": wf.mode.value,
                "enabled": wf.enabled,
                "paused_at": wf.paused_at.isoformat() if wf.paused_at else None,
                "health_status": wf.health_status,
            }
            for wf in workflows
        ],
        "count": len(workflows),
    }


class CreateWorkflowRequest(BaseModel):
    name: str
    slug: str
    platform: str
    mode: str = "manual"
    description: str | None = None
    timezone: str = "America/New_York"
    content_type: str = "general"


@router.post("/workflows")
def create_workflow(req: CreateWorkflowRequest, db: Session = Depends(get_db)):
    try:
        platform = Platform(req.platform)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid platform: {req.platform}. Valid: {[p.value for p in Platform]}")
    try:
        mode = WorkflowMode(req.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}. Valid: {[m.value for m in WorkflowMode]}")

    existing = db.query(Workflow).filter(Workflow.slug == req.slug).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Workflow slug '{req.slug}' already exists")

    workflow = Workflow(
        id=uuid.uuid4(),
        name=req.name,
        slug=req.slug,
        description=req.description,
        platform=platform,
        mode=mode,
        content_type=req.content_type,
        timezone=req.timezone,
        enabled=True,
    )
    db.add(workflow)

    version = WorkflowVersion(
        id=uuid.uuid4(),
        workflow_id=workflow.id,
        version_number=1,
        config=WorkflowVersionConfig().model_dump(),
        author="mcp",
        is_active=True,
        version_note="Initial version",
    )
    db.add(version)
    workflow.active_version_id = version.id

    db.commit()
    return {
        "id": str(workflow.id),
        "slug": workflow.slug,
        "name": workflow.name,
        "platform": workflow.platform.value,
        "mode": workflow.mode.value,
        "active_version": version.version_number,
    }


class ManualRequestBody(BaseModel):
    request_text: str
    actor: str = "mcp"


@router.post("/workflows/{workflow_slug}/manual-request")
def create_manual_request(workflow_slug: str, req: ManualRequestBody, db: Session = Depends(get_db)):
    workflow = db.query(Workflow).filter(Workflow.slug == workflow_slug).first()
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_slug}' not found")
    if not workflow.enabled:
        raise HTTPException(status_code=409, detail="Workflow is disabled")

    trigger = TriggerEngine(db).create_manual_request(req.request_text, workflow.id)
    db.flush()

    job = WorkflowEngine(db).execute(trigger)
    db.commit()

    drafts = []
    if hasattr(job, "drafts"):
        drafts = [
            {
                "id": str(d.id),
                "platform": d.platform.value,
                "content": d.content,
                "state": d.state.value,
            }
            for d in job.drafts
        ]

    return {
        "trigger_id": str(trigger.id),
        "job_id": str(job.id),
        "job_status": job.status,
        "error_message": job.error_message,
        "drafts": drafts,
    }


@router.post("/process-file")
def mcp_process_file(request_body: dict, db: Session = Depends(get_db)):
    """Receive a file from the MCP and enqueue for processing."""
    import hashlib
    from app.models.ingestion import IngestionQueueItem, IngestionSourceType
    content = request_body.get("content", "")
    file_name = request_body.get("file_name", "unknown")
    file_type = request_body.get("file_type")
    source_id = hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]
    item = IngestionQueueItem(
        source_type=IngestionSourceType.MCP_FILE.value,
        source_id=f"mcp-{source_id}",
        raw_payload={"content": content, "file_name": file_name, "file_type": file_type},
    )
    db.add(item)
    db.commit()
    return {"queued": True, "item_id": str(item.id)}
