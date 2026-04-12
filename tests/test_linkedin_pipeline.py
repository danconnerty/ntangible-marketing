import uuid
from unittest.mock import MagicMock

import pytest

from app.models.brain import KnowledgeNode
from app.publishers.linkedin_base import LinkedInPublishResult
from app.services.linkedin_pipeline import (
    determine_initial_status,
    generate_linkedin_item,
    publish_linkedin_item,
)


def _make_pending_node(
    content: str = "Pressure data beats vibes.",
    status: str = "pending",
) -> KnowledgeNode:
    node = KnowledgeNode(
        id=uuid.uuid4(),
        kind="draft",
        title="LinkedIn: test",
        content=content,
        status=status,
        metadata_={"platform": "linkedin"},
    )
    return node


# ------------------------------------------------------------------
# determine_initial_status
# ------------------------------------------------------------------

def test_determine_initial_status_tier_1():
    assert determine_initial_status("tier_1") == "pending"


def test_determine_initial_status_tier_2():
    assert determine_initial_status("tier_2") == "review_required"


def test_determine_initial_status_tier_3():
    assert determine_initial_status("tier_3") == "review_required"


# ------------------------------------------------------------------
# generate_linkedin_item
# ------------------------------------------------------------------

def test_generate_linkedin_item_does_not_auto_publish_tier_1(monkeypatch):
    class FakeDB:
        def __init__(self):
            self.added = []

        def add(self, item):
            self.added.append(item)

        def flush(self):
            pass

        def commit(self):
            pass

        def refresh(self, item):
            pass

        def query(self, *args, **kwargs):
            return MagicMock()

    def fake_generate_linkedin_post(content_type, pillar, claims, context):
        return (
            {
                "content": "Pressure data beats vibes.",
                "content_type": content_type,
                "pillar": pillar,
                "claim_keys_used": [],
                "hashtags": ["#MentalPerformance"],
                "intent": "brand",
            },
            {
                "prompt_snapshot": "prompt",
                "response": {"raw_text": "text"},
                "model": "claude",
                "tokens_in": 10,
                "tokens_out": 20,
                "cost_estimate": 0.1,
                "duration_ms": 100,
            },
        )

    def fake_compliance(draft, requested_claims, dynamic_value_groups=None):
        class Result:
            passed = True
            corrected_content = draft["content"]
            corrected_hashtags = draft["hashtags"]
            checks_run = ["trademarks"]
            failure_reason = None

        return Result()

    def fail_publish(*args, **kwargs):
        raise AssertionError("tier_1 generation should not auto-publish")

    monkeypatch.setattr(
        "app.services.linkedin_pipeline.generate_linkedin_post",
        fake_generate_linkedin_post,
    )
    monkeypatch.setattr(
        "app.services.linkedin_pipeline.run_linkedin_compliance_checks",
        fake_compliance,
    )
    monkeypatch.setattr(
        "app.services.linkedin_pipeline.publish_linkedin_item",
        fail_publish,
    )

    post = generate_linkedin_item(
        {
            "content_type": "thought_leadership",
            "pillar": "thought_leadership",
            "approval_tier": "tier_1",
            "claims": [],
            "context": "Pressure data beats vibes.",
        },
        FakeDB(),
    )

    assert post.status == "pending"


def test_generate_linkedin_item_tier_2_sets_review_required(monkeypatch):
    class FakeDB:
        def __init__(self):
            self.added = []

        def add(self, item):
            self.added.append(item)

        def flush(self):
            pass

        def commit(self):
            pass

        def refresh(self, item):
            pass

        def query(self, *args, **kwargs):
            return MagicMock()

    def fake_generate_linkedin_post(content_type, pillar, claims, context):
        return (
            {
                "content": "Data-driven decisions.",
                "content_type": content_type,
                "pillar": pillar,
                "claim_keys_used": [],
                "hashtags": [],
                "intent": "brand",
            },
            {
                "prompt_snapshot": "prompt",
                "response": {"raw_text": "text"},
                "model": "claude",
                "tokens_in": 10,
                "tokens_out": 20,
                "cost_estimate": 0.1,
                "duration_ms": 100,
            },
        )

    def fake_compliance(draft, requested_claims, dynamic_value_groups=None):
        class Result:
            passed = True
            corrected_content = draft["content"]
            corrected_hashtags = []
            checks_run = ["trademarks"]
            failure_reason = None

        return Result()

    monkeypatch.setattr(
        "app.services.linkedin_pipeline.generate_linkedin_post",
        fake_generate_linkedin_post,
    )
    monkeypatch.setattr(
        "app.services.linkedin_pipeline.run_linkedin_compliance_checks",
        fake_compliance,
    )

    post = generate_linkedin_item(
        {
            "content_type": "thought_leadership",
            "pillar": "thought_leadership",
            "approval_tier": "tier_2",
            "claims": [],
            "context": None,
        },
        FakeDB(),
    )

    assert post.status == "review_required"


