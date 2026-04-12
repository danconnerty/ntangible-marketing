import uuid

from sqlalchemy.dialects.postgresql import UUID

from app.models.content import ContentQueue, Intent, Pillar
from app.models.linkedin import (
    LinkedInApprovalTier,
    LinkedInContentType,
    LinkedInGenerationLog,
    LinkedInPost,
    LinkedInStatus,
)


def test_linkedin_post_defaults():
    post = LinkedInPost(
        id=uuid.uuid4(),
        content="Test LinkedIn post",
        content_type=LinkedInContentType.THOUGHT_LEADERSHIP,
        pillar=Pillar.THOUGHT_LEADERSHIP,
        intent=Intent.BRAND,
        hashtags=["#marketing"],
        approval_tier=LinkedInApprovalTier.TIER_1,
        status=LinkedInStatus.DRAFT,
        request_payload={"content_type": "thought_leadership"},
    )
    assert post.content_type == LinkedInContentType.THOUGHT_LEADERSHIP
    assert post.approval_tier == LinkedInApprovalTier.TIER_1
    assert post.status == LinkedInStatus.DRAFT
    assert LinkedInPost.__table__.c.status.default.arg == LinkedInStatus.DRAFT


def test_linkedin_status_values():
    assert LinkedInStatus.NEEDS_REVIEW.value == "needs_review"
    assert LinkedInStatus.APPROVED.value == "approved"
    assert LinkedInStatus.PUBLISHED.value == "published"


def test_linkedin_generation_log_fields():
    log = LinkedInGenerationLog(
        id=uuid.uuid4(),
        linkedin_post_id=None,
        prompt_snapshot="test prompt",
        response={"content": "test"},
        model="claude-sonnet-4-6",
        tokens_in=100,
        tokens_out=50,
        cost_estimate=0.001,
        duration_ms=500,
    )
    assert log.model == "claude-sonnet-4-6"
    assert log.linkedin_post_id is None


def test_linkedin_model_enum_and_column_wiring():
    post_table = LinkedInPost.__table__
    assert post_table.c.content_type.type.enums == [
        "thought_leadership",
        "data_insight",
        "company_update",
    ]
    assert post_table.c.approval_tier.type.enums == ["tier_1", "tier_2", "tier_3"]
    assert post_table.c.status.type.enums == [
        "draft",
        "needs_review",
        "approved",
        "publishing",
        "published",
        "publishing_unknown",
        "failed",
        "rejected",
    ]

    assert post_table.c.pillar.type.name == "pillar_enum"
    assert post_table.c.intent.type.name == "intent_enum"
    assert post_table.c.pillar.type is ContentQueue.__table__.c.pillar.type
    assert post_table.c.intent.type is ContentQueue.__table__.c.intent.type

    assert post_table.c.linkedin_post_id.type.length == 128
    assert isinstance(LinkedInGenerationLog.__table__.c.linkedin_post_id.type, UUID)
