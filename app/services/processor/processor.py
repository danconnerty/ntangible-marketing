"""Main processor service. Polls ingestion_queue, classifies, routes to handlers."""
from __future__ import annotations
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.ingestion import IngestionQueueItem, IngestionStatus
from app.services.processor.prefilter import should_filter
from app.services.processor.classifier import classify_item
from app.services.processor.handlers import knowledge as knowledge_handler
from app.services.processor.handlers import workflow as workflow_handler
from app.services.processor.handlers import alert as alert_handler

logger = logging.getLogger(__name__)

CLAIM_TIMEOUT = timedelta(minutes=15)
BATCH_LIMIT = 20


class ProcessorService:
    def __init__(self, db: Session, *, worker_name: str = "processor"):
        self.db = db
        self.worker_name = worker_name

    def tick(self, now: datetime | None = None) -> dict[str, int]:
        now = now or datetime.now(timezone.utc)
        counts = {"processed": 0, "filtered": 0, "failed": 0, "skipped": 0}
        items = (
            self.db.query(IngestionQueueItem)
            .filter(IngestionQueueItem.status == IngestionStatus.PENDING.value)
            .order_by(IngestionQueueItem.created_at.asc())
            .limit(BATCH_LIMIT)
            .all()
        )
        for item in items:
            if item.claimed_at and item.claimed_at > now - CLAIM_TIMEOUT:
                counts["skipped"] += 1
                continue
            item.claimed_at = now
            item.claimed_by = self.worker_name
            item.status = IngestionStatus.PROCESSING.value
            self.db.flush()
            try:
                self._process_item(item, now)
                counts["processed" if item.status == IngestionStatus.COMPLETED.value else "filtered"] += 1
            except Exception:
                logger.exception("Failed to process item %s", item.id)
                item.status = IngestionStatus.FAILED.value
                item.error = "Processing failed - check logs"
                item.processed_at = now
                counts["failed"] += 1
        return counts

    def _process_item(self, item: IngestionQueueItem, now: datetime) -> None:
        filter_result = should_filter(item.source_type, item.raw_payload)
        if filter_result is not None:
            item.status = IngestionStatus.FILTERED.value
            item.result = {"filter_reason": filter_result.reason, "filter_detail": filter_result.detail}
            item.processed_at = now
            logger.info("Filtered item %s: %s", item.id, filter_result.reason)
            return

        active_workflows = self._get_active_workflows()
        entity_types = self._get_entity_types()
        topics = self._get_topics()

        classification = classify_item(
            source_type=item.source_type, raw_payload=item.raw_payload,
            active_workflows=active_workflows, entity_types=entity_types,
            topics=topics,
        )
        item.classification = {
            "summary": classification.summary,
            "is_knowledge": classification.is_knowledge,
            "knowledge_kind": classification.knowledge_kind,
            "topic_key": classification.topic_key,
            "confidence": classification.confidence,
            "knowledge_entities": classification.knowledge_entities,
            "is_workflow_trigger": classification.is_workflow_trigger,
            "workflow_slugs": classification.workflow_slugs,
            "workflow_reason": classification.workflow_reason,
            "is_alert": classification.is_alert,
            "alert_reason": classification.alert_reason,
        }

        results = {}
        kr = knowledge_handler.handle(db=self.db, raw_payload=item.raw_payload, classification=classification)
        if kr: results["knowledge"] = kr.detail
        wr = workflow_handler.handle(db=self.db, raw_payload=item.raw_payload, classification=classification)
        if wr: results["workflow"] = wr.detail
        ar = alert_handler.handle(raw_payload=item.raw_payload, classification=classification)
        if ar: results["alert"] = ar.detail

        item.result = results
        item.status = IngestionStatus.COMPLETED.value
        item.processed_at = now
        logger.info("Processed item %s: %s", item.id, classification.summary)

    def _get_active_workflows(self) -> list[dict]:
        from app.services.brain_query import BrainQuery
        bq = BrainQuery(self.db)
        workflows = bq.list_entities_by_type("workflow")
        return [{"slug": w.slug, "name": w.canonical_name, "description": w.description or ""} for w in workflows]

    def _get_entity_types(self) -> list[str]:
        from app.models.brain import EntityNode
        rows = self.db.query(EntityNode.entity_type).distinct().all()
        return [r[0] for r in rows]

    def _get_topics(self) -> list[dict]:
        from app.models.brain import TopicProfile
        topics = self.db.query(TopicProfile).filter(TopicProfile.enabled == True).order_by(TopicProfile.priority.asc()).all()  # noqa: E712
        return [{"key": t.topic_key, "name": t.display_name} for t in topics]


def run_processor_loop(db_factory, *, interval_seconds: int = 5) -> None:
    logger.info("Processor loop starting (interval=%ds)", interval_seconds)
    while True:
        db = db_factory()
        try:
            service = ProcessorService(db)
            result = service.tick()
            db.commit()
            if any(result.values()):
                logger.info("Processor tick: %s", result)
        except Exception:
            logger.exception("Processor tick failed")
            db.rollback()
        finally:
            db.close()
        time.sleep(interval_seconds)
