from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.workflow import Platform
from app.services.brain_query import BrainQuery
from app.services.trigger_engine import TriggerEngine
from app.services.workflow_engine import WorkflowEngine
from data.sports_calendar import build_macro_calendar, get_calendar_window, iter_calendar_windows, rolling_calendar_days


@dataclass(frozen=True)
class SportsWorkflowRequest:
    partner_slug: str
    event_type: str
    platform: Platform
    workflow_slug: str
    content_type: str
    pillar: str
    context: str
    dynamic_value_groups: list[list[str]] = field(default_factory=list)
    approval_tier: str = "tier_1"


class SportsCalendarService:
    DEFAULT_DASHBOARD_DAYS = 28

    def __init__(self, db: Session):
        self.db = db
        self.bq = BrainQuery(db)
        self.trigger_engine = TriggerEngine(db)
        self.workflow_engine = WorkflowEngine(db)

    def list_dashboard(self, days: int = DEFAULT_DASHBOARD_DAYS) -> dict[str, Any]:
        return {
            "windows": self.list_windows(),
            "calendar_days": rolling_calendar_days(days),
            "stage_runs": self._list_stage_runs(),
        }

    def list_calendar_window(self, days: int = DEFAULT_DASHBOARD_DAYS, *, anchor: date | None = None) -> list[dict[str, Any]]:
        anchor = anchor or date.today()
        end_date = anchor + timedelta(days=days - 1)
        windows = build_macro_calendar(anchor.year) + build_macro_calendar(anchor.year + 1)
        events: list[dict[str, Any]] = []
        for window in windows:
            window_start = date.fromisoformat(str(window["start_date"]))
            window_end = date.fromisoformat(str(window["end_date"]))
            if window_end < anchor or window_start > end_date:
                continue
            events.append(
                {
                    "event_name": window["title"],
                    "title": window["title"],
                    "start_at": window["start_date"],
                    "end_at": window["end_date"],
                    "sport": window["sport"],
                    "event_type": window["window_type"],
                    "slug": window["slug"],
                    "content_bucket": window["content_bucket"],
                    "template_key": window["template_key"],
                    "default_platforms": window["default_platforms"],
                    "summary": window["summary"],
                    "stage_angle": window["stage_angle"],
                }
            )
        events.sort(key=lambda item: (item["start_at"], item["event_name"]))
        return events

    def list_windows(self) -> list[dict[str, Any]]:
        return build_macro_calendar()

    def load_season_calendar(self, year: int) -> list[dict[str, Any]]:
        return build_macro_calendar(year)

    def get_upcoming_events(self, days: int = 14) -> list[dict[str, Any]]:
        return self.list_calendar_window(days=days)

    def map_event_to_templates(self, event_id: str) -> list[dict[str, Any]]:
        window = get_calendar_window(event_id)
        if window is None:
            return []
        return [
            {
                "template_key": window.template_key,
                "content_bucket": window.content_bucket,
                "window_type": window.window_type,
                "default_platforms": list(window.default_platforms),
                "summary": window.summary,
                "stage_angle": window.stage_angle,
            }
        ]

    def stage_window(
        self,
        window_slug: str,
        *,
        actor: str = "planner",
        platforms: list[str] | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        window = get_calendar_window(window_slug)
        if window is None:
            raise ValueError(f"Sports calendar window not found: {window_slug}")

        selected_platforms = self._resolve_platforms(list(window.default_platforms), platforms)
        if not selected_platforms:
            raise ValueError("No valid target platforms provided")

        runs: list[dict[str, Any]] = []
        for platform in selected_platforms:
            request = SportsWorkflowRequest(
                partner_slug="sports_calendar",
                event_type=str(window.window_type),
                platform=platform,
                workflow_slug=f"sports-{window.slug}-{platform.value}",
                content_type=self._content_type_for(window.window_type, platform),
                pillar=self._pillar_for(window.window_type),
                context=self._build_context(window, actor=actor, note=note),
                dynamic_value_groups=[[window.title], [window.sport], [window.window_type]],
            )
            workflow, _version = self.trigger_engine.ensure_workflow(request)
            trigger = self.trigger_engine.create_manual_request(request.context, workflow.id)
            trigger.source_payload = {
                **trigger.source_payload,
                "actor": actor,
                "sports_window": {
                    "slug": window.slug,
                    "title": window.title,
                    "sport": window.sport,
                    "window_type": window.window_type,
                    "content_bucket": window.content_bucket,
                    "template_key": window.template_key,
                },
                "sports_window_slug": window.slug,
                "sports_window_title": window.title,
                "sports_window_type": window.window_type,
                "sports_window_sport": window.sport,
                "target_platform": platform.value,
                "request": request.context,
            }
            job = self.workflow_engine.execute(trigger)
            draft = self._first_draft_for_job(job.id)

            run = self.bq.create_knowledge_node(
                kind="run",
                title=f"Sports stage run: {window.title} / {platform.value}",
                status=job.status,
                metadata={
                    "run_type": "sports_stage",
                    "window_slug": window.slug,
                    "workflow_id": str(workflow.id),
                    "trigger_event_id": str(trigger.id),
                    "content_job_id": str(getattr(job, "id", "")) if getattr(job, "id", None) else None,
                    "actor": actor,
                    "target_platforms": [platform.value],
                    "summary": {
                        "window_slug": window.slug,
                        "workflow_slug": workflow.slug,
                        "platform": platform.value,
                        "content_job_id": str(getattr(job, "id", "")) if getattr(job, "id", None) else None,
                        "draft_id": str(draft.id) if draft else None,
                    },
                },
            )
            runs.append(
                {
                    "workflow_slug": workflow.slug,
                    "workflow_name": workflow.name,
                    "platform": platform.value,
                    "trigger_event_id": str(trigger.id),
                    "content_job_id": str(getattr(job, "id", "")) if getattr(job, "id", None) else None,
                    "draft_id": str(draft.id) if draft else None,
                    "status": job.status,
                    "content": draft.content if draft else None,
                }
            )

        return {
            "window_slug": window.slug,
            "window_title": window.title,
            "actor": actor,
            "runs": runs,
        }

    def _pillar_for(self, window_type: str) -> str:
        if window_type in {"partner_testing", "partner_series"}:
            return "client_proof"
        if window_type in {"signing_day", "championship_window"}:
            return "thought_leadership"
        return "blind_spot"

    def _content_type_for(self, window_type: str, platform: Platform) -> str:
        if platform == Platform.NEWSLETTER:
            return "newsletter"
        if platform == Platform.INSTAGRAM:
            return "partner_content" if window_type in {"partner_testing", "partner_series"} else "stat_card"
        if platform == Platform.LINKEDIN:
            return "company_update" if window_type == "signing_day" else "data_drop"
        return "trend_jack" if window_type in {"championship_window"} else "data_drop"

    def _build_context(self, window, *, actor: str, note: str | None) -> str:
        parts = [
            f"Sports calendar stage: {window.title}.",
            f"Sport: {window.sport}.",
            f"Window type: {window.window_type}.",
            f"Summary: {window.summary}.",
            f"Angle: {window.stage_angle}.",
            "Use the macro sports calendar as the source of truth.",
            f"Operator note: {note}." if note else "",
            f"Actor: {actor}.",
        ]
        return " ".join(part for part in parts if part)

    def _resolve_platforms(self, default_platforms: list[str], platforms: list[str] | None) -> list[Platform]:
        raw_platforms = platforms or default_platforms
        resolved: list[Platform] = []
        for platform in raw_platforms:
            try:
                resolved.append(Platform(platform))
            except ValueError:
                continue
        return resolved

    def _first_draft_for_job(self, content_job_id: uuid.UUID | None):
        if content_job_id is None:
            return None
        try:
            from app.models.review import DraftVariant

            return (
                self.db.query(DraftVariant)
                .filter(DraftVariant.content_job_id == content_job_id)
                .order_by(DraftVariant.created_at.asc())
                .first()
            )
        except Exception:
            return None

    def _list_stage_runs(self) -> list[dict[str, Any]]:
        try:
            runs = self.bq.list_knowledge_by_kind("run", limit=50)
            sports_runs = [r for r in runs if (r.metadata_ or {}).get("run_type") == "sports_stage"]
        except Exception:
            sports_runs = []
        return [
            {
                "id": str(run.id),
                "actor": (run.metadata_ or {}).get("actor", ""),
                "status": run.status,
                "target_platforms": (run.metadata_ or {}).get("target_platforms") or [],
                "summary": (run.metadata_ or {}).get("summary") or {},
            }
            for run in sports_runs
        ]
