import uuid
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.review import ContentJob, DraftVariant
from app.models.trigger import CalendarRule, TriggerEvent, TriggerProcessingStatus, TriggerType
from app.models.workflow import DraftState, Platform, Workflow, WorkflowMode, WorkflowVersion
from app.schemas.workflow_config import WorkflowVersionConfig


def ensure_workflow(db, *, name: str, slug: str, platform: Platform, content_type: str, mode: WorkflowMode):
    workflow = db.query(Workflow).filter(Workflow.slug == slug).first()
    if workflow is None:
        workflow = Workflow(
            id=uuid.uuid4(),
            name=name,
            slug=slug,
            description="Seeded demo workflow",
            mode=mode,
            platform=platform,
            content_type=content_type,
            enabled=True,
        )
        db.add(workflow)
        db.flush()

    version = db.query(WorkflowVersion).filter(WorkflowVersion.workflow_id == workflow.id).first()
    if version is None:
        version = WorkflowVersion(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            version_number=1,
            config=WorkflowVersionConfig().model_dump(),
            version_note="Demo seed",
            author="seed",
            is_active=True,
        )
        db.add(version)
        db.flush()
        workflow.active_version_id = version.id
    return workflow, version


def seed():
    db = SessionLocal()
    try:
        workflow, version = ensure_workflow(
            db,
            name="Tuesday LinkedIn TL",
            slug="tuesday-linkedin-tl",
            platform=Platform.LINKEDIN,
            content_type="thought_leadership",
            mode=WorkflowMode.MANUAL,
        )
        trigger = TriggerEvent(
            id=uuid.uuid4(),
            trigger_type=TriggerType.CALENDAR,
            workflow_id=workflow.id,
            processing_status=TriggerProcessingStatus.PROCESSED,
            source_payload={"request": "Weekly thought leadership about pressure and recruiting."},
        )
        db.add(trigger)
        db.flush()

        job = ContentJob(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            workflow_version_id=version.id,
            trigger_event_id=trigger.id,
            prompt_snapshot={"system": "seed", "user": "seed"},
            status="completed",
        )
        db.add(job)
        db.flush()

        existing = db.query(DraftVariant).filter(DraftVariant.content_job_id == job.id).first()
        if existing is None:
            db.add(
                DraftVariant(
                    id=uuid.uuid4(),
                    content_job_id=job.id,
                    platform=Platform.LINKEDIN,
                    content="Pressure data changes recruiting conversations when staffs stop guessing.",
                    hashtags=["#MentalPerformance", "#Recruiting"],
                    state=DraftState.MANUAL_READY,
                    timezone="America/Toronto",
                    recommended_publish_at=datetime.now(timezone.utc) + timedelta(hours=2),
                    expires_at=datetime.now(timezone.utc).replace(hour=23, minute=59, second=59, microsecond=0),
                    compliance_result={"passed": True, "checks_run": ["trademarks", "claims"]},
                )
            )

        rule = db.query(CalendarRule).filter(CalendarRule.workflow_id == workflow.id).first()
        if rule is None:
            db.add(
                CalendarRule(
                    id=uuid.uuid4(),
                    workflow_id=workflow.id,
                    cron_expression="0 9 * * 2",
                    timezone="America/Toronto",
                    next_fire_at=datetime.now(timezone.utc) + timedelta(days=1),
                )
            )

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