# ------------------------------------------------------------------
# publish_linkedin_item
# ------------------------------------------------------------------

def test_publish_linkedin_item_uses_active_connection_target(monkeypatch):
    post = _make_pending_node()

    db = MagicMock()
    # BrainQuery.get_knowledge_node calls db.query(KnowledgeNode).filter(...).first()
    db.query.return_value.filter.return_value.first.return_value = post

    captured: dict[str, object] = {}

    class FakeConnectionService:
        def __init__(self, incoming_db):
            assert incoming_db is db

        def resolve_active_publish_target(self, channel):
            assert channel == "linkedin"
            return {
                "channel": "linkedin",
                "connection": object(),
                "destination": object(),
                "credentials": {"access_token": "runtime-linkedin-token"},
                "config": {
                    "provider_key": "linkedin",
                    "organization_urn": "urn:li:organization:999",
                },
            }

    def fake_get_linkedin_publisher(*, runtime_config=None):
        captured["runtime_config"] = runtime_config
        return MagicMock(
            publish_post=MagicMock(
                return_value=LinkedInPublishResult(
                    success=True,
                    post_id="urn:li:share:123",
                    post_url="https://www.linkedin.com/feed/update/urn:li:share:123",
                )
            )
        )

    monkeypatch.setattr(
        "app.services.linkedin_pipeline.PublishingConnectionService",
        FakeConnectionService,
    )
    monkeypatch.setattr(
        "app.services.linkedin_pipeline.get_linkedin_publisher",
        fake_get_linkedin_publisher,
    )

    result = publish_linkedin_item(post.id, db)

    assert result.status == "active"
    assert captured["runtime_config"] == {
        "access_token": "runtime-linkedin-token",
        "provider_key": "linkedin",
        "organization_urn": "urn:li:organization:999",
    }


def test_publish_linkedin_item_accepts_scheduled_status(monkeypatch):
    post = _make_pending_node(status="scheduled")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = post

    class FakeConnectionService:
        def __init__(self, incoming_db):
            pass

        def resolve_active_publish_target(self, channel):
            return None

    def fake_get_linkedin_publisher(*, runtime_config=None):
        return MagicMock(
            publish_post=MagicMock(
                return_value=LinkedInPublishResult(
                    success=True,
                    post_id="urn:li:share:456",
                    post_url="https://www.linkedin.com/feed/update/urn:li:share:456",
                )
            )
        )

    monkeypatch.setattr("app.services.linkedin_pipeline.PublishingConnectionService", FakeConnectionService)
    monkeypatch.setattr("app.services.linkedin_pipeline.get_linkedin_publisher", fake_get_linkedin_publisher)

    result = publish_linkedin_item(post.id, db)
    assert result.status == "active"


def test_publish_linkedin_item_sets_failed_on_error(monkeypatch):
    post = _make_pending_node()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = post

    class FakeConnectionService:
        def __init__(self, incoming_db):
            pass

        def resolve_active_publish_target(self, channel):
            return None

    def fake_get_linkedin_publisher(*, runtime_config=None):
        return MagicMock(
            publish_post=MagicMock(
                return_value=LinkedInPublishResult(success=False, error="api error")
            )
        )

    monkeypatch.setattr("app.services.linkedin_pipeline.PublishingConnectionService", FakeConnectionService)
    monkeypatch.setattr("app.services.linkedin_pipeline.get_linkedin_publisher", fake_get_linkedin_publisher)

    result = publish_linkedin_item(post.id, db)
    assert result.status == "failed"
    assert result.metadata_["failure_reason"] == "api error"


def test_publish_linkedin_item_sets_publishing_unknown_on_timeout(monkeypatch):
    post = _make_pending_node()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = post

    class FakeConnectionService:
        def __init__(self, incoming_db):
            pass

        def resolve_active_publish_target(self, channel):
            return None

    def fake_get_linkedin_publisher(*, runtime_config=None):
        return MagicMock(
            publish_post=MagicMock(
                return_value=LinkedInPublishResult(success=False, error="request timeout occurred")
            )
        )

    monkeypatch.setattr("app.services.linkedin_pipeline.PublishingConnectionService", FakeConnectionService)
    monkeypatch.setattr("app.services.linkedin_pipeline.get_linkedin_publisher", fake_get_linkedin_publisher)

    result = publish_linkedin_item(post.id, db)
    assert result.status == "publishing_unknown"


def test_publish_linkedin_item_raises_if_not_found():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(ValueError, match="LinkedIn post not found"):
        publish_linkedin_item(uuid.uuid4(), db)


def test_publish_linkedin_item_raises_if_wrong_status():
    post = _make_pending_node(status="active")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = post

    with pytest.raises(ValueError, match="Cannot publish post"):
        publish_linkedin_item(post.id, db)
