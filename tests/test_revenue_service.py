import uuid
from types import SimpleNamespace

import pytest

from app.models.brain import EntityNode, KnowledgeNode
from app.models.trigger import TriggerEvent, TriggerType
from app.services.revenue_service import RevenueService, _PlaybookAdapter


class FakeDB:
    def __init__(self):
        self.added = []
        self.flush_count = 0

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flush_count += 1


def _make_playbook_entity(
    slug="alliance-registration-push",
    name="Alliance Registration Push",
    playbook_type="registration_push",
    persona="event_operator",
    offer="Register now",
    cta="Reserve your spot",
    default_audience="travel ball coaches",
    default_proof_points=None,
    active=True,
    workflow_id=None,
) -> EntityNode:
    entity = EntityNode(
        id=uuid.uuid4(),
        entity_type="playbook",
        canonical_name=name,
        slug=slug,
        status="active",
        metadata_={
            "description": "Drive registrations",
            "playbook_type": playbook_type,
            "workflow_id": str(workflow_id or uuid.uuid4()),
            "target_output": "linkedin",
            "persona": persona,
            "offer": offer,
            "cta": cta,
            "default_audience": default_audience,
            "default_proof_points": default_proof_points or ["Pressure data"],
            "active": active,
        },
    )
    return entity


def _make_goal_node(
    slug="alliance-registration-completions",
    name="Alliance registration completions",
    metric_type="registrations",
    attribution_window_days=14,
    active=True,
) -> KnowledgeNode:
    return KnowledgeNode(
        id=uuid.uuid4(),
        kind="goal",
        title=name,
        status="active",
        metadata_={
            "slug": slug,
            "metric_type": metric_type,
            "attribution_window_days": attribution_window_days,
            "active": active,
        },
    )


def _make_conversion_node(
    goal_id: uuid.UUID,
    external_event_id="conv-1",
    source_kind="partner_event",
    source_reference="evt-1",
    metric_value=1.0,
    goal_slug="alliance-registration-completions",
) -> KnowledgeNode:
    return KnowledgeNode(
        id=uuid.uuid4(),
        kind="conversion",
        title=f"Conversion: {goal_slug} / {external_event_id}",
        status="active",
        metadata_={
            "goal_node_id": str(goal_id),
            "goal_slug": goal_slug,
            "external_event_id": external_event_id,
            "source_kind": source_kind,
            "source_reference": source_reference,
            "metric_value": float(metric_value),
        },
    )


def test_run_playbook_by_slug_creates_execution_and_revenue_summary(monkeypatch):
    fake_db = FakeDB()
    playbook_entity = _make_playbook_entity()
    playbook = _PlaybookAdapter(playbook_entity)
    trigger = TriggerEvent(
        id=uuid.uuid4(),
        trigger_type=TriggerType.MANUAL_REQUEST,
        workflow_id=uuid.uuid4(),
        source_payload={"request": "Drive registrations"},
    )

    monkeypatch.setattr(RevenueService, "_ensure_defaults", lambda self: None)
    monkeypatch.setattr(RevenueService, "_get_playbook_by_slug", lambda self, slug: playbook)
    monkeypatch.setattr(RevenueService, "_build_trigger", lambda self, *args, **kwargs: trigger)
    monkeypatch.setattr(
        RevenueService,
        "_create_sales_packages",
        lambda self, playbook, source_kind, source_id, content_job_id=None: [
            SimpleNamespace(id=uuid.uuid4(), kind="sales_package")
        ],
    )

    class FakeWorkflowEngine:
        def __init__(self, db):
            self.db = db

        def execute(self, incoming_trigger):
            assert incoming_trigger is trigger
            return SimpleNamespace(id=uuid.uuid4(), status="completed", error_message=None)

    monkeypatch.setattr("app.services.revenue_service.WorkflowEngine", FakeWorkflowEngine)

    result = RevenueService(fake_db).run_playbook_by_slug(
        "alliance-registration-push",
        actor="sales",
        source_kind="partner_event",
        source_id="evt-1",
    )

    assert result["playbook_slug"] == "alliance-registration-push"
    assert result["intent"] == "revenue"
    assert result["status"] == "completed"
    assert result["sales_package_count"] == 1
    # The execution node is a KnowledgeNode with kind="execution"
    assert any(
        isinstance(item, KnowledgeNode) and item.kind == "execution"
        for item in fake_db.added
    )


def test_record_conversion_event_dedupes(monkeypatch):
    fake_db = FakeDB()
    goal = _make_goal_node()
    existing = _make_conversion_node(goal_id=goal.id)

    monkeypatch.setattr(RevenueService, "_ensure_defaults", lambda self: None)
    monkeypatch.setattr(RevenueService, "_get_goal_by_slug", lambda self, slug: goal)
    monkeypatch.setattr(
        RevenueService,
        "_find_conversion_event",
        lambda self, goal_id, external_event_id: existing,
    )

    result = RevenueService(fake_db).record_conversion_event(
        goal_slug="alliance-registration-completions",
        external_event_id="conv-1",
        source_kind="partner_event",
        source_reference="evt-1",
        metric_value=1,
    )

    assert result["id"] == str(existing.id)
    assert result["goal_slug"] == "alliance-registration-completions"


def test_record_conversion_event_requires_existing_goal(monkeypatch):
    monkeypatch.setattr(RevenueService, "_ensure_defaults", lambda self: None)
    monkeypatch.setattr(RevenueService, "_get_goal_by_slug", lambda self, slug: None)

    with pytest.raises(ValueError, match="Conversion goal not found"):
        RevenueService(FakeDB()).record_conversion_event(
            goal_slug="missing-goal",
            external_event_id="conv-2",
            source_kind="manual",
            source_reference="manual-run",
            metric_value=1,
        )
