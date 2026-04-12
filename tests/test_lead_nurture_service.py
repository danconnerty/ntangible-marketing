import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.lead_nurture_service import LeadNurtureService


def test_build_nurture_recommendations_uses_lead_stage_and_memory(monkeypatch):
    db = MagicMock()
    service = LeadNurtureService(db)
    lead = SimpleNamespace(
        id=uuid.uuid4(),
        canonical_name="West Coast Academy",
        metadata_={"stage": "qualified", "priority": "high", "sport": "softball"},
    )

    monkeypatch.setattr(
        service.memory,
        "build_generation_context",
        lambda query, platform=None, approved_limit=3, rejected_limit=2, workflow_slug=None: {
            "approved_examples": [{"id": "1", "content": "Proof-first coach story"}],
            "rejected_examples": [],
            "memory_ids": ["1"],
        },
    )

    recommendations = service.build_recommendations(lead)

    assert recommendations["touchpoint_type"] == "case-study-followup"
    assert "West Coast Academy" in recommendations["summary"]


def test_generate_content_for_lead_creates_manual_request(monkeypatch):
    db = MagicMock()
    service = LeadNurtureService(db)
    lead = SimpleNamespace(
        id=uuid.uuid4(),
        canonical_name="West Coast Academy",
        metadata_={"stage": "proposal", "priority": "high"},
    )
    workflow = SimpleNamespace(id=uuid.uuid4(), slug="lead-nurture-linkedin")
    task_node = SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(service, "_get_lead", lambda lead_id: lead)
    monkeypatch.setattr(service, "_resolve_lead_workflow", lambda platform: workflow)
    monkeypatch.setattr(
        service.trigger_engine,
        "create_manual_request",
        lambda request_text, workflow_id: SimpleNamespace(id=uuid.uuid4(), source_payload={"request": request_text}),
    )
    monkeypatch.setattr(
        service.workflow_engine,
        "execute",
        lambda trigger: SimpleNamespace(status="manual_ready"),
    )
    monkeypatch.setattr(
        service.bq,
        "create_knowledge_node",
        lambda **kwargs: task_node,
    )

    result = service.generate_content(lead.id, platform="linkedin", actor="sales")

    assert result["workflow_slug"] == "lead-nurture-linkedin"
    assert result["status"] == "manual_ready"
