import uuid

from app.models.instagram import (
    InstagramContentType,
    InstagramGenerationLog,
    InstagramRenderJob,
    InstagramRenderStatus,
    InstagramTemplateFamily,
    PartnerDeliveryChannel,
    PartnerDeliveryPackage,
    PartnerPackageStatus,
)


def test_instagram_content_type_enum():
    assert InstagramContentType.ATHLETE_SPOTLIGHT.value == "athlete_spotlight"
    assert InstagramContentType.EDUCATION_CAROUSEL.value == "education_carousel"
    assert InstagramContentType.PARTNER_CONTENT.value == "partner_content"


def test_instagram_render_job_fields():
    job = InstagramRenderJob(
        id=uuid.uuid4(),
        draft_variant_id=uuid.uuid4(),
        template_family=InstagramTemplateFamily.EDUCATION_CAROUSEL,
        status=InstagramRenderStatus.PENDING,
        input_payload={"slides": 5},
    )
    assert job.template_family == InstagramTemplateFamily.EDUCATION_CAROUSEL
    assert job.status == InstagramRenderStatus.PENDING


def test_instagram_generation_log_fields():
    log = InstagramGenerationLog(
        id=uuid.uuid4(),
        draft_variant_id=uuid.uuid4(),
        prompt_snapshot="system\n---\nuser",
        response={"caption": "Pressure reveals what training hides."},
        model="claude-sonnet-4-6",
        tokens_in=123,
        tokens_out=456,
        cost_estimate=0.015,
        duration_ms=1200,
    )
    assert log.tokens_in == 123
    assert log.response["caption"].startswith("Pressure")


def test_partner_delivery_package_fields():
    package = PartnerDeliveryPackage(
        id=uuid.uuid4(),
        draft_variant_id=uuid.uuid4(),
        partner_name="Alliance Fastpitch",
        source_event_type="leaderboard_published",
        status=PartnerPackageStatus.NEEDS_REVIEW,
        delivery_channel=PartnerDeliveryChannel.DASHBOARD,
        caption="Hook\nBody\nTag a teammate.",
        hashtags=["#AllianceFastpitch", "#ClutchFactor"],
        asset_ids=[],
        delivery_payload={"recipient": "dashboard"},
    )
    assert package.partner_name == "Alliance Fastpitch"
    assert package.status == PartnerPackageStatus.NEEDS_REVIEW
    assert package.delivery_channel == PartnerDeliveryChannel.DASHBOARD
