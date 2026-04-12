import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.brain import EntityNode, KnowledgeNode
from app.services.brain_query import BrainQuery
from app.services.review_queue import ReviewQueue
from app.services.trigger_engine import TriggerEngine
from app.services.workflow_engine import WorkflowEngine

logger = logging.getLogger(__name__)

CLAIM_TIMEOUT = timedelta(minutes=15)


@dataclass(frozen=True)
class SchedulerTickResult:
    calendar_rules_fired: int
    manual_drafts_expired: int
    drafts_published: int
    workflow_failures: int = 0


class SchedulerService:
    def __init__(self, db: Session, *, batch_limit: int = 50, worker_name: str = "scheduler"):
        self.db = db
        self.bq = BrainQuery(db)
        self.batch_limit = batch_limit
        self.worker_name = worker_name

    def tick(self, now: datetime | None = None) -> SchedulerTickResult:
        now = now or datetime.now(timezone.utc)
        fired_result = self.fire_due_calendar_rules(now)
        published_result = self.publish_due_drafts(now)
        fired, generation_failures = self._normalize_result(fired_result)
        published, publish_failures = self._normalize_result(published_result)
        expired = self.expire_due_manual_drafts(now)
        return SchedulerTickResult(
            calendar_rules_fired=fired,
            manual_drafts_expired=expired,
            drafts_published=published,
            workflow_failures=generation_failures + publish_failures,
        )

    def run_cycle(self, now: datetime | None = None) -> dict[str, int]:
        result = self.tick(now)
        return {
            "calendar_rules_fired": result.calendar_rules_fired,
            "manual_drafts_expired": result.manual_drafts_expired,
            "drafts_published": result.drafts_published,
            "workflow_failures": result.workflow_failures,
        }

    def _normalize_result(self, result: int | tuple[int, int]) -> tuple[int, int]:
        if isinstance(result, tuple):
            return result
        return result, 0

    def fire_due_calendar_rules(self, now: datetime) -> tuple[int, int]:
        rules = self.bq.list_due_schedule_rules(now, limit=self.batch_limit)
        # Filter to rules whose next_fire_at has passed and are not claimed
        due_rules = []
        for rule in rules:
            next_fire = rule.metadata_.get("next_fire_at")
            if not next_fire:
                continue
            try:
                next_fire_dt = datetime.fromisoformat(next_fire)
            except ValueError:
                continue
            if next_fire_dt > now:
                continue
            claimed_at_str = rule.metadata_.get("claimed_at")
            if claimed_at_str:
                try:
                    claimed_at = datetime.fromisoformat(claimed_at_str)
                    if claimed_at > now - CLAIM_TIMEOUT:
                        continue
                except ValueError:
                    pass
            # Check workflow is enabled
            wf_id = rule.metadata_.get("workflow_entity_id")
            if wf_id:
                import uuid as _uuid
                wf = self.bq.get_entity(_uuid.UUID(wf_id))
                if wf and (wf.status != "active" or wf.metadata_.get("enabled") is False):
                    continue
                if wf and wf.metadata_.get("paused_at"):
                    continue
            due_rules.append(rule)

        if not due_rules:
            return 0, 0

        trigger_engine = TriggerEngine(self.db)
        workflow_engine = WorkflowEngine(self.db)
        fired = 0
        failures = 0
        for rule in due_rules:
            if not self._claim_rule(rule, now):
                continue
            wf_id = rule.metadata_.get("workflow_entity_id")
            workflow = None
            if wf_id:
                import uuid as _uuid
                workflow = self.bq.get_entity(_uuid.UUID(wf_id))
            try:
                trigger_node = trigger_engine.fire_schedule_rule(rule)
                logger.info(
                    "Schedule rule %s fired for workflow %s",
                    rule.id,
                    workflow.slug if workflow else wf_id,
                )
                job = workflow_engine.execute_brain(trigger_node)
                meta = dict(rule.metadata_)
                meta["last_fired_at"] = now.isoformat()
                meta["next_fire_at"] = self._advance_next_fire(rule, now).isoformat()
                meta.pop("claimed_at", None)
                meta.pop("claimed_by", None)
                rule.metadata_ = meta
                if workflow is not None:
                    wm = dict(workflow.metadata_)
                    wm["last_run_at"] = now.isoformat()
                    if job.status == "failed":
                        wm["health_status"] = "unhealthy"
                        wm["last_error"] = job.metadata_.get("error")
                        failures += 1
                    else:
                        wm["health_status"] = "healthy"
                        wm["last_success_at"] = now.isoformat()
                        wm.pop("last_error", None)
                    workflow.metadata_ = wm
                fired += 1
            except Exception as exc:
                logger.exception("Schedule rule %s failed", rule.id)
                meta = dict(rule.metadata_)
                meta["last_fired_at"] = now.isoformat()
                meta["next_fire_at"] = self._advance_next_fire(rule, now).isoformat()
                meta.pop("claimed_at", None)
                meta.pop("claimed_by", None)
                rule.metadata_ = meta
                if workflow is not None:
                    wm = dict(workflow.metadata_)
                    wm["last_run_at"] = now.isoformat()
                    wm["health_status"] = "unhealthy"
                    wm["last_error"] = str(exc)
                    workflow.metadata_ = wm
                fired += 1
                failures += 1
        self.db.flush()
        return fired, failures

    def expire_due_manual_drafts(self, now: datetime) -> int:
        drafts = self.bq.list_expirable_drafts(now, limit=self.batch_limit)
        if not drafts:
            return 0

        queue = ReviewQueue(self.db)
        for draft in drafts:
            queue.act(
                draft_id=draft.id,
                action="expire",
                actor="scheduler",
                notes="Expired at end of manual review day.",
            )
        self.db.flush()
        return len(drafts)

    def publish_due_drafts(self, now: datetime) -> tuple[int, int]:
        due_drafts = self.bq.list_publishable_drafts(now, limit=self.batch_limit)
        if not due_drafts:
            return 0, 0

        queue = ReviewQueue(self.db)
        published = 0
        failures = 0
        for draft in due_drafts:
            try:
                logger.info(
                    "Publishing due draft %s (platform=%s, status=%s)",
                    draft.id, draft.metadata_.get("platform"), draft.status,
                )
                queue.publish_due_draft(draft.id, actor="scheduler")
                self._update_workflow_health_for_draft(draft, now)
                if draft.status == "active":
                    logger.info("Draft %s published successfully", draft.id)
                elif draft.status == "failed":
                    logger.warning("Draft %s publish failed: %s", draft.id, draft.metadata_.get("failure_reason"))
                    failures += 1
                published += 1
            except Exception as exc:
                logger.exception("Failed to publish draft %s", draft.id)
                failures += 1
                published += 1
        self.db.flush()
        return published, failures

    def _claim_rule(self, rule: KnowledgeNode, now: datetime) -> bool:
        claimed_at_str = rule.metadata_.get("claimed_at")
        if claimed_at_str:
            try:
                claimed_at = datetime.fromisoformat(claimed_at_str)
                if claimed_at > now - CLAIM_TIMEOUT:
                    return False
            except ValueError:
                pass
        meta = dict(rule.metadata_)
        meta["claimed_at"] = now.isoformat()
        meta["claimed_by"] = self.worker_name
        rule.metadata_ = meta
        self.db.flush()
        return True

    def _update_workflow_health_for_draft(self, draft: KnowledgeNode, now: datetime) -> None:
        workflow = self.bq.get_workflow_for_draft(draft.id)
        if workflow is None:
            return
        wm = dict(workflow.metadata_)
        wm["last_run_at"] = now.isoformat()
        if draft.status == "active":
            wm["last_success_at"] = now.isoformat()
            wm["health_status"] = "healthy"
            wm.pop("last_error", None)
        elif draft.status == "failed":
            wm["health_status"] = "unhealthy"
            wm["last_error"] = draft.metadata_.get("failure_reason")
        workflow.metadata_ = wm

    def _advance_next_fire(self, rule: KnowledgeNode, now: datetime) -> datetime:
        meta = rule.metadata_
        cron = meta.get("cron_expression", "0 9 * * *")
        fields = cron.split()
        if len(fields) != 5:
            return now + timedelta(days=1)

        minute_field, hour_field, _day_field, _month_field, weekday_field = fields
        minute = int(minute_field) if minute_field.isdigit() else 0
        hour = int(hour_field) if hour_field.isdigit() else 9
        timezone_name = meta.get("timezone", "America/New_York")
        tz = ZoneInfo(timezone_name)
        local_now = now.astimezone(tz)
        next_local = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_local <= local_now:
            next_local += timedelta(days=1)

        if weekday_field != "*" and weekday_field.isdigit():
            target_weekday = int(weekday_field)
            python_weekday = (target_weekday - 1) % 7
            while next_local.weekday() != python_weekday:
                next_local += timedelta(days=1)

        return next_local.astimezone(timezone.utc)


def run_scheduler_loop(db_factory, *, interval_seconds: int = 15) -> None:
    while True:
        db = db_factory()
        try:
            summary = SchedulerService(db).run_cycle()
            db.commit()
            if any(summary.values()):
                logger.info("Scheduler cycle completed: %s", summary)
        except Exception:
            logger.exception("Scheduler cycle failed")
            db.rollback()
        finally:
            db.close()
        time.sleep(interval_seconds)
