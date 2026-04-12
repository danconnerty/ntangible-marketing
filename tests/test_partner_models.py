import uuid

from app.models.partner import PartnerAccount, PartnerDeliveryBundle, PartnerEventRecord


def test_partner_account_fields():
    partner = PartnerAccount(
        id=uuid.uuid4(),
        slug="alliance-fastpitch",
        display_name="Alliance Fastpitch",
        portal_username="alliance",
        portal_password_hash="hash",
        webhook_secret="secret",
        supported_event_types=["assessment_completed", "leaderboard_published"],
    )
    assert partner.slug == "alliance-fastpitch"


def test_partner_event_record_fields():
    event = PartnerEventRecord(
        id=uuid.uuid4(),
        partner_account_id=uuid.uuid4(),
        intake_source="webhook",
        event_type="assessment_completed",
        external_event_id="evt-123",
        raw_payload={},
        normalized_payload={},
        processing_status="received",
    )
    assert event.event_type == "assessment_completed"


def test_partner_delivery_bundle_fields():
    bundle = PartnerDeliveryBundle(
        id=uuid.uuid4(),
        partner_account_id=uuid.uuid4(),
        partner_event_record_id=uuid.uuid4(),
        draft_variant_id=uuid.uuid4(),
        platform="instagram",
        status="needs_review",
        caption="Partner-ready caption",
        hashtags=["#AllianceFastpitch"],
        asset_ids=[],
        delivery_payload={},
    )
    assert bundle.platform == "instagram"
