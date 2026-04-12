import uuid
from datetime import datetime, timezone

from app.models.ingestion import IngestionQueueItem, IngestionStatus, IngestionSourceType


def test_ingestion_queue_item_defaults():
    item = IngestionQueueItem(
        source_type=IngestionSourceType.GMAIL,
        source_id="msg-abc-123",
        raw_payload={"subject": "Hello", "body": "World"},
    )
    assert item.source_type == IngestionSourceType.GMAIL
    assert item.source_id == "msg-abc-123"
    assert item.status == IngestionStatus.PENDING
    assert item.raw_payload == {"subject": "Hello", "body": "World"}
    assert item.claimed_at is None
    assert item.classification is None
    assert item.result is None
    assert item.error is None


def test_ingestion_source_types():
    assert IngestionSourceType.GMAIL.value == "gmail"
    assert IngestionSourceType.CALENDAR.value == "calendar"
    assert IngestionSourceType.MCP_FILE.value == "mcp_file"
    assert IngestionSourceType.MANUAL_UPLOAD.value == "manual_upload"


def test_ingestion_statuses():
    assert IngestionStatus.PENDING.value == "pending"
    assert IngestionStatus.PROCESSING.value == "processing"
    assert IngestionStatus.COMPLETED.value == "completed"
    assert IngestionStatus.FILTERED.value == "filtered"
    assert IngestionStatus.FAILED.value == "failed"
