import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.review import DraftVariant
from app.services.partner_delivery_service import PartnerDeliveryService
from app.services.partner_intake_service import PartnerIntakeService


def test_ingest_webhook_creates_partner_event_and_trigger(monkeypatch):
    db = MagicMock()
    service = PartnerIntakeService(db)
    partner = SimpleNamespace(id=uuid.uuid4(), slug="alliance_fastpitch", canonical_name="Alliance Fastpitch")
    monkeypatch.setattr(service, "_resolve_partner", lambda slug: partner)
    monkeypatch.setattr(service, "_create_event_record", lambda partner, source, normalized, raw_payload: SimpleNamespace(id=uuid.uuid4()))
    monkeypatch.setattr(
        service,
        "_execute_requests",
        lambda partner, normalized, event_record: [{"workflow_slug": "partner-alliance-assessment-x"}],
    )

    result = service.ingest_webhook(
        "alliance_fastpitch",
        {"event_type": "assessment_completed", "external_event_id": "evt-1"},
    )

    assert result["partner_slug"] == "alliance_fastpitch"
    assert result["results"][0]["workflow_slug"] == "partner-alliance-assessment-x"


def test_create_bundle_from_partner_draft():
    db = MagicMock()
    service = PartnerDeliveryService(db)
    draft = SimpleNamespace(
        id=uuid.uuid4(),
        content="Caption",
        hashtags=["#Alliance"],
        platform=SimpleNamespace(value="instagram"),
    )
    partner = SimpleNamespace(id=uuid.uuid4(), canonical_name="Alliance Fastpitch", slug="alliance-fastpitch")
    event = SimpleNamespace(id=uuid.uuid4(), event_type="leaderboard_published")

    bundle = service.build_bundle(partner, event, draft, asset_ids=[])

    assert bundle.caption == "Caption"
    assert bundle.platform == "instagram"


def test_partner_draft_has_partner_intent_and_metadata():
    draft = DraftVariant(
        intent="partner",
        partner_slug="alliance_fastpitch",
        source_event_type="assessment_completed",
    )

    assert draft.intent == "partner"
    assert draft.partner_slug == "alliance_fastpitch"
