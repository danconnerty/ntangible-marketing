import uuid
from types import SimpleNamespace

from app.models.brain import KnowledgeNode
from app.models.science import ScienceContentStatus, ScienceContentType
from app.services.science_credibility_service import ScienceCredibilityService


class FakeDB:
    def __init__(self):
        self.added = []
        self.flushed = 0

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flushed += 1


def test_generate_science_content_creates_manual_ready_record(monkeypatch):
    db = FakeDB()
    service = ScienceCredibilityService(db)
    workflow_id = uuid.uuid4()
    trigger_id = uuid.uuid4()
    job_id = uuid.uuid4()
    draft_id = uuid.uuid4()

    monkeypatch.setattr(
        service,
        "_resolve_workflow",
        lambda science_type, platform: SimpleNamespace(
            id=workflow_id,
            slug=f"science-{science_type}-{platform}",
            name="Science Workflow",
            platform=platform,
        ),
    )
    monkeypatch.setattr(
        service.trigger_engine,
        "create_manual_request",
        lambda request_text, resolved_workflow_id: SimpleNamespace(
            id=trigger_id,
            source_payload={"request": request_text},
            workflow_id=resolved_workflow_id,
        ),
    )
    monkeypatch.setattr(
        service.workflow_engine,
        "execute",
        lambda trigger: SimpleNamespace(id=job_id, status="completed"),
    )
    monkeypatch.setattr(
        service,
        "_latest_draft_for_job",
        lambda incoming_job_id: SimpleNamespace(id=draft_id),
    )

    result = service.generate_science_content(
        ScienceContentType.ADVISOR_SPOTLIGHT.value,
        platform="linkedin",
        topic="Why validation matters",
        audience="college coaches",
        source_focus="science team credibility",
        source_notes=["white paper", "peer review pipeline"],
        advisor_name="Dr. Ed Levine",
    )

    assert result["science_type"] == ScienceContentType.ADVISOR_SPOTLIGHT.value
    assert result["status"] == ScienceContentStatus.REVIEW_READY.value
    assert result["workflow_slug"] == "science-advisor_spotlight-linkedin"
    assert result["draft_id"] == str(draft_id)
    assert any(isinstance(item, KnowledgeNode) and (item.metadata_ or {}).get("record_type") == "science" for item in db.added)

