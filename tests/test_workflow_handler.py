from unittest.mock import MagicMock, patch

from app.services.processor.handlers.workflow import handle
from app.services.processor.handlers.base import HandlerResult
from app.services.processor.classifier import ClassificationResult


def test_workflow_handler_triggers_matching_workflow():
    classification = ClassificationResult(
        summary="Partner update email",
        is_knowledge=False,
        is_workflow_trigger=True,
        workflow_slugs=["partner-update"],
        workflow_reason="Partner relationship update",
    )
    mock_db = MagicMock()
    mock_workflow = MagicMock()
    mock_workflow.slug = "partner-update"
    mock_workflow.canonical_name = "Partner Update"
    mock_workflow.id = "wf-123"

    with patch("app.services.processor.handlers.workflow.BrainQuery") as MockBQ:
        mock_bq = MockBQ.return_value
        mock_bq.get_entity_by_slug.return_value = mock_workflow
        mock_bq.create_knowledge_node.return_value = MagicMock(id="trigger-1")
        result = handle(db=mock_db, raw_payload={"subject": "Update"}, classification=classification)

    assert isinstance(result, HandlerResult)
    assert result.handler_name == "workflow"
    assert result.success is True
    assert "partner-update" in result.detail["triggered"]


def test_workflow_handler_skips_unknown_slugs():
    classification = ClassificationResult(
        summary="Email about unknown workflow",
        is_knowledge=False,
        is_workflow_trigger=True,
        workflow_slugs=["nonexistent-workflow"],
        workflow_reason="Trigger reason",
    )
    mock_db = MagicMock()
    with patch("app.services.processor.handlers.workflow.BrainQuery") as MockBQ:
        mock_bq = MockBQ.return_value
        mock_bq.get_entity_by_slug.return_value = None
        result = handle(db=mock_db, raw_payload={"subject": "Update"}, classification=classification)
    assert result.detail["skipped"] == ["nonexistent-workflow"]


def test_workflow_handler_not_triggered():
    classification = ClassificationResult(summary="Regular email", is_knowledge=True, is_workflow_trigger=False)
    result = handle(db=MagicMock(), raw_payload={"subject": "Update"}, classification=classification)
    assert result is None
