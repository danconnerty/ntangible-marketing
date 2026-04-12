from app.services.processor.handlers.base import HandlerResult
from app.services.processor.handlers.alert import handle
from app.services.processor.classifier import ClassificationResult


def test_alert_handler_when_alert():
    classification = ClassificationResult(
        summary="Urgent partner request",
        is_knowledge=False,
        is_alert=True,
        alert_reason="Time-sensitive partnership decision needed",
    )
    result = handle(
        raw_payload={"from": "dan@partner.co", "subject": "Urgent"},
        classification=classification,
    )
    assert isinstance(result, HandlerResult)
    assert result.handler_name == "alert"
    assert result.success is True
    assert result.detail["mock"] is True
    assert "Time-sensitive" in result.detail["message"]


def test_alert_handler_when_not_alert():
    classification = ClassificationResult(
        summary="Regular email",
        is_knowledge=True,
        is_alert=False,
    )
    result = handle(
        raw_payload={"from": "dan@partner.co", "subject": "Update"},
        classification=classification,
    )
    assert result is None
