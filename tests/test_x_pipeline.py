import uuid
from unittest.mock import MagicMock

from app.models.brain import KnowledgeNode
from app.publishers.base import PostResult
from app.services.x_pipeline import publish_partner_x_item


def _make_pending_node(content: str = "Pressure data beats vibes.") -> KnowledgeNode:
    node = KnowledgeNode(
        id=uuid.uuid4(),
        kind="draft",
        title="X post: test",
        content=content,
        status="pending",
        metadata_={"platform": "x"},
    )
    return node


def test_publish_partner_x_item_uses_active_connection_target(monkeypatch):
    item = _make_pending_node()

    db = MagicMock()
    # BrainQuery.get_knowledge_node calls db.query(KnowledgeNode).filter(...).first()
    db.query.return_value.filter.return_value.first.return_value = item

    captured: dict[str, object] = {}

    class FakeConnectionService:
        def __init__(self, incoming_db):
            assert incoming_db is db

        def resolve_active_publish_target(self, channel):
            assert channel == "x"
            return {
                "channel": "x",
                "connection": object(),
                "destination": object(),
                "credentials": {"access_token": "runtime-x-token"},
                "config": {"provider_key": "tweepy", "screen_name": "ntangible"},
            }

    def fake_get_publisher(*, platform="x", runtime_config=None):
        captured["platform"] = platform
        captured["runtime_config"] = runtime_config
        return MagicMock(
            post_tweet=MagicMock(
                return_value=PostResult(
                    success=True,
                    platform_post_id="x-123",
                    post_url="https://x.com/i/status/x-123",
                )
            )
        )

    monkeypatch.setattr(
        "app.services.x_pipeline.PublishingConnectionService",
        FakeConnectionService,
    )
    monkeypatch.setattr("app.services.x_pipeline.get_publisher", fake_get_publisher)

    result = publish_partner_x_item(item.id, db)

    assert result.status == "active"
    assert captured["platform"] == "x"
    assert captured["runtime_config"] == {
        "access_token": "runtime-x-token",
        "provider_key": "tweepy",
        "screen_name": "ntangible",
    }


def test_publish_partner_x_item_sets_failed_on_error(monkeypatch):
    item = _make_pending_node()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = item

    class FakeConnectionService:
        def __init__(self, incoming_db):
            pass

        def resolve_active_publish_target(self, channel):
            return None

    def fake_get_publisher(*, platform="x", runtime_config=None):
        return MagicMock(
            post_tweet=MagicMock(
                return_value=PostResult(success=False, error="rate limit exceeded")
            )
        )

    monkeypatch.setattr("app.services.x_pipeline.PublishingConnectionService", FakeConnectionService)
    monkeypatch.setattr("app.services.x_pipeline.get_publisher", fake_get_publisher)

    result = publish_partner_x_item(item.id, db)

    assert result.status == "failed"
    assert result.metadata_["failure_reason"] == "rate limit exceeded"


def test_publish_partner_x_item_sets_publishing_unknown_on_unknown_error(monkeypatch):
    item = _make_pending_node()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = item

    class FakeConnectionService:
        def __init__(self, incoming_db):
            pass

        def resolve_active_publish_target(self, channel):
            return None

    def fake_get_publisher(*, platform="x", runtime_config=None):
        return MagicMock(
            post_tweet=MagicMock(
                return_value=PostResult(success=False, error="unknown: network timeout")
            )
        )

    monkeypatch.setattr("app.services.x_pipeline.PublishingConnectionService", FakeConnectionService)
    monkeypatch.setattr("app.services.x_pipeline.get_publisher", fake_get_publisher)

    result = publish_partner_x_item(item.id, db)

    assert result.status == "publishing_unknown"


def test_publish_partner_x_item_raises_if_not_found(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    import pytest

    with pytest.raises(ValueError, match="X content not found"):
        publish_partner_x_item(uuid.uuid4(), db)


def test_publish_partner_x_item_raises_if_wrong_status(monkeypatch):
    item = _make_pending_node()
    item.status = "active"
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = item

    import pytest

    with pytest.raises(ValueError, match="Cannot publish X content"):
        publish_partner_x_item(item.id, db)
