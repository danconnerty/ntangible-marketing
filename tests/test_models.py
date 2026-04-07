import uuid

from app.models.content import (
    ContentQueue,
    ContentType,
    GenerationLog,
    Intent,
    Pillar,
    Status,
)


def test_content_queue_fields():
    item = ContentQueue(
        id=uuid.uuid4(),
        content="Test tweet",
        content_type=ContentType.HOT_TAKE,
        pillar=Pillar.BLIND_SPOT,
        intent=Intent.BRAND,
        hashtags=["#test"],
        status=Status.DRAFT,
        variant_group=uuid.uuid4(),
        request_payload={"content_type": "hot_take", "pillar": "blind_spot"},
        compliance_result={"passed": True},
    )
    assert item.content == "Test tweet"
    assert item.status == Status.DRAFT
    assert item.content_type == ContentType.HOT_TAKE


def test_content_type_enum():
    assert ContentType.HOT_TAKE.value == "hot_take"
    assert ContentType.DATA_DROP.value == "data_drop"
    assert ContentType.TREND_JACK.value == "trend_jack"


def test_status_enum():
    assert Status.DRAFT.value == "draft"
    assert Status.PUBLISHING.value == "publishing"
    assert Status.PUBLISHED.value == "published"
    assert Status.PUBLISHING_UNKNOWN.value == "publishing_unknown"
    assert Status.FAILED.value == "failed"
    assert Status.REJECTED.value == "rejected"


def test_generation_log_fields():
    log = GenerationLog(
        id=uuid.uuid4(),
        content_queue_id=None,
        prompt_snapshot="test prompt",
        response={"content": "test"},
        model="claude-sonnet-4-6",
        tokens_in=100,
        tokens_out=50,
        cost_estimate=0.001,
        duration_ms=500,
    )
    assert log.model == "claude-sonnet-4-6"
    assert log.content_queue_id is None


def test_database_enums_use_lowercase_values():
    assert ContentQueue.__table__.c.content_type.type.enums == [
        "hot_take",
        "data_drop",
        "trend_jack",
    ]
    assert ContentQueue.__table__.c.status.type.enums == [
        "draft",
        "publishing",
        "published",
        "publishing_unknown",
        "failed",
        "rejected",
    ]
