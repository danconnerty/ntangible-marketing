import uuid
from types import SimpleNamespace

from app.models.brain import KnowledgeNode
from app.services.repurposing_service import RepurposingService, RepurposingSourceInput


class FakeDB:
    def __init__(self):
        self.added = []
        self.flush_count = 0

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flush_count += 1


def test_create_platform_derivative_builds_manual_request(monkeypatch):
    fake_db = FakeDB()
    service = RepurposingService(fake_db)
    source = RepurposingSourceInput(
        source_kind="manual",
        source_id="seed-1",
        title="Pressure Performance",
        source_text="A nucleus post about translating pressure into proof.",
        source_platform="linkedin",
        actor="planner",
    )
    source_node = SimpleNamespace(id=uuid.uuid4())
    workflow = SimpleNamespace(id=uuid.uuid4(), slug="repurpose-linkedin-manual-seed-1")
    job = SimpleNamespace(id=uuid.uuid4(), status="manual_ready", trigger_event_id=uuid.uuid4())
    draft = SimpleNamespace(
        id=uuid.uuid4(),
        content="Repurposed LinkedIn draft",
        state=SimpleNamespace(value="manual_ready"),
        compliance_result={"subject": "Pressure Performance on LinkedIn"},
    )
    captured = {}

    def fake_ensure_workflow(request):
        captured["request"] = request
        return workflow, SimpleNamespace(id=uuid.uuid4(), version_number=1)

    def fake_create_manual_request(context, workflow_id):
        captured["manual_request"] = {"context": context, "workflow_id": workflow_id}
        return SimpleNamespace(id=uuid.uuid4(), source_payload={"request": context})

    monkeypatch.setattr(service.trigger_engine, "ensure_workflow", fake_ensure_workflow)
    monkeypatch.setattr(service.trigger_engine, "create_manual_request", fake_create_manual_request)
    monkeypatch.setattr(service.workflow_engine, "execute", lambda trigger: job)
    monkeypatch.setattr(service, "_first_draft_for_job", lambda content_job_id: draft)

    returned_workflow, returned_job, returned_draft = service._create_platform_derivative(source, source_node, "linkedin")

    assert returned_workflow.slug == workflow.slug
    assert returned_job.status == "manual_ready"
    assert returned_draft.content == "Repurposed LinkedIn draft"
    assert captured["request"].workflow_slug == "repurpose-linkedin-manual-seed-1"
    assert captured["manual_request"]["workflow_id"] == workflow.id


def test_fan_out_source_creates_derivative_records_and_blog_draft(monkeypatch):
    fake_db = FakeDB()
    service = RepurposingService(fake_db)
    source = RepurposingSourceInput(
        source_kind="manual",
        source_id="seed-1",
        title="Pressure Performance",
        source_text="A nucleus post about translating pressure into proof.",
        source_platform="linkedin",
        actor="planner",
    )
    source_node = SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(service, "_ensure_source", lambda incoming: source_node)

    def fake_platform_derivative(incoming_source, incoming_source_record, channel):
        return (
            SimpleNamespace(id=uuid.uuid4(), slug=f"repurpose-{channel}", name=f"{channel.title()} Workflow"),
            SimpleNamespace(id=uuid.uuid4(), status="manual_ready", trigger_event_id=uuid.uuid4()),
            SimpleNamespace(
                id=uuid.uuid4(),
                content=f"{channel} draft body",
                state=SimpleNamespace(value="manual_ready"),
                compliance_result={"subject": f"{channel} subject"},
            ),
        )

    monkeypatch.setattr(service, "_create_platform_derivative", fake_platform_derivative)

    result = service.fan_out_source(source)

    assert result["source_title"] == "Pressure Performance"
    assert {item["channel"] for item in result["derivatives"]} == {"x", "linkedin", "instagram", "newsletter", "blog"}
    # derivatives and runs are now KnowledgeNodes
    assert any(
        isinstance(obj, KnowledgeNode)
        and (obj.metadata_ or {}).get("repurposing_role") == "derivative"
        and (obj.metadata_ or {}).get("channel") == "blog"
        for obj in fake_db.added
    )
    assert any(
        isinstance(obj, KnowledgeNode)
        and (obj.metadata_ or {}).get("run_type") == "repurposing"
        for obj in fake_db.added
    )
