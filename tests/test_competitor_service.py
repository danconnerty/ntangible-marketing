import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.competitor_service import CompetitorService


def _make_signal(
    signal_type="positioning_shift",
    summary="Competitor moved toward athlete-mental-performance messaging",
    severity="medium",
    reaction_angle=None,
    status="open",
) -> SimpleNamespace:
    """Return a SimpleNamespace that mimics a KnowledgeNode signal."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        kind="signal",
        title=summary,
        content=summary,
        status=status,
        metadata_={
            "signal_type": signal_type,
            "severity": severity,
            "reaction_angle": reaction_angle,
        },
    )


def _make_source(slug="rival-brand", display_name="Rival Brand") -> SimpleNamespace:
    """Return a SimpleNamespace that mimics a competitor EntityNode."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        slug=slug,
        canonical_name=display_name,
        metadata_={
            "source_url": None,
            "platform": "web",
            "active": True,
        },
    )


def test_ingest_observation_creates_signal(monkeypatch):
    db = MagicMock()
    service = CompetitorService(db)
    source = _make_source()
    observation = SimpleNamespace(
        id=uuid.uuid4(),
        kind="observation",
        metadata_={"source_entity_id": str(source.id)},
    )
    signal = _make_signal()

    monkeypatch.setattr(service, "_ensure_source", lambda slug, payload: source)
    monkeypatch.setattr(service, "_create_observation", lambda ensured_source, payload: observation)
    monkeypatch.setattr(
        service.agent,
        "classify_observation",
        lambda payload: {
            "signal_type": "positioning_shift",
            "summary": "Competitor moved toward athlete-mental-performance messaging",
            "severity": "medium",
            "reaction_angle": "Lean harder into proof-first coach credibility.",
        },
    )
    monkeypatch.setattr(
        service,
        "_create_signal",
        lambda ensured_source, created_observation, classification: signal,
    )

    result = service.ingest_observation(
        {
            "source_slug": "rival-brand",
            "headline": "Pressure is trainable",
            "url": "https://example.com/post",
        }
    )

    assert result["signal_type"] == "positioning_shift"
    assert result["severity"] == "medium"
    assert result["summary"] == "Competitor moved toward athlete-mental-performance messaging"


def test_create_response_trigger_for_signal(monkeypatch):
    db = MagicMock()
    service = CompetitorService(db)
    signal = _make_signal(
        summary="Competitor moved toward pressure-data messaging",
        signal_type="positioning_shift",
        severity="medium",
    )
    workflow = SimpleNamespace(id=uuid.uuid4(), slug="competitor-response-linkedin", name="Competitor Response")

    monkeypatch.setattr(service, "_get_signal", lambda signal_id: signal)
    monkeypatch.setattr(service, "_resolve_response_workflow", lambda platform: workflow)
    monkeypatch.setattr(
        service.trigger_engine,
        "ingest_external",
        lambda payload, workflow_id: SimpleNamespace(id=uuid.uuid4(), source_payload=payload),
    )
    monkeypatch.setattr(
        service.workflow_engine,
        "execute",
        lambda trigger: SimpleNamespace(status="manual_ready"),
    )

    result = service.create_response_trigger(signal.id, platform="linkedin", actor="analyst")

    assert result["workflow_slug"] == "competitor-response-linkedin"
    assert result["status"] == "manual_ready"


def test_ingest_observation_auto_creates_response_for_medium_signal(monkeypatch):
    db = MagicMock()
    service = CompetitorService(db)
    source = _make_source()
    observation = SimpleNamespace(
        id=uuid.uuid4(),
        kind="observation",
        metadata_={"source_entity_id": str(source.id)},
    )
    signal = _make_signal(
        signal_type="positioning_shift",
        summary="Competitor pushed a new pressure messaging angle",
        severity="medium",
    )

    monkeypatch.setattr(service, "_ensure_source", lambda slug, payload: source)
    monkeypatch.setattr(service, "_create_observation", lambda ensured_source, payload: observation)
    monkeypatch.setattr(
        service.agent,
        "classify_observation",
        lambda payload: {
            "signal_type": "positioning_shift",
            "summary": "Competitor pushed a new pressure messaging angle",
            "severity": "medium",
        },
    )
    monkeypatch.setattr(service, "_create_signal", lambda ensured_source, created_observation, classification: signal)
    monkeypatch.setattr(
        service,
        "create_response_trigger",
        lambda signal_id, platform, actor="competitor_scout": {
            "signal_id": str(signal_id),
            "workflow_slug": f"competitor-response-{platform}",
            "status": "manual_ready",
        },
    )

    result = service.ingest_observation(
        {
            "source_slug": "rival-brand",
            "headline": "Pressure is trainable",
            "url": "https://example.com/post",
        }
    )

    assert result["auto_responded"] is True
    assert result["auto_runs"][0]["workflow_slug"] == "competitor-response-linkedin"
