"""Workflow trigger handler. Matches classifier output to active workflows."""
from __future__ import annotations
import logging
from sqlalchemy.orm import Session
from app.services.brain_query import BrainQuery
from app.services.processor.classifier import ClassificationResult
from app.services.processor.handlers.base import HandlerResult

logger = logging.getLogger(__name__)


def handle(*, db: Session, raw_payload: dict, classification: ClassificationResult) -> HandlerResult | None:
    if not classification.is_workflow_trigger:
        return None

    bq = BrainQuery(db)
    triggered = []
    skipped = []

    for slug in classification.workflow_slugs:
        workflow = bq.get_entity_by_slug("workflow", slug)
        if workflow is None:
            logger.warning("Classifier suggested workflow '%s' but it doesn't exist", slug)
            skipped.append(slug)
            continue

        trigger = bq.create_knowledge_node(
            kind="ingestion_trigger",
            title=f"Ingestion trigger: {classification.summary}",
            content=classification.workflow_reason or "",
            metadata={
                "workflow_slug": slug,
                "workflow_entity_id": str(workflow.id),
                "trigger_source": "processor",
                "classification_summary": classification.summary,
            },
        )
        logger.info("Triggered workflow '%s' from ingestion: %s (trigger_id=%s)", slug, classification.workflow_reason, trigger.id)
        triggered.append(slug)

    return HandlerResult(handler_name="workflow", success=True, detail={"triggered": triggered, "skipped": skipped, "reason": classification.workflow_reason})
