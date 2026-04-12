"""Mock alert handler. Logs alert but does not send."""
from __future__ import annotations
import logging
from app.services.processor.classifier import ClassificationResult
from app.services.processor.handlers.base import HandlerResult

logger = logging.getLogger(__name__)


def handle(*, raw_payload: dict, classification: ClassificationResult) -> HandlerResult | None:
    if not classification.is_alert:
        return None
    message = classification.alert_reason or classification.summary
    logger.info("MOCK ALERT: %s", message)
    return HandlerResult(
        handler_name="alert",
        success=True,
        detail={"mock": True, "message": message, "channel": "telegram"},
    )
