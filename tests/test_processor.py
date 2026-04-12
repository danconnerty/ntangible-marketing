from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.services.processor.processor import ProcessorService


def test_tick_processes_pending_item():
    mock_db = MagicMock()
    mock_item = MagicMock()
    mock_item.id = "item-1"
    mock_item.source_type = "gmail"
    mock_item.source_id = "msg-123"
    mock_item.raw_payload = {"from": "test@test.com", "subject": "Test", "body": "Hello", "headers": {}}
    mock_item.status = "pending"
    mock_item.claimed_at = None

    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_item]

    classification = MagicMock()
    classification.is_knowledge = False
    classification.is_workflow_trigger = False
    classification.is_alert = False
    classification.summary = "Test email"

    with patch("app.services.processor.processor.should_filter", return_value=None), \
         patch("app.services.processor.processor.classify_item", return_value=classification), \
         patch("app.services.processor.processor.knowledge_handler") as mock_kh, \
         patch("app.services.processor.processor.workflow_handler") as mock_wh, \
         patch("app.services.processor.processor.alert_handler") as mock_ah:
        mock_kh.handle.return_value = None
        mock_wh.handle.return_value = None
        mock_ah.handle.return_value = None
        service = ProcessorService(mock_db)
        result = service.tick()
    assert result["processed"] == 1
    assert result["filtered"] == 0


def test_tick_filters_noise():
    mock_db = MagicMock()
    mock_item = MagicMock()
    mock_item.id = "item-1"
    mock_item.source_type = "gmail"
    mock_item.source_id = "msg-123"
    mock_item.raw_payload = {"from": "noreply@spam.com", "headers": {"List-Unsubscribe": "yes"}}
    mock_item.status = "pending"
    mock_item.claimed_at = None
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_item]

    from app.services.processor.prefilter import FilterReason
    with patch("app.services.processor.processor.should_filter", return_value=FilterReason("newsletter_unsubscribe", "Has unsubscribe")):
        service = ProcessorService(mock_db)
        result = service.tick()
    assert result["filtered"] == 1
    assert result["processed"] == 0


def test_tick_skips_claimed_items():
    mock_db = MagicMock()
    mock_item = MagicMock()
    mock_item.id = "item-1"
    mock_item.source_type = "gmail"
    mock_item.status = "pending"
    mock_item.claimed_at = datetime.now(timezone.utc)
    mock_item.claimed_by = "other-worker"
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_item]
    service = ProcessorService(mock_db)
    result = service.tick()
    assert result["processed"] == 0
    assert result["skipped"] == 1


def test_tick_empty_queue():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    service = ProcessorService(mock_db)
    result = service.tick()
    assert result["processed"] == 0
    assert result["filtered"] == 0
