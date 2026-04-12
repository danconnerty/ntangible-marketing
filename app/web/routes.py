import logging
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any
from urllib.parse import parse_qs, quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

try:  # pragma: no cover - exercised via fallback in environments without jinja2
    from fastapi.templating import Jinja2Templates
except ImportError:  # pragma: no cover - optional dependency
    Jinja2Templates = None

from app.database import get_db
from app.auth import (
    CONTROL_ROOM_SESSION_COOKIE,
    control_room_auth_enabled,
    create_session,
    exchange_code_for_tokens,
    get_cognito_login_url,
    get_cognito_logout_url,
)
from app.config import get_settings
from app.models.asset import Asset
from app.models.brain import EntityEdge, EntityNode, KnowledgeEdge, KnowledgeNode, TopicProfile
from app.models.campaign import Campaign, CampaignStatus
from app.models.trigger import CalendarRule, PartnerSource, TriggerEvent, TriggerType
from app.models.workflow import DraftState, Platform, Workflow, WorkflowMode, WorkflowVersion
from app.models.review import ContentJob, DraftVariant, ReviewAction, ReviewActionType
from app.services.brain_query import BrainQuery
from app.services.automatic_control import (
    build_scheduler_status,
    list_automatic_workflow_cards as list_automatic_workflow_cards_service,
    move_workflow_to_manual,
    pause_all_workflows,
    resume_all_workflows,
    set_workflow_pause_state,
)
from app.services.analytics_ingest import AnalyticsService, build_analytics_summary, generate_weekly_digest
from app.services.blog_service import BlogService
from app.services.campaign_service import CampaignService
from app.services.competitor_service import CompetitorService
from app.services.lead_nurture_service import LeadNurtureService
from app.services.memory_retrieval import MemoryRetrievalService
from app.services.partner_delivery_service import PartnerDeliveryService
from app.services.partner_intake_service import PartnerIntakeService
from app.services.repurposing_service import RepurposingService
from app.services.revenue_service import RevenueService
from app.services.review_queue import ReviewQueue
from app.services.science_credibility_service import ScienceCredibilityService
from app.services.sports_calendar_service import SportsCalendarService
from app.services.trigger_engine import TriggerEngine
from app.services.workflow_engine import WorkflowEngine
from app.services.publishing_connection_service import PublishingConnectionService
from app.services.ugc_service import UGCService
from app.services.video_content_service import VideoContentService
from app.schemas.workflow_config import CtaConfig, PromptConfig, RoutingConfig, WorkflowVersionConfig
from app.services.workflow_editor import WorkflowEditor


logger = logging.getLogger(__name__)

web_router = APIRouter(prefix="/control-room", tags=["web"])
public_router = APIRouter(tags=["public"])


def _render_cards(title: str, drafts: list[dict[str, Any]], description: str | None = None) -> str:
    card_html = []
    for draft in drafts:
        card_html.append(
            "".join(
                [
                    f"<article><h2>{draft.get('workflow_name', 'Draft')}</h2>",
                    f"<p>{draft.get('trigger_label', '')}</p>",
                    f"<p>{draft.get('trigger_reason', '')}</p>",
                    f"<p>{draft.get('content', '')}</p>",
                    f"<p>{draft.get('notes', '')}</p>",
                    f"<p>{draft.get('expires_label', '')}</p>",
                    "<button>Post Now</button>",
                    "<button>Schedule</button>",
                    "<button>Reject</button>",
                    "<button>Why This Draft?</button>",
                    "<button>Improve Workflow</button></article>",
                ]
            )
        )
    body = [f"<h1>{title}</h1>"]
    if description:
        body.append(f"<p>{description}</p>")
    body.extend(card_html)
    return "".join(body)


def _render_fallback_template(template_name: str, context: dict[str, Any]) -> str:
    if template_name == "manual.html":
        return _render_cards("Manual Queue", context.get("drafts", []))
    if template_name == "rejected.html":
        return _render_cards(
            "Rejected",
            context.get("drafts", []),
            "Read-only history of rejected drafts",
        )
    if template_name == "expired.html":
        return _render_cards(
            "Expired",
            context.get("drafts", []),
            "Read-only history of drafts that timed out",
        )
    if template_name == "calendar.html":
        manual_items = "".join(
            f"<article><h2>{item.get('workflow_name', '')}</h2><p>{item.get('content', '')}</p></article>"
            for item in context.get("manual_items", [])
        )
        automatic_items = "".join(
            f"<article><h2>{item.get('workflow_name', '')}</h2><p>{item.get('publish_label', '')}</p><p>{item.get('content', '')}</p></article>"
            for item in context.get("automatic_items", [])
        )
        return (
            "<h1>Calendar</h1>"
            "<h2>All-Day Manual</h2>"
            f"{manual_items}"
            "<h2>Timed Automatic</h2>"
            f"{automatic_items}"
        )
    if template_name == "automatic.html":
        workflows = "".join(
            (
                f"<article><h2>{item.get('workflow_name', '')}</h2>"
                f"<p>Next Trigger {item.get('next_trigger_label', '')}</p>"
                f"<p>Queued Drafts {item.get('queued_draft_count', 0)}</p>"
                f"<p>Pause Move to Manual</p></article>"
            )
            for item in context.get("workflows", [])
        )
        return "<h1>Automatic</h1>" f"{workflows}"
    if template_name == "brain.html":
        items = "".join(
            (
                f"<article><h2>{item.get('title', '')}</h2>"
                f"<p>{item.get('content', '')}</p>"
                f"<p>{item.get('bucket', '')}</p></article>"
            )
            for item in context.get("items", [])
        )
        return (
            "<h1>Brain / History</h1>"
            f"{items}"
        )
    if template_name == "trigger_feed.html":
        items = "".join(
            (
                f"<article><h2>{item.get('partner_slug', '')}</h2>"
                f"<p>{item.get('external_event_type', '')}</p>"
                f"<p>{item.get('workflow_slug', '')}</p></article>"
            )
            for item in context.get("items", [])
        )
        return (
            "<h1>Trigger Feed</h1>"
            f"{items}"
        )
    if template_name == "analytics.html":
        summary = context.get("summary", {})
        workflow_metrics = context.get("workflow_metrics", [])
        platform_metrics = context.get("platform_metrics", [])
        workflow_html = "".join(
            (
                f"<article><h2>{item.get('workflow_name', '')}</h2>"
                f"<p>{item.get('platform', '')}</p>"
                f"<p>{item.get('trigger_type', '')}</p>"
                f"<p>{item.get('record_count', 0)}</p></article>"
            )
            for item in workflow_metrics
        )
        platform_html = "".join(
            (
                f"<article><h2>{item.get('platform', '')}</h2>"
                f"<p>{item.get('promotion_confidence', 0)}</p></article>"
            )
            for item in platform_metrics
        )
        return (
            "<h1>Analytics</h1>"
            "<h2>Promotion confidence</h2>"
            f"<p>{summary.get('promotion_confidence', 0)}</p>"
            "<h2>Workflow health</h2>"
            f"{workflow_html}"
            "<h2>By platform</h2>"
            f"{platform_html}"
        )
    if template_name == "campaigns.html":
        items = "".join(
            (
                f"<article><h2>{item.get('name', '')}</h2>"
                f"<p>{item.get('slug', '')}</p>"
                f"<p>{item.get('objective', '')}</p>"
                f"<p>{item.get('audience', '')}</p>"
                f"<p>{item.get('theme', '')}</p></article>"
            )
            for item in context.get("campaigns", [])
        )
        return "<h1>Campaigns</h1>" + items
    if template_name == "competitors.html":
        sources = "".join(
            (
                f"<article><h2>{item.get('display_name', '')}</h2>"
                f"<p>{item.get('platform', '')}</p>"
                f"<p>{item.get('source_url', '')}</p></article>"
            )
            for item in context.get("sources", [])
        )
        signals = "".join(
            (
                f"<article><h2>{item.get('source_name', '')}</h2>"
                f"<p>{item.get('signal_type', '')}</p>"
                f"<p>{item.get('summary', '')}</p></article>"
            )
            for item in context.get("signals", [])
        )
        return f"<h1>Competitors</h1>{sources}{signals}"
    if template_name == "leads.html":
        leads = "".join(
            (
                f"<article><h2>{item.get('name', '')}</h2>"
                f"<p>{item.get('stage', '')}</p>"
                f"<p>{item.get('next_touchpoint', '')}</p></article>"
            )
            for item in context.get("leads", [])
        )
        tasks = "".join(
            (
                f"<article><h2>{item.get('lead_name', '')}</h2>"
                f"<p>{item.get('task_type', '')}</p>"
                f"<p>{item.get('summary', '')}</p></article>"
            )
            for item in context.get("tasks", [])
        )
        return f"<h1>Leads</h1>{leads}{tasks}"
    if template_name == "partners.html":
        partners = "".join(
            (
                f"<article><h2>{item.get('display_name', '')}</h2>"
                f"<p>{item.get('slug', '')}</p></article>"
            )
            for item in context.get("partners", [])
        )
        events = "".join(
            (
                f"<article><h2>{item.get('partner_name', '')}</h2>"
                f"<p>{item.get('event_type', '')}</p></article>"
            )
            for item in context.get("events", [])
        )
        bundles = "".join(
            (
                f"<article><h2>{item.get('partner_name', '')}</h2>"
                f"<p>{item.get('platform', '')}</p></article>"
            )
            for item in context.get("bundles", [])
        )
        return f"<h1>Partners</h1>{partners}{events}{bundles}"
    if template_name == "revenue.html":
        playbooks = "".join(
            (
                f"<article><h2>{item.get('name', '')}</h2>"
                f"<p>{item.get('playbook_type', '')}</p>"
                f"<p>{item.get('persona', '')}</p></article>"
            )
            for item in context.get("playbooks", [])
        )
        goals = "".join(
            (
                f"<article><h2>{item.get('name', '')}</h2>"
                f"<p>{item.get('metric_type', '')}</p></article>"
            )
            for item in context.get("conversion_goals", [])
        )
        return f"<h1>Revenue</h1>{playbooks}{goals}"
    if template_name == "settings.html":
        summary = context.get("summary", {})
        return (
            "<h1>Control Room Settings</h1>"
            f"<p>{summary.get('timezone', '')}</p>"
            f"<p>{'Session login required' if summary.get('auth_required') else 'Session login disabled'}</p>"
            "<button>Pause All Automatic Workflows</button>"
        )
    if template_name == "login.html":
        return "<h1>Control Room Login</h1>"
    if template_name == "partials/draft_panel.html":
        panel = context["panel"]
        compliance = panel.get("compliance_result", {})
        checks = " ".join(compliance.get("checks_run", []))
        return (
            "<h1>Why This Draft?</h1>"
            f"<p>{panel.get('workflow_name', '')}</p>"
            f"<p>{panel.get('trigger_label', '')}</p>"
            f"<p>{panel.get('trigger_reason', '')}</p>"
            f"<p>{checks}</p>"
        )
    if template_name == "partials/action_result.html":
        result = context["result"]
        return f"<div>{result.get('status_label', '')}</div><p>{result.get('message', '')}</p>"
    if template_name == "partials/campaign_run_result.html":
        result = context["result"]
        items = "".join(
            (
                f"<article><h2>{item.get('workflow_name', item.get('workflow_slug', ''))}</h2>"
                f"<p>{item.get('status', '')}</p>"
                f"<p>{item.get('summary', '')}</p></article>"
            )
            for item in result.get("workflow_runs", [])
        )
        return f"<h1>{result.get('campaign_slug', '')}</h1>{items}"
    if template_name == "partials/competitor_signal_result.html":
        result = context["result"]
        return (
            f"<div>{result.get('workflow_slug', '')}</div>"
            f"<p>{result.get('status', '')}</p>"
        )
    if template_name == "partials/lead_task_result.html":
        result = context["result"]
        return (
            f"<div>{result.get('workflow_slug', '')}</div>"
            f"<p>{result.get('status', '')}</p>"
        )
    if template_name == "partials/partner_event_result.html":
        result = context["result"]
        rows = "".join(
            f"<article><h2>{item.get('workflow_slug', '')}</h2><p>{item.get('status', '')}</p></article>"
            for item in result.get("results", [])
        )
        return f"<h1>{result.get('partner_slug', '')}</h1>{rows}"
    if template_name == "partials/partner_bundle_result.html":
        result = context["result"]
        return f"<div>{result.get('status', '')}</div><p>{result.get('message', '')}</p>"
    if template_name == "partials/revenue_run_result.html":
        result = context["result"]
        return (
            f"<div>{result.get('playbook_slug', '')}</div>"
            f"<p>{result.get('status', '')}</p>"
            f"<p>{result.get('sales_package_count', 0)}</p>"
        )
    if template_name == "partials/workflow_proposal.html":
        proposal = context["proposal"]
        workflow = proposal.get("workflow", {})
        changes = "".join(f"<li>{change}</li>" for change in proposal.get("changes", []))
        return (
            "<h1>Workflow Proposal</h1>"
            f"<p>{workflow.get('name', '')}</p>"
            f"<p>v{proposal.get('current_version')} to v{proposal.get('proposed_version')}</p>"
            f"<ul>{changes}</ul>"
        )
    page = context.get("page", "control-room")
    if template_name == "home.html":
        return (
            "<h1>Control Room</h1>"
            f"<p>Paused Workflows {context.get('paused_workflow_count', 0)}</p>"
            f"<p>Unhealthy Workflows {context.get('unhealthy_workflow_count', 0)}</p>"
            f"<p>Upcoming Auto (24h) {context.get('upcoming_auto_count', 0)}</p>"
        )
    return f"<h1>{page.title()}</h1>"


class _FallbackTemplates:
    def TemplateResponse(self, request: Request, template_name: str, context: dict[str, Any]) -> HTMLResponse:
        return HTMLResponse(_render_fallback_template(template_name, context))


templates = (
    Jinja2Templates(directory="app/web/templates")
    if Jinja2Templates is not None
    else _FallbackTemplates()
)


def _brain_sidebar_topics(db: Session) -> list[dict[str, str]]:
    """Return lightweight topic list for the brain sidebar nav."""
    try:
        rows = db.query(TopicProfile.topic_key, TopicProfile.display_name).order_by(TopicProfile.priority.asc()).all()
        return [{"key": r.topic_key, "name": r.display_name} for r in rows]
    except Exception:
        return []


def _safe_fetch(label: str, loader, fallback):
    try:
        return loader()
    except Exception as exc:
        logger.warning("Control-room %s unavailable: %s", label, exc)
        return fallback() if callable(fallback) else fallback


def _format_dt(value: datetime | None, fmt: str = "%b %d, %H:%M") -> str | None:
    if not value:
        return None
    return value.strftime(fmt)


def _format_iso_label(value: str | None, fmt: str = "%b %d, %H:%M") -> str | None:
    if not value:
        return None
    return _format_dt(datetime.fromisoformat(value), fmt)


def _build_trigger_meta(trigger: TriggerEvent | None, partner_source: PartnerSource | None = None) -> tuple[str, str, str]:
    if not trigger:
        return ("Unknown Trigger", "trigger-manual", "No trigger metadata recorded.")

    if trigger.trigger_type == TriggerType.CALENDAR:
        cron_expression = trigger.source_payload.get("cron_expression")
        if cron_expression:
            reason = f"Generated from recurring calendar rule ({cron_expression})."
        else:
            reason = "Generated from recurring calendar rule."
        return ("Calendar Trigger", "trigger-calendar", reason)

    if trigger.trigger_type == TriggerType.EXTERNAL:
        partner_label = partner_source.display_name if partner_source else "External source"
        event_label = trigger.external_event_type or trigger.source_payload.get("event_type") or "event"
        external_event_id = trigger.external_event_id or trigger.source_payload.get("external_event_id")
        reason = f"{partner_label} sent {event_label}"
        if external_event_id:
            reason += f" ({external_event_id})"
        return ("External Trigger", "trigger-external", reason)

    request_text = trigger.source_payload.get("request")
    if request_text:
        return ("Manual Request", "trigger-manual", request_text)
    return ("Manual Request", "trigger-manual", "Generated from an operator request.")


def _build_brain_trigger_meta(bq: BrainQuery, draft_id: uuid.UUID) -> tuple[str, str, str]:
    """Build trigger metadata from brain graph edges."""
    # Find job node → trigger node via edges
    job_edges = bq.get_edges_to(draft_id, relation="produced_draft")
    if not job_edges:
        return ("Unknown Trigger", "trigger-manual", "No trigger metadata recorded.")
    job_node = bq.get_knowledge_node(job_edges[0].source_id)
    if not job_node:
        return ("Unknown Trigger", "trigger-manual", "No trigger metadata recorded.")

    trigger_edges = bq.get_edges_to(job_node.id, relation="produced_job")
    if not trigger_edges:
        return ("Manual Request", "trigger-manual", "Generated from an operator request.")
    trigger_node = bq.get_knowledge_node(trigger_edges[0].source_id)
    if not trigger_node:
        return ("Manual Request", "trigger-manual", "Generated from an operator request.")

    tmeta = trigger_node.metadata_ or {}
    trigger_type = tmeta.get("trigger_type", "manual")

    if trigger_type == "calendar":
        cron = tmeta.get("cron_expression", "")
        reason = f"Generated from recurring calendar rule ({cron})." if cron else "Generated from recurring calendar rule."
        return ("Calendar Trigger", "trigger-calendar", reason)

    if trigger_type == "external":
        partner = tmeta.get("partner_name", "External source")
        event = tmeta.get("source_event_type", "event")
        event_id = tmeta.get("source_event_id", "")
        reason = f"{partner} sent {event}"
        if event_id:
            reason += f" ({event_id})"
        return ("External Trigger", "trigger-external", reason)

    request_text = tmeta.get("request", "")
    if request_text:
        return ("Manual Request", "trigger-manual", request_text)
    return ("Manual Request", "trigger-manual", "Generated from an operator request.")


def _serialize_brain_card(db: Session, draft: KnowledgeNode, history_action: str | None = None) -> dict[str, Any]:
    """Serialize a KnowledgeNode draft into a card dict for templates."""
    bq = BrainQuery(db)
    meta = draft.metadata_ or {}

    # Get linked workflow via edge
    workflow = bq.get_workflow_for_draft(draft.id)

    # Get review action notes from linked review_action knowledge nodes
    review_edges = bq.get_edges_from(draft.id, relation="reviewed_by")
    latest_note = None
    for edge in reversed(review_edges):
        review_node = bq.get_knowledge_node(edge.target_id)
        if review_node and (history_action is None or review_node.metadata_.get("action") == history_action):
            latest_note = review_node.metadata_.get("notes")
            break

    # Get assets — Asset.draft_variant_id holds the KnowledgeNode.id during transition
    try:
        assets = db.query(Asset).filter(Asset.draft_variant_id == draft.id).order_by(Asset.sort_order.asc()).all()
    except Exception:
        assets = []
    asset_list = [
        {
            "id": str(a.id),
            "url": a.url,
            "filename": a.filename,
            "asset_role": a.asset_role,
            "mime_type": a.mime_type,
            "render_status": a.render_status,
            "provider": a.provider,
            "platform_metadata": a.platform_metadata or {},
        }
        for a in assets
    ]

    # Build trigger meta from trigger knowledge node (follow produced_draft edge backward)
    trigger_label, trigger_class, trigger_reason = _build_brain_trigger_meta(bq, draft.id)

    return {
        "id": str(draft.id),
        "platform": meta.get("platform", "unknown"),
        "content": draft.content or "",
        "hashtags": meta.get("hashtags", []),
        "created_label": _format_dt(draft.created_at),
        "recommended_label": None,
        "scheduled_label": _format_iso_label(meta.get("valid_from_iso") or (draft.valid_from.isoformat() if draft.valid_from else None)),
        "expires_label": _format_iso_label(meta.get("valid_until_iso") or (draft.valid_until.isoformat() if draft.valid_until else None)),
        "published_label": _format_iso_label(meta.get("published_at")),
        "workflow_name": workflow.canonical_name if workflow else "Unknown Workflow",
        "workflow_slug": workflow.slug if workflow else "",
        "version_number": None,
        "trigger_label": trigger_label,
        "trigger_class": trigger_class,
        "trigger_reason": trigger_reason,
        "state": draft.status,
        "notes": latest_note,
        "failure_reason": meta.get("failure_reason"),
        "post_url": meta.get("post_url"),
        "compliance_result": meta.get("compliance_result") or {},
        "newsletter_subject": meta.get("compliance_result", {}).get("subject") if isinstance(meta.get("compliance_result"), dict) else None,
        "newsletter_preview_text": meta.get("compliance_result", {}).get("preview_text") if isinstance(meta.get("compliance_result"), dict) else None,
        "newsletter_segment": meta.get("compliance_result", {}).get("segment") if isinstance(meta.get("compliance_result"), dict) else None,
        "intent": meta.get("intent"),
        "assets": asset_list,
    }


def _get_assets(db: Session, draft_id: uuid.UUID) -> list[dict[str, Any]]:
    assets = (
        db.query(Asset)
        .filter(Asset.draft_variant_id == draft_id)
        .order_by(Asset.sort_order.asc(), Asset.created_at.asc())
        .all()
    )
    return [
        {
            "asset_type": asset.asset_type,
            "asset_role": asset.asset_role,
            "filename": asset.filename,
            "url": asset.url,
            "storage_path": asset.storage_path,
            "render_status": asset.render_status,
            "mime_type": asset.mime_type,
        }
        for asset in assets
    ]


def _load_related_context(
    db: Session,
    draft: DraftVariant,
) -> tuple[ContentJob | None, Workflow | None, WorkflowVersion | None, TriggerEvent | None, PartnerSource | None]:
    job = db.query(ContentJob).filter(ContentJob.id == draft.content_job_id).first()
    if not job:
        return None, None, None, None, None

    workflow = db.query(Workflow).filter(Workflow.id == job.workflow_id).first()
    version = db.query(WorkflowVersion).filter(WorkflowVersion.id == job.workflow_version_id).first()
    trigger = db.query(TriggerEvent).filter(TriggerEvent.id == job.trigger_event_id).first()
    partner_source = None
    if trigger and trigger.partner_source_id:
        partner_source = db.query(PartnerSource).filter(PartnerSource.id == trigger.partner_source_id).first()
    return job, workflow, version, trigger, partner_source


def _latest_action_note(db: Session, draft_id: uuid.UUID, action_type: ReviewActionType | None = None) -> str | None:
    query = db.query(ReviewAction).filter(ReviewAction.draft_variant_id == draft_id)
    if action_type:
        query = query.filter(ReviewAction.action == action_type)
    action = query.order_by(ReviewAction.created_at.desc()).first()
    return action.notes if action else None


def _serialize_card(
    db: Session,
    draft: DraftVariant,
    history_action: ReviewActionType | None = None,
) -> dict[str, Any]:
    job, workflow, version, trigger, partner_source = _load_related_context(db, draft)
    trigger_label, trigger_class, trigger_reason = _build_trigger_meta(trigger, partner_source)

    # Load associated image assets for this draft
    try:
        assets = (
            db.query(Asset)
            .filter(Asset.draft_variant_id == draft.id)
            .order_by(Asset.sort_order.asc())
            .all()
        )
    except Exception:
        assets = []

    asset_list = [
        {
            "id": str(a.id),
            "url": a.url,
            "filename": a.filename,
            "asset_role": a.asset_role,
            "mime_type": a.mime_type,
            "render_status": a.render_status,
            "provider": a.provider,
            "platform_metadata": a.platform_metadata or {},
        }
        for a in assets
    ]

    return {
        "id": str(draft.id),
        "platform": draft.platform.value,
        "content": draft.content,
        "hashtags": draft.hashtags or [],
        "created_label": _format_dt(draft.created_at),
        "recommended_label": _format_dt(draft.recommended_publish_at, "%H:%M"),
        "scheduled_label": _format_dt(draft.scheduled_publish_at),
        "expires_label": _format_dt(draft.expires_at),
        "published_label": _format_dt(draft.published_at),
        "workflow_name": workflow.name if workflow else "Unknown Workflow",
        "workflow_slug": workflow.slug if workflow else "",
        "version_number": version.version_number if version else None,
        "trigger_label": trigger_label,
        "trigger_class": trigger_class,
        "trigger_reason": trigger_reason,
        "state": draft.state.value,
        "notes": _latest_action_note(db, draft.id, history_action),
        "failure_reason": draft.failure_reason,
        "post_url": draft.post_url,
        "compliance_result": draft.compliance_result or {},
        "newsletter_subject": (draft.compliance_result or {}).get("subject"),
        "newsletter_preview_text": (draft.compliance_result or {}).get("preview_text"),
        "newsletter_segment": (draft.compliance_result or {}).get("segment"),
        "intent": (trigger.source_payload or {}).get("intent") if trigger else None,
        "assets": asset_list,
    }


def load_review_count(db: Session) -> int:
    try:
        return db.query(KnowledgeNode).filter(KnowledgeNode.kind == "draft", KnowledgeNode.status == "review_required").count()
    except Exception:
        return 0


def load_manual_cards(db: Session, limit: int = 50) -> list[dict[str, Any]]:
    drafts = BrainQuery(db).list_drafts_by_status("review_required", limit=limit)
    return [_serialize_brain_card(db, draft) for draft in drafts]


def load_automatic_cards(db: Session, limit: int = 50) -> list[dict[str, Any]]:
    drafts = (
        db.query(KnowledgeNode)
        .filter(KnowledgeNode.kind == "draft", KnowledgeNode.status == "scheduled")
        .order_by(KnowledgeNode.valid_from.asc(), KnowledgeNode.created_at.asc())
        .limit(limit)
        .all()
    )
    return [_serialize_brain_card(db, draft) for draft in drafts]


def load_automatic_workflow_cards(db: Session) -> list[dict[str, Any]]:
    cards = list_automatic_workflow_cards_service(db)
    workflows: list[dict[str, Any]] = []
    for card in cards:
        # The service now returns dicts directly — serialize any KnowledgeNode objects if present
        raw_drafts = card.get("drafts", [])
        drafts = []
        for d in raw_drafts:
            if isinstance(d, KnowledgeNode):
                drafts.append(_serialize_brain_card(db, d))
            elif isinstance(d, dict):
                drafts.append(d)
            else:
                try:
                    drafts.append(_serialize_card(db, d))
                except Exception:
                    pass
        workflows.append(
            {
                "workflow_id": card["workflow_id"],
                "workflow_name": card["workflow_name"],
                "workflow_slug": card.get("workflow_slug", ""),
                "platform": card["platform"],
                "mode": card["mode"],
                "timezone": card["timezone"],
                "health_status": card["health_status"],
                "paused_at": card.get("paused_at"),
                "next_trigger_label": _format_iso_label(card.get("next_trigger_at")),
                "publish_time_label": card.get("publish_time_label"),
                "last_success_label": _format_iso_label(card.get("last_success_at")),
                "last_error": card.get("last_error"),
                "queued_draft_count": card["queued_draft_count"],
                "drafts": drafts,
            }
        )
    return workflows


def load_home_summary(db: Session) -> dict[str, int]:
    scheduler_status = build_scheduler_status(db)
    bq = BrainQuery(db)
    return {
        "manual_count": db.query(KnowledgeNode).filter(KnowledgeNode.kind == "draft", KnowledgeNode.status == "review_required").count(),
        "auto_count": db.query(KnowledgeNode).filter(KnowledgeNode.kind == "draft", KnowledgeNode.status == "scheduled").count(),
        "published_count": db.query(KnowledgeNode).filter(KnowledgeNode.kind == "draft", KnowledgeNode.status == "active").count(),
        "rejected_count": db.query(KnowledgeNode).filter(KnowledgeNode.kind == "draft", KnowledgeNode.status == "rejected").count(),
        "expired_count": db.query(KnowledgeNode).filter(KnowledgeNode.kind == "draft", KnowledgeNode.status == "expired").count(),
        "failed_count": db.query(KnowledgeNode).filter(KnowledgeNode.kind == "draft", KnowledgeNode.status == "failed").count(),
        "trigger_count": db.query(KnowledgeNode).filter(KnowledgeNode.kind == "trigger").count(),
        "workflow_count": db.query(EntityNode).filter(EntityNode.entity_type == "workflow", EntityNode.status == "active").count(),
        "paused_workflow_count": scheduler_status["paused_workflows"],
        "unhealthy_workflow_count": scheduler_status["unhealthy_workflows"],
        "upcoming_auto_count": scheduler_status["upcoming_24h"],
    }


def load_today_activity(db: Session, limit: int = 20) -> dict[str, Any]:
    """Build a unified today-activity feed for the dashboard right column."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    bq = BrainQuery(db)

    # --- Draft KnowledgeNodes created today ---
    drafts = (
        db.query(KnowledgeNode)
        .filter(KnowledgeNode.kind == "draft", KnowledgeNode.created_at >= today_start)
        .order_by(KnowledgeNode.created_at.desc())
        .limit(limit)
        .all()
    )

    # --- Trigger KnowledgeNodes created today ---
    triggers = (
        db.query(KnowledgeNode)
        .filter(KnowledgeNode.kind == "trigger", KnowledgeNode.created_at >= today_start)
        .order_by(KnowledgeNode.created_at.desc())
        .limit(limit)
        .all()
    )

    # --- Map brain draft statuses to activity types ---
    _status_type_map = {
        "active": "published",
        "failed": "failed",
        "scheduled": "scheduled",
        "review_required": "pending",
        "pending": "pending",
        "rejected": "failed",
        "expired": "failed",
        "publishing": "scheduled",
    }

    _status_label_map = {
        "active": "Published",
        "failed": "Failed",
        "scheduled": "Scheduled",
        "review_required": "Awaiting review",
        "pending": "Draft generated",
        "rejected": "Rejected",
        "expired": "Expired",
        "publishing": "Publishing",
    }

    items: list[dict[str, Any]] = []

    for draft in drafts:
        meta = draft.metadata_ or {}
        workflow = bq.get_workflow_for_draft(draft.id)
        wf_name = workflow.canonical_name if workflow else "Unknown Workflow"
        platform = meta.get("platform", "unknown")
        status = draft.status or "pending"
        activity_type = _status_type_map.get(status, "pending")
        state_label = _status_label_map.get(status, status)
        title = f"{state_label} {platform} {wf_name}"
        detail = ""
        if status == "failed" and meta.get("failure_reason"):
            detail = meta.get("failure_reason", "")
        elif status == "rejected":
            detail = "Draft rejected"
        elif status == "expired":
            detail = "Draft expired without publishing"
        elif status == "scheduled" and draft.valid_from:
            detail = f"Scheduled for {draft.valid_from.strftime('%I:%M %p')}"

        # Determine trigger source type
        source = meta.get("trigger_type", "calendar")

        timestamp = None
        if meta.get("published_at"):
            try:
                timestamp = datetime.fromisoformat(meta["published_at"])
            except Exception:
                pass
        if timestamp is None:
            timestamp = draft.created_at

        items.append({
            "type": activity_type,
            "source": source,
            "title": title,
            "platform": platform,
            "time": timestamp.strftime("%-I:%M %p") if timestamp else "",
            "detail": detail,
            "sort_key": timestamp or now,
        })

    for trigger in triggers:
        tmeta = trigger.metadata_ or {}
        trigger_type = tmeta.get("trigger_type", "manual")
        wf_name = tmeta.get("workflow_name", "Unknown Workflow")
        if trigger_type == "external":
            partner_name = tmeta.get("partner_name", "External source")
            event_type = tmeta.get("source_event_type", "event")
            title = f"Trigger: {partner_name} {event_type}"
        elif trigger_type == "calendar":
            title = f"Calendar trigger fired for {wf_name}"
        else:
            title = f"Manual request for {wf_name}"
        items.append({
            "type": "triggered",
            "source": trigger_type,
            "title": title,
            "platform": "",
            "time": trigger.created_at.strftime("%-I:%M %p") if trigger.created_at else "",
            "detail": "",
            "sort_key": trigger.created_at or now,
        })

    # Sort combined list by time descending, limit to requested count
    items.sort(key=lambda x: x["sort_key"], reverse=True)
    items = items[:limit]

    # Remove sort_key from output
    for item in items:
        item.pop("sort_key", None)

    # Summary counts
    published_count = sum(1 for i in items if i["type"] == "published")
    scheduled_count = sum(1 for i in items if i["type"] == "scheduled")
    failed_count = sum(1 for i in items if i["type"] == "failed")
    triggered_count = sum(1 for i in items if i["type"] == "triggered")
    pending_count = sum(1 for i in items if i["type"] == "pending")

    return {
        "items": items,
        "total": len(items),
        "published_count": published_count,
        "scheduled_count": scheduled_count,
        "failed_count": failed_count,
        "triggered_count": triggered_count,
        "pending_count": pending_count,
    }


def load_trigger_feed_items(db: Session, limit: int = 50) -> list[dict[str, Any]]:
    items = TriggerEngine(db).list_events(limit=limit)
    return [
        {
            **item,
            "created_label": _format_dt(datetime.fromisoformat(item["created_at"])) if item.get("created_at") else None,
        }
        for item in items
    ]


def load_brain_results(
    db: Session,
    query: str = "",
    bucket: str | None = None,
    platform: str | None = None,
    workflow_slug: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    memory = MemoryRetrievalService(db)
    memory.sync_control_room_memory(limit=max(limit * 2, 100))
    platform_enum = None
    if platform:
        platform_enum = Platform(platform)
    items = memory.search(
        query=query,
        platform=platform_enum,
        bucket=bucket,  # pass raw string; search() handles it
        workflow_slug=workflow_slug,
        limit=limit,
    )
    summary = {
        "total": len(items),
        "approved": sum(1 for item in items if item.get("bucket") == "approved"),
        "rejected": sum(1 for item in items if item.get("bucket") == "rejected"),
        "expired": sum(1 for item in items if item.get("bucket") == "expired"),
    }
    return {
        "query": query,
        "items": items,
        "summary": summary,
    }


def load_analytics_summary(db: Session) -> dict[str, Any]:
    return AnalyticsService(db).build_summary()


def load_analytics_dashboard(
    db: Session,
    platform: str | None = None,
    workflow_slug: str | None = None,
    days: int = 30,
) -> dict[str, Any]:
    return build_analytics_summary(
        db,
        platform=platform,
        workflow_slug=workflow_slug,
        days=days,
    )


def load_campaign_rows(db: Session) -> list[dict[str, Any]]:
    return CampaignService(db).list_campaigns()


def run_campaign_from_web(db: Session, campaign_slug: str, actor: str = "planner") -> dict[str, Any]:
    return CampaignService(db).run_campaign_by_slug(campaign_slug, actor=actor)


def load_partner_dashboard(db: Session) -> dict[str, list[dict[str, Any]]]:
    intake = PartnerIntakeService(db)
    delivery = PartnerDeliveryService(db)
    return {
        "partners": intake.list_partners(),
        "events": intake.list_events(limit=30),
        "bundles": delivery.list_bundles(limit=30),
    }


def load_revenue_dashboard(db: Session) -> dict[str, list[dict[str, Any]]]:
    return RevenueService(db).list_dashboard()


def load_expansion_modules(db: Session) -> list[dict[str, Any]]:
    blog = _safe_fetch("blog dashboard", lambda: BlogService(db).list_dashboard(), lambda: {"counts": {"total": 0}})
    science = _safe_fetch("science dashboard", lambda: ScienceCredibilityService(db).list_dashboard(), lambda: {"counts": {"total": 0}})
    video = _safe_fetch("video dashboard", lambda: VideoContentService(db).list_dashboard(), lambda: {"count": 0})
    ugc = _safe_fetch(
        "ugc dashboard",
        lambda: UGCService(db).list_dashboard(),
        lambda: {"request_count": 0, "submission_count": 0},
    )
    repurposing = _safe_fetch(
        "repurposing dashboard",
        lambda: RepurposingService(db).list_dashboard(),
        lambda: {"sources": [], "derivatives": [], "runs": []},
    )
    sports = _safe_fetch("sports dashboard", lambda: SportsCalendarService(db).list_dashboard(), lambda: {"windows": [], "stage_runs": []})

    blog_counts = blog.get("counts", {})
    science_counts = science.get("counts", {})
    rep_sources = repurposing.get("sources", [])
    rep_derivatives = repurposing.get("derivatives", [])
    sport_windows = sports.get("windows", [])

    return [
        {
            "slug": "blog",
            "title": "Blog & SEO",
            "count_label": f"{blog_counts.get('total', 0)} articles",
            "href": "/control-room/blog",
            "section_ref": "\u00a711.2",
            "purpose": (
                "Own the search results. When a D1 coach googles "
                "\u201cmental performance assessment for athletes\u201d or "
                "\u201cclutch factor testing,\u201d NTangible should own that result. "
                "2\u20134 SEO-optimized posts per month, 800\u20131,200 words each."
            ),
            "stats": {
                "draft": blog_counts.get("review_ready", 0),
                "published": blog_counts.get("published", 0),
                "failed": blog_counts.get("failed", 0),
            },
        },
        {
            "slug": "science",
            "title": "Science Credibility",
            "count_label": f"{science_counts.get('total', 0)} records",
            "href": "/control-room/science",
            "section_ref": "\u00a711.1",
            "purpose": (
                "Proactive defense, not reactive. Competitors like Scorability ($40M raised) "
                "occupy mindshare. Advisor spotlights, white paper excerpts, and dataset "
                "credibility posts establish validated methodology before credibility is challenged."
            ),
            "stats": {
                "spotlights": science_counts.get("advisor_spotlights", 0),
                "excerpts": science_counts.get("white_paper_excerpts", 0),
                "milestones": science_counts.get("peer_review_milestones", 0),
            },
        },
        {
            "slug": "video",
            "title": "Video Content",
            "count_label": f"{video.get('count', 0)} briefs",
            "href": "/control-room/video",
            "section_ref": "\u00a711.4",
            "purpose": (
                "~10% of content volume. High-impact moments only \u2014 partnership "
                "announcements, conference recaps, milestone celebrations. The engine "
                "generates the script (hook, talking points, CTA); Dan records. No editing "
                "required beyond basic trim."
            ),
            "stats": {
                "scripted": video.get("count", 0),
            },
        },
        {
            "slug": "ugc",
            "title": "UGC & Testimonials",
            "count_label": f"{ugc.get('request_count', 0)} requests / {ugc.get('submission_count', 0)} submissions",
            "href": "/control-room/ugc",
            "section_ref": "\u00a711.5",
            "purpose": (
                "The most powerful version isn\u2019t NTangible posting about athletes \u2014 "
                "it\u2019s athletes posting about themselves. Athletes scoring 750+ CF get "
                "automated testimonial requests. One submission creates 3\u20135 content pieces "
                "at zero production cost."
            ),
            "stats": {
                "sent": ugc.get("request_count", 0),
                "received": ugc.get("submission_count", 0),
            },
        },
        {
            "slug": "repurposing",
            "title": "Content Repurposing",
            "count_label": f"{len(rep_derivatives)} derivatives",
            "href": "/control-room/repurposing",
            "section_ref": "\u00a711.8",
            "purpose": (
                "The highest-leverage move in the system. One content nucleus (e.g., a LinkedIn "
                "post) automatically becomes an X thread, single tweet, IG caption, blog expansion, "
                "newsletter excerpt, and email snippet. Posts scoring 75+ are auto-queued. "
                "Dan\u2019s input gets amplified 5\u201310x without additional effort."
            ),
            "stats": {
                "sources": len(rep_sources),
                "derivatives": len(rep_derivatives),
                "ratio": f"{len(rep_derivatives) / len(rep_sources):.1f}x" if rep_sources else "0x",
            },
        },
        {
            "slug": "sports",
            "title": "Sports Calendar",
            "count_label": f"{len(sport_windows)} windows",
            "href": "/control-room/sports",
            "section_ref": "\u00a711.6",
            "purpose": (
                "The sports calendar drives everything. Content not mapped to the calendar feels "
                "disconnected. Pre-loaded macro windows \u2014 combine season, transfer portal, "
                "draft week, testing windows \u2014 auto-stage content templates so the engine is "
                "ready when moments hit."
            ),
            "stats": {
                "windows": len(sport_windows),
                "stage runs": len(sports.get("stage_runs", [])),
            },
        },
    ]


def ingest_partner_event_from_web(db: Session, partner_slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    return PartnerIntakeService(db).ingest_webhook(partner_slug, payload)


def update_partner_bundle_from_web(db: Session, bundle_id: str, status: str = "delivered") -> dict[str, Any]:
    return PartnerDeliveryService(db).update_bundle_status(uuid.UUID(bundle_id), status)


def run_revenue_playbook_from_web(
    db: Session,
    playbook_slug: str,
    *,
    actor: str = "sales",
    source_kind: str = "manual",
    source_id: str = "manual-run",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return RevenueService(db).run_playbook_by_slug(
        playbook_slug,
        actor=actor,
        source_kind=source_kind,
        source_id=source_id,
        context=context or {},
    )


def load_competitor_dashboard(db: Session) -> dict[str, list[dict[str, Any]]]:
    return CompetitorService(db).list_dashboard()


def respond_to_competitor_signal_from_web(
    db: Session,
    signal_id: str,
    platform: str = "linkedin",
    actor: str = "analyst",
) -> dict[str, Any]:
    return CompetitorService(db).create_response_trigger(
        uuid.UUID(signal_id),
        platform=platform,
        actor=actor,
    )


def load_lead_dashboard(db: Session) -> dict[str, list[dict[str, Any]]]:
    return LeadNurtureService(db).list_dashboard()


def generate_lead_content_from_web(
    db: Session,
    lead_id: str,
    platform: str = "linkedin",
    actor: str = "sales",
) -> dict[str, Any]:
    return LeadNurtureService(db).generate_content(
        uuid.UUID(lead_id),
        platform=platform,
        actor=actor,
    )


def _default_analytics_summary(days: int) -> dict[str, Any]:
    return {
        "window_days": days,
        "record_count": 0,
        "workflow_count": 0,
        "engagement_percentile": 0.0,
        "approval_rate": 0.0,
        "average_content_score": 0.0,
        "recycle_candidate_count": 0,
        "promotion_confidence": 0.0,
        "promotion_recommendation": "manual_only",
    }


def _empty_weekly_digest() -> dict[str, Any]:
    return {
        "total_posts": 0,
        "avg_score": 0.0,
        "period_start": None,
        "period_end": None,
        "recommendations": [],
        "top_performers": [],
        "underperformers": [],
        "platform_breakdown": [],
        "intent_split": {},
    }


def _load_recent_published_posts(
    db: Session,
    *,
    platform: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    from app.models.content_brain import ContentBrainAsset, ContentBrainItem, ContentPlatform

    brain_platform_map = {
        "linkedin": ContentPlatform.LINKEDIN,
        "instagram": ContentPlatform.INSTAGRAM,
        "x": ContentPlatform.OTHER,
        "newsletter": ContentPlatform.WEB,
    }
    brain_platform = brain_platform_map.get(platform)

    posts: list[dict[str, Any]] = []
    bq = BrainQuery(db)

    brain_q = db.query(ContentBrainItem).filter(
        ContentBrainItem.item_type.in_(["post", "reel", "video", "article", "social_post"])
    )
    if brain_platform is not None:
        brain_q = brain_q.filter(ContentBrainItem.platform == brain_platform)
    brain_items = (
        brain_q.order_by(
            ContentBrainItem.published_at.desc().nullslast(),
            ContentBrainItem.created_at.desc(),
        )
        .limit(limit)
        .all()
    )

    item_ids = [item.id for item in brain_items]
    image_urls: dict[str, str] = {}
    if item_ids:
        for asset in db.query(ContentBrainAsset).filter(
            ContentBrainAsset.content_item_id.in_(item_ids),
            ContentBrainAsset.asset_type == "image",
        ).all():
            key = str(asset.content_item_id)
            if key not in image_urls:
                image_urls[key] = asset.url

    for item in brain_items:
        published_at = item.published_at or item.created_at
        sort_key = published_at.isoformat() if published_at else ""
        text = item.body_text or item.summary or item.title or ""
        preview = (text[:180] + "...") if len(text) > 180 else text
        item_platform = item.platform.value if item.platform else (platform or "unknown")
        posts.append(
            {
                "id": str(item.id),
                "platform": item_platform,
                "workflow_name": item_platform.replace("_", " ").title(),
                "published_at": sort_key,
                "content_preview": preview,
                "impressions": 0,
                "engagement_rate": 0.0,
                "content_score": 0.0,
                "recycle": False,
                "image_url": image_urls.get(str(item.id), ""),
                "_sort_key": sort_key,
            }
        )

    published_nodes = bq.list_drafts_by_status("active", limit=limit, platform=platform)
    for node in published_nodes:
        metadata = node.metadata_ or {}
        workflow = bq.get_workflow_for_draft(node.id)
        published_at = metadata.get("published_at") or (
            node.updated_at.isoformat() if node.updated_at else ""
        )
        node_platform = metadata.get("platform")
        if not node_platform and workflow is not None and getattr(workflow, "platform", None):
            node_platform = workflow.platform.value
        node_platform = node_platform or platform or "unknown"
        workflow_name = "Unknown Workflow"
        if workflow is not None:
            workflow_name = getattr(workflow, "canonical_name", None) or getattr(workflow, "name", workflow_name)
        posts.append(
            {
                "id": str(node.id),
                "platform": node_platform,
                "workflow_name": workflow_name,
                "published_at": published_at,
                "content_preview": (node.content[:180] + "...") if node.content and len(node.content) > 180 else (node.content or ""),
                "impressions": 0,
                "engagement_rate": 0.0,
                "content_score": float(metadata.get("content_score") or 0.0),
                "recycle": bool(metadata.get("recycle_recommended")),
                "_sort_key": published_at,
            }
        )

    posts.sort(key=lambda item: item.get("_sort_key", ""), reverse=True)
    for post in posts:
        post.pop("_sort_key", None)
    return posts[:limit]


def load_settings_summary(db: Session | None = None) -> dict[str, Any]:
    settings = get_settings()
    scheduler_status = build_scheduler_status(db) if db is not None else {
        "paused_workflows": 0,
        "unhealthy_workflows": 0,
        "upcoming_24h": 0,
        "due_rules": 0,
        "due_drafts": 0,
    }
    return {
        "timezone": settings.control_room_default_timezone,
        "auth_required": settings.control_room_require_auth,
        "scheduler_status": scheduler_status,
        "publishers": {
            "x": settings.x_publisher,
            "linkedin": settings.linkedin_publisher,
            "instagram": settings.instagram_publisher,
            "newsletter": settings.newsletter_publisher,
        },
        "canva": {
            "renderer": settings.canva_renderer,
            "has_api_key": bool(settings.canva_api_key),
            "brand_template_set": settings.canva_brand_template_set,
        },
        "connections": (
            PublishingConnectionService(db).list_connection_summaries()
            if db is not None
            else []
        ),
        "legacy_mode_note": "Legacy X, LinkedIn, Instagram, and content-brain APIs remain compatibility paths.",
    }


def _workflow_create_error_response(message: str) -> RedirectResponse:
    return RedirectResponse(
        url=f"/control-room/workflows?error={quote(message)}",
        status_code=303,
    )


def load_workflow_detail(db: Session, workflow_slug: str) -> dict[str, Any]:
    detail = WorkflowEditor(db).get_workflow_detail(workflow_slug)
    return {
        "workflow": detail["workflow"],
        "active_version": detail["active_version"],
        "versions": detail["versions"],
        "approved_examples": detail["approved_examples"],
        "rejected_examples": detail["rejected_examples"],
    }


def load_history_cards(db: Session, state: DraftState, limit: int = 50) -> list[dict[str, Any]]:
    # Map old DraftState to brain status
    _state_to_brain_status = {
        DraftState.REJECTED: "rejected",
        DraftState.EXPIRED: "expired",
        DraftState.PUBLISHED: "active",
        DraftState.FAILED: "failed",
    }
    _state_to_history_action = {
        DraftState.REJECTED: "reject",
        DraftState.EXPIRED: "expire",
    }
    brain_status = _state_to_brain_status.get(state)
    history_action = _state_to_history_action.get(state)
    if brain_status:
        drafts = (
            db.query(KnowledgeNode)
            .filter(KnowledgeNode.kind == "draft", KnowledgeNode.status == brain_status)
            .order_by(KnowledgeNode.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_serialize_brain_card(db, draft, history_action=history_action) for draft in drafts]
    # Fallback: old model
    old_history_action = {
        DraftState.REJECTED: ReviewActionType.REJECT,
        DraftState.EXPIRED: ReviewActionType.EXPIRE,
    }.get(state)
    drafts = (
        db.query(DraftVariant)
        .filter(DraftVariant.state == state)
        .order_by(DraftVariant.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_serialize_card(db, draft, history_action=old_history_action) for draft in drafts]


def load_calendar_items(db: Session) -> dict[str, Any]:
    from data.sports_calendar import rolling_calendar_days
    from datetime import date as _date, timedelta as _timedelta
    import calendar as _cal_mod

    today = _date.today()

    # Pull all active draft KnowledgeNodes (review_required + scheduled + active)
    all_drafts = (
        db.query(KnowledgeNode)
        .filter(
            KnowledgeNode.kind == "draft",
            KnowledgeNode.status.in_(["review_required", "scheduled", "active"]),
        )
        .order_by(KnowledgeNode.created_at.desc())
        .limit(200)
        .all()
    )
    bq_cal = BrainQuery(db)

    # Build a date -> drafts map
    drafts_by_date: dict[str, list[dict[str, Any]]] = {}
    for draft in all_drafts:
        meta = draft.metadata_ or {}
        draft_date = None
        if draft.valid_from:
            draft_date = draft.valid_from.date().isoformat()
        elif draft.created_at:
            draft_date = draft.created_at.date().isoformat()
        else:
            draft_date = today.isoformat()
        workflow = bq_cal.get_workflow_for_draft(draft.id)
        wf_name = workflow.canonical_name if workflow else "Unknown Workflow"
        platform = meta.get("platform", "unknown")
        status = draft.status or "pending"
        drafts_by_date.setdefault(draft_date, []).append({
            "id": str(draft.id),
            "workflow_name": wf_name,
            "platform": platform,
            "state": status,
            "content": draft.content or "",
            "time_label": draft.valid_from.strftime("%H:%M") if draft.valid_from else None,
            "kind": "timed" if draft.valid_from else "manual",
            "intent": meta.get("intent", "brand"),
        })

    # Get sports calendar windows for 60 days
    sports_days = rolling_calendar_days(60, anchor=today - _timedelta(days=today.weekday()))
    sports_by_date: dict[str, list[dict[str, Any]]] = {}
    for sd in sports_days:
        if sd["windows"]:
            sports_by_date[sd["date"]] = [
                {
                    "title": w["title"],
                    "sport": w["sport"],
                    "kind": "sports",
                    "window_type": w["window_type"],
                    "platforms": w.get("default_platforms", []),
                }
                for w in sd["windows"]
            ]

    # Build month calendar grid (current month)
    year, month = today.year, today.month
    first_weekday, days_in_month = _cal_mod.monthrange(year, month)
    # Adjust to Monday start (calendar module uses Monday=0)
    month_start = _date(year, month, 1)
    # Pad start to Monday
    pad_before = month_start.weekday()  # 0=Monday
    grid_start = month_start - _timedelta(days=pad_before)
    # Build 6 weeks (42 days) to cover any month
    month_days = []
    for i in range(42):
        d = grid_start + _timedelta(days=i)
        d_iso = d.isoformat()
        day_drafts = drafts_by_date.get(d_iso, [])
        day_sports = sports_by_date.get(d_iso, [])
        items = day_sports + day_drafts
        month_days.append({
            "date": d_iso,
            "day": d.day,
            "weekday": d.strftime("%a"),
            "label": d.strftime("%b %d"),
            "is_today": d == today,
            "is_current_month": d.month == month,
            "is_weekend": d.weekday() >= 5,
            "items": items,
            "item_count": len(items),
        })

    # Build week view (current week, Mon-Sun)
    week_start = today - _timedelta(days=today.weekday())
    week_days = []
    for i in range(7):
        d = week_start + _timedelta(days=i)
        d_iso = d.isoformat()
        day_drafts = drafts_by_date.get(d_iso, [])
        day_sports = sports_by_date.get(d_iso, [])
        items = day_sports + day_drafts
        week_days.append({
            "date": d_iso,
            "day": d.day,
            "weekday": d.strftime("%a"),
            "label": d.strftime("%b %d"),
            "full_label": d.strftime("%A, %B %d"),
            "is_today": d == today,
            "is_weekend": d.weekday() >= 5,
            "items": items,
            "item_count": len(items),
        })

    # Legacy items for backward compat
    manual_items = [
        d for drafts in drafts_by_date.values() for d in drafts
        if d["kind"] == "manual"
    ][:20]
    automatic_items = [
        d for drafts in drafts_by_date.values() for d in drafts
        if d["kind"] == "timed"
    ][:20]

    return {
        "month_days": month_days,
        "week_days": week_days,
        "month_label": today.strftime("%B %Y"),
        "week_label": f"{week_start.strftime('%b %d')} – {(week_start + _timedelta(days=6)).strftime('%b %d, %Y')}",
        "today": today.isoformat(),
        "manual_items": manual_items,
        "automatic_items": automatic_items,
    }


def _workflow_name_for_draft(db: Session, draft: DraftVariant) -> str:
    if draft.content_job_id:
        job = db.query(ContentJob).filter(ContentJob.id == draft.content_job_id).first()
        if job and job.workflow_id:
            wf = db.query(Workflow).filter(Workflow.id == job.workflow_id).first()
            if wf:
                return wf.name
    return "Unknown Workflow"


def load_draft_panel(db: Session, incoming_draft_id: str, focus: str = "why") -> dict[str, Any] | None:
    draft_id = uuid.UUID(incoming_draft_id)
    bq = BrainQuery(db)

    # Try brain model first
    draft = bq.get_knowledge_node(draft_id)
    if draft and draft.kind == "draft":
        meta = draft.metadata_ or {}
        workflow = bq.get_workflow_for_draft(draft.id)
        trigger_label, _, trigger_reason = _build_brain_trigger_meta(bq, draft.id)
        return {
            "id": str(draft.id),
            "content": draft.content or "",
            "hashtags": meta.get("hashtags", []),
            "platform": meta.get("platform", "unknown"),
            "workflow_name": workflow.canonical_name if workflow else "Unknown Workflow",
            "workflow_slug": workflow.slug if workflow else "",
            "version_number": None,
            "version_note": None,
            "trigger_label": trigger_label,
            "trigger_reason": trigger_reason,
            "trigger_payload": {},
            "compliance_result": meta.get("compliance_result") or {},
            "prompt_snapshot": meta.get("prompt_snapshot") or {},
            "asset_items": _get_assets(db, draft.id),
            "focus": focus,
        }

    # Fallback to old model
    old_draft = db.query(DraftVariant).filter(DraftVariant.id == draft_id).first()
    if not old_draft:
        return None

    job, workflow, version, trigger, partner_source = _load_related_context(db, old_draft)
    trigger_label, _, trigger_reason = _build_trigger_meta(trigger, partner_source)

    return {
        "id": str(old_draft.id),
        "content": old_draft.content,
        "hashtags": old_draft.hashtags or [],
        "platform": old_draft.platform.value,
        "workflow_name": workflow.name if workflow else "Unknown Workflow",
        "workflow_slug": workflow.slug if workflow else "",
        "version_number": version.version_number if version else None,
        "version_note": version.version_note if version else None,
        "trigger_label": trigger_label,
        "trigger_reason": trigger_reason,
        "trigger_payload": trigger.source_payload if trigger else {},
        "compliance_result": old_draft.compliance_result or {},
        "prompt_snapshot": job.prompt_snapshot if job else {},
        "asset_items": _get_assets(db, old_draft.id),
        "focus": focus,
    }


def apply_web_action(
    db: Session,
    incoming_draft_id: str,
    action: str,
    actor: str,
    notes: str | None = None,
    scheduled_at_raw: str | None = None,
) -> dict[str, str]:
    valid_actions = {"post_now", "schedule", "reject", "pause", "move_to_manual"}
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    scheduled_at = None
    if scheduled_at_raw:
        scheduled_at = datetime.fromisoformat(scheduled_at_raw)

    queue = ReviewQueue(db)
    try:
        draft = queue.act(
            draft_id=uuid.UUID(incoming_draft_id),
            action=action,
            actor=actor,
            notes=notes,
            scheduled_at=scheduled_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    db.commit()

    if action == "post_now":
        meta = draft.metadata_ or {} if isinstance(draft, KnowledgeNode) else {}
        if isinstance(draft, KnowledgeNode):
            published = draft.status == "active"
            post_url = meta.get("post_url")
            failure_reason = meta.get("failure_reason")
        else:
            published = draft.state == DraftState.PUBLISHED
            post_url = getattr(draft, "post_url", None)
            failure_reason = getattr(draft, "failure_reason", None)
        if published:
            message = "Draft published successfully."
            if post_url:
                message += f" {post_url}"
            return {"id": str(draft.id), "status_label": "Posted", "status_class": "badge-success", "message": message}
        return {"id": str(draft.id), "status_label": "Failed", "status_class": "badge-danger", "message": failure_reason or "Draft failed to publish."}

    if action == "schedule":
        if isinstance(draft, KnowledgeNode):
            scheduled_label = _format_iso_label(draft.valid_from.isoformat() if draft.valid_from else None)
        else:
            scheduled_label = _format_dt(getattr(draft, "scheduled_publish_at", None))
        return {
            "id": str(draft.id),
            "status_label": "Scheduled",
            "status_class": "badge-info",
            "message": f"Draft scheduled for {scheduled_label}.",
        }

    if action == "pause":
        return {
            "id": str(draft.id),
            "status_label": "Paused",
            "status_class": "badge-warning",
            "message": "Automatic draft moved back to the manual queue.",
        }

    if action == "move_to_manual":
        return {
            "id": str(draft.id),
            "status_label": "Manual",
            "status_class": "badge-info",
            "message": "Automatic draft moved to manual review.",
        }

    return {
        "id": str(draft.id),
        "status_label": "Rejected",
        "status_class": "badge-danger",
        "message": "Draft moved to rejected history.",
    }


def apply_workflow_web_action(
    db: Session,
    workflow_id: str,
    action: str,
    actor: str,
) -> dict[str, str]:
    try:
        if action == "pause":
            workflow = set_workflow_pause_state(db, workflow_id, paused=True)
            message = "Automatic workflow paused."
            status_label = "Paused"
            status_class = "badge-warning"
        elif action == "resume":
            workflow = set_workflow_pause_state(db, workflow_id, paused=False)
            message = "Automatic workflow resumed."
            status_label = "Running"
            status_class = "badge-success"
        elif action == "move_to_manual":
            workflow = move_workflow_to_manual(db, workflow_id)
            message = "Workflow moved to manual review."
            status_label = "Manual"
            status_class = "badge-info"
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    db.commit()
    return {
        "id": str(workflow.id),
        "status_label": status_label,
        "status_class": status_class,
        "message": message,
    }


def apply_settings_action(db: Session, action: str) -> dict[str, str]:
    if action == "pause_all":
        count = pause_all_workflows(db)
        message = f"Paused {count} automatic workflows."
    elif action == "resume_all":
        count = resume_all_workflows(db)
        message = f"Resumed {count} automatic workflows."
    else:
        raise HTTPException(status_code=400, detail=f"Unknown settings action: {action}")
    db.commit()
    return {
        "id": action,
        "status_label": "Updated",
        "status_class": "badge-info",
        "message": message,
    }


def _parse_json_field(raw_value: str) -> dict[str, Any]:
    raw_value = (raw_value or "").strip()
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="JSON payload must be an object")
    return parsed


@web_router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    summary = _safe_fetch(
        "home summary",
        lambda: load_home_summary(db),
        lambda: {
            "manual_count": 0,
            "auto_count": 0,
            "published_count": 0,
            "rejected_count": 0,
            "expired_count": 0,
            "failed_count": 0,
            "trigger_count": 0,
            "workflow_count": 0,
            "paused_workflow_count": 0,
            "unhealthy_workflow_count": 0,
            "upcoming_auto_count": 0,
        },
    )
    manual_drafts = _safe_fetch("manual cards", lambda: load_manual_cards(db), lambda: [])
    scheduled_drafts = _safe_fetch("automatic cards", lambda: load_automatic_cards(db), lambda: [])
    today_activity = _safe_fetch(
        "today activity",
        lambda: load_today_activity(db),
        lambda: {"items": [], "total": 0, "published_count": 0, "scheduled_count": 0, "failed_count": 0, "triggered_count": 0, "pending_count": 0},
    )
    workflows = _safe_fetch(
        "workflows for generate",
        lambda: db.query(Workflow).filter(Workflow.enabled == True).order_by(Workflow.name).all(),
        lambda: [],
    )

    today_label = datetime.now().strftime("%A, %B %-d, %Y")

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "page": "dashboard",
            "review_count": summary.get("manual_count", 0),
            "today_date": today_label,
            "manual_drafts": manual_drafts,
            "scheduled_drafts": scheduled_drafts,
            "today_activity": today_activity,
            **summary,
        },
    )


@web_router.post("/generate", response_class=HTMLResponse)
async def generate_content_fragment(
    request: Request,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    workflow_id_raw = form_data.get("workflow_id", [""])[0]
    request_text = form_data.get("request_text", [""])[0] or "Generate content"

    if not workflow_id_raw:
        return HTMLResponse(
            '<div class="alert alert-error">Please select a workflow.</div>'
        )

    try:
        wf_id = uuid.UUID(workflow_id_raw)
    except ValueError:
        return HTMLResponse(
            '<div class="alert alert-error">Invalid workflow ID.</div>'
        )

    try:
        trigger = TriggerEngine(db).create_manual_request(
            request_text=request_text,
            workflow_id=wf_id,
        )
        db.flush()

        job = WorkflowEngine(db).execute(trigger)
        db.commit()

        if job.status == "failed":
            error_msg = job.error_message or "Generation failed"
            return HTMLResponse(
                f'<div class="alert alert-error">Generation failed: {error_msg}</div>'
            )

        return HTMLResponse(
            '<div class="alert alert-success">'
            "Draft generated successfully! It should appear in the Needs Review section."
            "</div>"
        )
    except ValueError as exc:
        db.rollback()
        return HTMLResponse(
            f'<div class="alert alert-error">Validation error: {exc}</div>'
        )
    except Exception as exc:
        db.rollback()
        logger.error("Content generation failed: %s", exc)
        return HTMLResponse(
            f'<div class="alert alert-error">Something went wrong: {exc}</div>'
        )


@web_router.get("/manual")
def manual_view(request: Request, db: Session = Depends(get_db)):
    drafts = _safe_fetch("manual cards", lambda: load_manual_cards(db), lambda: [])
    return templates.TemplateResponse(
        request,
        "manual.html",
        {
            "page": "manual",
            "review_count": load_review_count(db),
            "drafts": drafts,
        },
    )


@web_router.post("/drafts/{draft_id}/action", response_class=HTMLResponse)
async def draft_action_fragment(
    request: Request,
    draft_id: str,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    action = form_data.get("action", [""])[0]
    actor = form_data.get("actor", ["admin"])[0]
    notes = form_data.get("notes", [None])[0]
    scheduled_at = form_data.get("scheduled_at", [None])[0]

    result = apply_web_action(
        db=db,
        incoming_draft_id=draft_id,
        action=action,
        actor=actor,
        notes=notes,
        scheduled_at_raw=scheduled_at,
    )
    return templates.TemplateResponse(
        request,
        "partials/action_result.html",
        {"result": result},
    )


@web_router.post("/workflows/{workflow_id}/action", response_class=HTMLResponse)
async def workflow_action_fragment(
    request: Request,
    workflow_id: str,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    action = form_data.get("action", [""])[0]
    actor = form_data.get("actor", ["admin"])[0]

    result = apply_workflow_web_action(
        db=db,
        workflow_id=workflow_id,
        action=action,
        actor=actor,
    )
    return templates.TemplateResponse(
        request,
        "partials/action_result.html",
        {"result": result},
    )


@web_router.get("/drafts/{draft_id}/panel", response_class=HTMLResponse)
def draft_panel(
    request: Request,
    draft_id: str,
    focus: str = "why",
    db: Session = Depends(get_db),
):
    panel = load_draft_panel(db, draft_id, focus=focus)
    if not panel:
        raise HTTPException(status_code=404, detail="Draft not found")
    return templates.TemplateResponse(
        request,
        "partials/draft_panel.html",
        {"panel": panel},
    )


@web_router.get("/automatic")
def automatic_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "automatic.html",
        {
            "page": "automatic",
            "workflows": load_automatic_workflow_cards(db),
        },
    )


@web_router.get("/rejected")
def rejected_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "rejected.html",
        {
            "page": "rejected",
            "drafts": load_history_cards(db, DraftState.REJECTED),
        },
    )


@web_router.get("/expired")
def expired_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "expired.html",
        {
            "page": "expired",
            "drafts": load_history_cards(db, DraftState.EXPIRED),
        },
    )


def load_calendar_view_data(db: Session, anchor_date: date | None = None) -> dict[str, Any]:
    """Build all data needed for the Google Calendar-style view."""
    from datetime import date as _date, timedelta as _td
    import calendar as _cal_mod

    today = _date.today()
    anchor = anchor_date or today

    # ---------- month grid (6 weeks = 42 days) ----------
    year, month = anchor.year, anchor.month
    _, days_in_month = _cal_mod.monthrange(year, month)
    month_start = _date(year, month, 1)
    pad_before = month_start.weekday()  # 0=Monday
    grid_start = month_start - _td(days=pad_before)
    grid_end = grid_start + _td(days=42)

    # ---------- week grid ----------
    week_start = anchor - _td(days=anchor.weekday())
    week_end = week_start + _td(days=7)

    # ---------- collect all items in the widest range ----------
    range_start = min(grid_start, week_start, anchor)
    range_end = max(grid_end, week_end, anchor + _td(days=1))

    # Recurring calendar rules
    all_workflows = {str(wf.id): wf for wf in db.query(Workflow).all()}
    rules = db.query(CalendarRule).filter(CalendarRule.enabled.is_(True)).all()
    items_by_date: dict[str, list[dict[str, Any]]] = {}

    for rule in rules:
        wf = all_workflows.get(str(rule.workflow_id))
        wf_name = wf.name if wf else "Unknown Workflow"
        wf_platform = wf.platform.value if wf and wf.platform else "x"
        fire_dates = _cron_fire_dates(rule.cron_expression, rule.timezone, range_start, (range_end - range_start).days)
        for dt in fire_dates:
            day_key = dt.strftime("%Y-%m-%d")
            items_by_date.setdefault(day_key, []).append({
                "type": "rule",
                "platform": wf_platform,
                "title": wf_name,
                "time": dt.strftime("%H:%M"),
                "time_label": dt.strftime("%I:%M %p").lstrip("0"),
                "status": "recurring",
                "detail": _cron_human_label(rule.cron_expression),
                "content": "",
            })

    # Scheduled / published drafts from KnowledgeNodes
    bq_cal_view = BrainQuery(db)
    drafts = (
        db.query(KnowledgeNode)
        .filter(
            KnowledgeNode.kind == "draft",
            KnowledgeNode.status.in_(["review_required", "scheduled", "active"]),
        )
        .order_by(KnowledgeNode.created_at.desc())
        .limit(500)
        .all()
    )
    for draft in drafts:
        meta = draft.metadata_ or {}
        if draft.valid_from:
            draft_date = draft.valid_from.date()
            t = draft.valid_from.strftime("%H:%M")
            t_label = draft.valid_from.strftime("%I:%M %p").lstrip("0")
        elif draft.created_at:
            draft_date = draft.created_at.date()
            t = draft.created_at.strftime("%H:%M")
            t_label = draft.created_at.strftime("%I:%M %p").lstrip("0")
        else:
            draft_date = today
            t = "00:00"
            t_label = ""
        if draft_date < range_start or draft_date >= range_end:
            continue
        status = draft.status or "scheduled"
        workflow = bq_cal_view.get_workflow_for_draft(draft.id)
        wf_name = workflow.canonical_name if workflow else "Draft"
        platform = meta.get("platform", "unknown")
        items_by_date.setdefault(draft_date.isoformat(), []).append({
            "type": "draft",
            "platform": platform,
            "title": wf_name,
            "time": t,
            "time_label": t_label,
            "status": status,
            "detail": (draft.content[:120] + "...") if draft.content and len(draft.content) > 120 else (draft.content or ""),
            "content": draft.content or "",
        })

    # Active campaigns
    campaigns = (
        db.query(Campaign)
        .filter(Campaign.status == CampaignStatus.ACTIVE, Campaign.start_date.isnot(None), Campaign.end_date.isnot(None),
                Campaign.start_date <= range_end, Campaign.end_date >= range_start)
        .all()
    )
    for camp in campaigns:
        d = max(camp.start_date, range_start)
        visible_end = min(camp.end_date, range_end - _td(days=1))
        while d <= visible_end:
            items_by_date.setdefault(d.isoformat(), []).append({
                "type": "campaign",
                "platform": "",
                "title": camp.name,
                "time": "",
                "time_label": "",
                "status": "campaign",
                "detail": camp.objective[:60] if camp.objective else "",
                "content": "",
            })
            d += _td(days=1)

    # Sort each day's items by time
    for day_key in items_by_date:
        items_by_date[day_key].sort(key=lambda x: x["time"])

    # ---------- build month_days ----------
    month_days = []
    for i in range(42):
        d = grid_start + _td(days=i)
        d_iso = d.isoformat()
        month_days.append({
            "date": d_iso,
            "day": d.day,
            "weekday": d.strftime("%a"),
            "label": d.strftime("%b %d"),
            "full_label": d.strftime("%A, %B %d, %Y"),
            "is_today": d == today,
            "is_current_month": d.month == month,
            "is_weekend": d.weekday() >= 5,
            "items": items_by_date.get(d_iso, []),
        })

    # ---------- build week_days ----------
    week_days = []
    for i in range(7):
        d = week_start + _td(days=i)
        d_iso = d.isoformat()
        week_days.append({
            "date": d_iso,
            "day": d.day,
            "weekday_short": d.strftime("%a"),
            "weekday_full": d.strftime("%A"),
            "label": d.strftime("%b %d"),
            "full_label": d.strftime("%A, %B %d, %Y"),
            "is_today": d == today,
            "is_weekend": d.weekday() >= 5,
            "items": items_by_date.get(d_iso, []),
        })

    # ---------- build day view ----------
    day_iso = anchor.isoformat()
    day_items = items_by_date.get(day_iso, [])
    hours = []
    for h in range(24):
        hour_items = [it for it in day_items if it["time"].startswith(f"{h:02d}:")]
        hours.append({
            "hour": h,
            "label": f"{h:02d}:00" if h > 0 else "12 AM",
            "label_12": datetime(2000, 1, 1, h).strftime("%I %p").lstrip("0"),
            "items": hour_items,
        })

    # navigation helpers
    prev_month = (month_start - _td(days=1)).replace(day=1)
    next_month = (month_start + _td(days=32)).replace(day=1)
    prev_week = week_start - _td(days=7)
    next_week = week_start + _td(days=7)
    prev_day = anchor - _td(days=1)
    next_day = anchor + _td(days=1)

    # Load partner sources for the workflow wizard
    partner_sources = []
    try:
        partner_sources = [
            {"slug": ps.slug, "display_name": ps.display_name}
            for ps in db.query(PartnerSource).filter(PartnerSource.enabled == True).all()
        ]
    except Exception:
        pass

    return {
        "anchor": anchor.isoformat(),
        "today": today.isoformat(),
        "anchor_day": {
            "day": anchor.day,
            "weekday_short": anchor.strftime("%a"),
            "is_today": anchor == today,
        },
        "month_label": anchor.strftime("%B %Y"),
        "week_label": f"{week_start.strftime('%b %d')} – {(week_end - _td(days=1)).strftime('%b %d, %Y')}",
        "day_label": anchor.strftime("%A, %B %d, %Y"),
        "month_days": month_days,
        "week_days": week_days,
        "day_hours": hours,
        "day_items": day_items,
        "nav": {
            "prev_month": prev_month.isoformat(),
            "next_month": next_month.isoformat(),
            "prev_week": prev_week.isoformat(),
            "next_week": next_week.isoformat(),
            "prev_day": prev_day.isoformat(),
            "next_day": next_day.isoformat(),
            "today": today.isoformat(),
        },
        "partner_sources": partner_sources,
        "items_json": json.dumps(items_by_date),
    }


@web_router.get("/calendar")
def calendar_view(
    request: Request,
    db: Session = Depends(get_db),
    date_str: str | None = None,
    view: str = "month",
):
    anchor = None
    if date_str:
        try:
            anchor = date.fromisoformat(date_str)
        except ValueError:
            pass

    data = load_calendar_view_data(db, anchor)

    return templates.TemplateResponse(
        request,
        "calendar.html",
        {
            "page": "calendar",
            "view": view,
            **data,
        },
    )


@web_router.get("/triggers")
def trigger_feed_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "trigger_feed.html",
        {
            "page": "triggers",
            "items": load_trigger_feed_items(db),
        },
    )


@web_router.get("/activity")
def activity_view(
    request: Request,
    query: str = "",
    bucket: str | None = None,
    platform: str | None = None,
    days: str | None = None,
    db: Session = Depends(get_db),
):
    from datetime import timedelta
    from app.models.content_brain import ContentBrainAsset, ContentBrainItem, ContentPlatform
    from app.models.workflow import Platform as PlatformEnum

    items: list[dict[str, Any]] = []

    # -- date cutoff -----------------------------------------------------------
    cutoff = None
    if days:
        try:
            cutoff = datetime.utcnow() - timedelta(days=int(days))
        except (ValueError, TypeError):
            pass

    # -- Content Brain items (the REAL past content) ---------------------------
    # This is the primary data source: all scraped/ingested content
    include_brain = bucket in (None, "", "brain", "published")
    if include_brain:
        brain_q = db.query(ContentBrainItem).filter(
            ContentBrainItem.item_type.in_(["post", "reel", "video", "article", "social_post", "research_pdf"])
        )
        if platform:
            if platform == "research":
                brain_q = brain_q.filter(ContentBrainItem.item_type == "research_pdf")
            else:
                platform_map = {
                    "linkedin": ContentPlatform.LINKEDIN,
                    "instagram": ContentPlatform.INSTAGRAM,
                    "youtube": ContentPlatform.YOUTUBE,
                }
                if platform in platform_map:
                    brain_q = brain_q.filter(ContentBrainItem.platform == platform_map[platform])
        if query:
            brain_q = brain_q.filter(
                ContentBrainItem.title.ilike(f"%{query}%")
                | ContentBrainItem.summary.ilike(f"%{query}%")
                | ContentBrainItem.body_text.ilike(f"%{query}%")
            )
        if cutoff:
            brain_q = brain_q.filter(
                (ContentBrainItem.published_at >= cutoff) | (ContentBrainItem.created_at >= cutoff)
            )
        brain_q = brain_q.order_by(
            ContentBrainItem.published_at.desc().nullslast(),
            ContentBrainItem.created_at.desc(),
        ).limit(100)

        # Pre-load assets for brain items
        brain_items = brain_q.all()
        brain_item_ids = [item.id for item in brain_items]
        assets_by_item: dict[str, list[dict]] = {}
        if brain_item_ids:
            for asset in db.query(ContentBrainAsset).filter(ContentBrainAsset.content_item_id.in_(brain_item_ids)).all():
                key = str(asset.content_item_id)
                if key not in assets_by_item:
                    assets_by_item[key] = []
                assets_by_item[key].append({"type": asset.asset_type, "url": asset.url})

        # Readable labels
        _type_labels = {
            "post": "Post", "reel": "Reel", "video": "Video", "page": "Page",
            "article": "Article", "social_post": "Post", "profile": "Profile",
            "bundle_chunk": "Document", "sitemap_entry": "Page", "research_pdf": "Research Paper",
        }
        _plat_labels = {
            "instagram": "Instagram", "linkedin": "LinkedIn", "youtube": "YouTube", "web": "Web",
        }

        for item in brain_items:
            display_date = item.published_at or item.created_at
            item_assets = assets_by_item.get(str(item.id), [])
            image_url = next((a["url"] for a in item_assets if a["type"] == "image"), None)

            # Generate YouTube thumbnail from external_id
            if not image_url and item.platform and item.platform.value == "youtube" and item.external_id:
                image_url = f"https://img.youtube.com/vi/{item.external_id}/mqdefault.jpg"

            # Use summary as the clean content; fall back to body_text
            clean_content = item.summary
            if not clean_content and item.body_text:
                clean_content = item.body_text[:500]

            # Build readable title
            plat_label = _plat_labels.get(item.platform.value, "") if item.platform else ""
            type_label = _type_labels.get(item.item_type, item.item_type)
            raw_title = item.title or ""

            if item.platform and item.platform.value == "instagram" and item.item_type in ("post", "reel"):
                # IG titles are shortcodes — extract caption from summary instead
                if item.summary and '": "' in item.summary:
                    caption = item.summary[item.summary.index('": "') + 4:].rstrip('"')
                    display_title = caption[:90] + ("..." if len(caption) > 90 else "")
                elif item.summary:
                    display_title = item.summary[:90]
                else:
                    display_title = f"{plat_label} {type_label}"
            elif item.item_type == "bundle_chunk":
                display_title = raw_title.replace("ntangible_chunk_", "").replace("_", " ").title() if raw_title else "Document"
            elif item.item_type == "sitemap_entry":
                if raw_title:
                    display_title = raw_title
                elif item.url:
                    display_title = item.url.rstrip("/").split("/")[-1].replace("-", " ").replace("_", " ").title()
                else:
                    display_title = "Page"
            elif raw_title:
                display_title = raw_title
            else:
                display_title = f"{plat_label} {type_label}"

            items.append({
                "id": str(item.id),
                "type": "published",
                "bucket": "brain",
                "title": display_title,
                "content": clean_content,
                "platform": item.platform.value if item.platform else None,
                "item_type": item.item_type,
                "workflow_name": None,
                "workflow_slug": None,
                "trigger_label": type_label,
                "trigger_type": None,
                "notes": None,
                "url": item.url,
                "author": item.author,
                "image_url": image_url,
                "external_id": item.external_id,
                "metadata": {},
                "created_at": display_date.isoformat() if display_date else "",
                "created_label": display_date.strftime("%b %d, %Y %H:%M") if display_date else "",
            })

    # -- sort and limit --------------------------------------------------------
    items.sort(key=lambda x: x["created_at"] or datetime.min, reverse=True)
    items = items[:100]

    brain_count = db.query(ContentBrainItem).count()
    summary = {
        "total": len(items),
        "brain": sum(1 for i in items if i["bucket"] == "brain"),
        "published": sum(1 for i in items if i["type"] == "published"),
        "rejected": sum(1 for i in items if i["type"] == "rejected"),
        "expired": sum(1 for i in items if i["type"] == "expired"),
        "trigger": sum(1 for i in items if i["type"] == "trigger"),
        "brain_total": brain_count,
    }

    return templates.TemplateResponse(
        request,
        "activity.html",
        {
            "page": "activity",
            "review_count": db.query(KnowledgeNode).filter(KnowledgeNode.kind == "draft", KnowledgeNode.status == "review_required").count(),
            "days": days or "",
            "query": query,
            "bucket": bucket or "",
            "platform": platform or "",
            "items": items,
            "summary": summary,
        },
    )


@web_router.get("/brain")
def brain_view(
    request: Request,
    query: str = "",
    bucket: str | None = None,
    platform: str | None = None,
    workflow_slug: str | None = None,
    db: Session = Depends(get_db),
):
    results = _safe_fetch(
        "brain search",
        lambda: load_brain_results(
            db,
            query=query,
            bucket=bucket,
            platform=platform,
            workflow_slug=workflow_slug,
        ),
        lambda: {"query": query, "items": [], "summary": {"total": 0, "approved": 0, "rejected": 0}},
    )
    return templates.TemplateResponse(
        request,
        "brain.html",
        {
            "page": "brain",
            "review_count": load_review_count(db),
            **results,
        },
    )


@web_router.get("/analytics")
def analytics_view(
    request: Request,
    platform: str | None = None,
    tab: str = "published",
    metric: str = "volume",
    period: int = 365,
    db: Session = Depends(get_db),
):
    review_count = _safe_fetch(
        "analytics review count",
        lambda: db.query(KnowledgeNode).filter(
            KnowledgeNode.kind == "draft",
            KnowledgeNode.status == "review_required",
        ).count(),
        0,
    )

    analytics_dashboard = _safe_fetch(
        "analytics dashboard",
        lambda: load_analytics_dashboard(db, platform=platform, days=period),
        lambda: {
            "summary": _default_analytics_summary(period),
            "workflow_metrics": [],
            "platform_metrics": [],
            "recycle_candidates": [],
            "filters": {"platform": platform, "workflow_slug": None, "days": period},
        },
    )
    summary = {**_default_analytics_summary(period), **analytics_dashboard.get("summary", {})}
    workflow_metrics = analytics_dashboard.get("workflow_metrics", [])
    platform_metrics = analytics_dashboard.get("platform_metrics", [])

    weekly_digest = _safe_fetch(
        "weekly digest",
        lambda: generate_weekly_digest(db),
        _empty_weekly_digest,
    )
    weekly_digest = {**_empty_weekly_digest(), **(weekly_digest or {})}

    competitor_dashboard = _safe_fetch(
        "competitor dashboard",
        lambda: load_competitor_dashboard(db),
        lambda: {"sources": [], "signals": []},
    )
    revenue_dashboard = _safe_fetch(
        "revenue dashboard",
        lambda: load_revenue_dashboard(db),
        lambda: {
            "playbooks": [],
            "executions": [],
            "conversion_goals": [],
            "conversion_events": [],
            "sales_packages": [],
        },
    )
    published_posts = _safe_fetch(
        "recent published posts",
        lambda: _load_recent_published_posts(db, platform=platform, limit=100),
        [],
    )

    platform_counts = {
        "linkedin": 0,
        "x": 0,
        "instagram": 0,
        "newsletter": 0,
    }
    for row in platform_metrics:
        row_platform = row.get("platform")
        if row_platform in platform_counts:
            platform_counts[row_platform] = int(row.get("record_count", 0) or 0)
    if not any(platform_counts.values()):
        for post in published_posts:
            row_platform = post.get("platform")
            if row_platform in platform_counts:
                platform_counts[row_platform] += 1

    return templates.TemplateResponse(
        request,
        "analytics.html",
        {
            "page": "analytics",
            "review_count": review_count,
            "summary": summary,
            "workflow_metrics": workflow_metrics,
            "weekly_digest": weekly_digest,
            "signals": competitor_dashboard.get("signals", []),
            "playbooks": revenue_dashboard.get("playbooks", []),
            "conversion_goals": revenue_dashboard.get("conversion_goals", []),
            "executions": revenue_dashboard.get("executions", []),
            "platform_counts": platform_counts,
            "published_posts": published_posts,
            "selected_platform": platform,
            "selected_tab": tab,
            "selected_metric": metric,
            "selected_period": period,
        },
    )


@web_router.post("/analytics/run-playbook", response_class=HTMLResponse)
async def analytics_run_playbook_fragment(
    request: Request,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    playbook_slug = form_data.get("playbook_slug", [None])[0]
    if not playbook_slug:
        return HTMLResponse('<div class="alert alert-danger">Missing playbook_slug</div>')
    try:
        result = run_revenue_playbook_from_web(
            db,
            playbook_slug,
            actor="admin",
            source_kind="dashboard",
            source_id="manual",
        )
        db.commit()
    except Exception as exc:
        logger.exception("Revenue playbook run failed: %s", exc)
        return HTMLResponse(
            f'<div class="alert alert-danger">Error: {exc}</div>'
        )
    return templates.TemplateResponse(
        request,
        "partials/revenue_run_result.html",
        {"result": result},
    )


@web_router.get("/campaigns")
def campaigns_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "campaigns.html",
        {
            "page": "campaigns",
            "campaigns": load_campaign_rows(db),
        },
    )


@web_router.post("/campaigns/{campaign_slug}/run", response_class=HTMLResponse)
async def campaign_run_fragment(
    request: Request,
    campaign_slug: str,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    actor = form_data.get("actor", ["planner"])[0]
    try:
        result = run_campaign_from_web(db, campaign_slug, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return templates.TemplateResponse(
        request,
        "partials/campaign_run_result.html",
        {"result": result},
    )


@web_router.get("/partners")
def partners_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "partners.html",
        {
            "page": "partners",
            **load_partner_dashboard(db),
        },
    )


@web_router.get("/revenue")
def revenue_view(request: Request, db: Session = Depends(get_db)):
    dashboard = load_revenue_dashboard(db)
    playbooks = dashboard.get("playbooks", [])
    goals = dashboard.get("conversion_goals", [])
    packages = dashboard.get("sales_packages", [])
    executions = dashboard.get("executions", [])
    conversion_events = dashboard.get("conversion_events", [])

    # --- Lead pipeline data ---
    try:
        lead_data = load_lead_dashboard(db)
    except Exception:
        lead_data = {"leads": [], "tasks": []}
    leads = lead_data.get("leads", [])

    # --- Intent split from weekly digest ---
    try:
        digest = generate_weekly_digest(db)
    except Exception:
        digest = {"intent_split": {}, "total_posts": 0}
    intent_split = digest.get("intent_split", {})
    revenue_pct = intent_split.get("revenue", 0.0)
    brand_pct = intent_split.get("brand", 0.0)
    partner_pct = intent_split.get("partner", 0.0)
    total_posts = digest.get("total_posts", 0)

    playbook_purposes: dict[str, str] = {
        "alliance-registration-push": (
            "Drives assessment sign-ups during July/Aug and December testing windows. "
            "Urgency-driven messaging tied to real platform data: "
            "\u201cCoaches from D1 programs searched Clutch Factor\u2122 scores this week.\u201d"
        ),
        "fss-roi-summary": (
            "Packages hard ROI numbers FSS can use with their board: athletes tested, "
            "profiles viewed by coaches, commitment rates. Proves the integration\u2019s "
            "value after each event circuit."
        ),
        "coach-demo-push-linkedin": (
            "Makes other programs ask \u201cwhy don\u2019t we have this?\u201d Short-form "
            "case studies from verified clients designed to drive demo requests from "
            "coaches and front offices."
        ),
    }
    for pb in playbooks:
        pb["purpose"] = playbook_purposes.get(pb.get("slug", ""), "")

    # Group playbooks by persona for audience-segmented display
    persona_groups: dict[str, list[dict[str, Any]]] = {}
    persona_labels = {
        "coach": "For Coaches",
        "event_operator": "For Partners",
        "partner_operator": "For Partners",
        "athlete": "For Athletes & Parents",
        "parent": "For Athletes & Parents",
    }
    for pb in playbooks:
        label = persona_labels.get(pb.get("persona", ""), "Other")
        persona_groups.setdefault(label, []).append(pb)

    # Partner enablement status (static structure reflecting Blueprint partners)
    partner_enablement = [
        {
            "partner": "Alliance Fastpitch",
            "slug": "alliance_fastpitch",
            "items": [
                {"label": "Registration push content", "type": "registration_push"},
                {"label": "Proof of value summary", "type": "partner_roi_summary"},
            ],
        },
        {
            "partner": "Future Stars Series (FSS)",
            "slug": "fss",
            "items": [
                {"label": "Event differentiation copy", "type": "event_differentiation"},
                {"label": "Post-event proof package", "type": "partner_roi_summary"},
            ],
        },
        {
            "partner": "Collegiate (MSU, Hofstra, BC)",
            "slug": "collegiate",
            "items": [
                {"label": "Athletic department ROI content", "type": "roi_justification"},
            ],
        },
    ]
    # Mark items as generated if a matching sales package exists
    package_kinds = {p.get("package_kind") for p in packages}
    for group in partner_enablement:
        for item in group["items"]:
            item["generated"] = item["type"] in package_kinds

    return templates.TemplateResponse(
        request,
        "revenue.html",
        {
            "page": "revenue",
            "playbooks": playbooks,
            "persona_groups": persona_groups,
            "executions": executions,
            "conversion_goals": goals,
            "conversion_events": conversion_events,
            "sales_packages": packages,
            "leads": leads,
            "partner_enablement": partner_enablement,
            "active_playbook_count": sum(1 for p in playbooks if p.get("active")),
            "execution_count": len(executions),
            "active_goal_count": sum(1 for g in goals if g.get("active")),
            "inactive_goal_count": sum(1 for g in goals if not g.get("active")),
            "delivered_package_count": sum(1 for p in packages if p.get("status") == "delivered"),
            "review_package_count": sum(1 for p in packages if p.get("status") == "needs_review"),
            "revenue_pct": revenue_pct,
            "brand_pct": brand_pct,
            "partner_pct": partner_pct,
            "total_posts": total_posts,
            "conversion_event_count": len(conversion_events),
        },
    )


@web_router.get("/expansion")
def expansion_view(request: Request, db: Session = Depends(get_db)):
    modules = load_expansion_modules(db)

    # Sum numeric counts from each module's count_label (e.g. "4 articles" -> 4)
    total_assets = 0
    for m in modules:
        label = m.get("count_label", "")
        parts = label.split()
        if parts and parts[0].isdigit():
            total_assets += int(parts[0])

    # Pull repurposing stats for derivatives/sources
    rep_module = next((m for m in modules if m["slug"] == "repurposing"), None)
    rep_stats = rep_module.get("stats", {}) if rep_module else {}
    derivative_count = rep_stats.get("derivatives", 0)
    source_count = rep_stats.get("sources", 0)

    return templates.TemplateResponse(
        request,
        "expansion.html",
        {
            "page": "expansion",
            "review_count": load_review_count(db),
            "modules": modules,
            "total_assets": total_assets,
            "derivative_count": derivative_count,
            "source_count": source_count,
        },
    )


@web_router.post("/revenue/playbooks/{playbook_slug}/run", response_class=HTMLResponse)
async def revenue_playbook_fragment(
    request: Request,
    playbook_slug: str,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    actor = form_data.get("actor", ["sales"])[0]
    source_kind = form_data.get("source_kind", ["manual"])[0]
    source_id = form_data.get("source_id", ["manual-run"])[0]
    result = run_revenue_playbook_from_web(
        db,
        playbook_slug,
        actor=actor,
        source_kind=source_kind,
        source_id=source_id,
    )
    db.commit()
    return templates.TemplateResponse(
        request,
        "partials/revenue_run_result.html",
        {"result": result},
    )


@web_router.post("/partners/{partner_slug}/events", response_class=HTMLResponse)
async def partner_event_fragment(
    request: Request,
    partner_slug: str,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    payload = {key: values[0] for key, values in form_data.items()}
    result = ingest_partner_event_from_web(db, partner_slug, payload)
    db.commit()
    return templates.TemplateResponse(
        request,
        "partials/partner_event_result.html",
        {"result": result},
    )


@web_router.post("/partners/bundles/{bundle_id}/action", response_class=HTMLResponse)
async def partner_bundle_fragment(
    request: Request,
    bundle_id: str,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    status = form_data.get("status", ["delivered"])[0]
    result = update_partner_bundle_from_web(db, bundle_id, status=status)
    db.commit()
    return templates.TemplateResponse(
        request,
        "partials/partner_bundle_result.html",
        {"result": result},
    )


@web_router.get("/competitors")
def competitors_view(request: Request, db: Session = Depends(get_db)):
    dashboard = load_competitor_dashboard(db)
    return templates.TemplateResponse(
        request,
        "competitors.html",
        {
            "page": "competitors",
            **dashboard,
        },
    )


@web_router.post("/competitors/signals/{signal_id}/respond", response_class=HTMLResponse)
async def competitor_signal_fragment(
    request: Request,
    signal_id: str,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    platform = form_data.get("platform", ["linkedin"])[0]
    actor = form_data.get("actor", ["analyst"])[0]
    result = respond_to_competitor_signal_from_web(
        db,
        signal_id,
        platform=platform,
        actor=actor,
    )
    db.commit()
    return templates.TemplateResponse(
        request,
        "partials/competitor_signal_result.html",
        {"result": result},
    )


@web_router.get("/leads")
def leads_view(request: Request, db: Session = Depends(get_db)):
    dashboard = load_lead_dashboard(db)
    return templates.TemplateResponse(
        request,
        "leads.html",
        {
            "page": "leads",
            **dashboard,
        },
    )


@web_router.post("/leads/{lead_id}/generate-content", response_class=HTMLResponse)
async def lead_generate_fragment(
    request: Request,
    lead_id: str,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    platform = form_data.get("platform", ["linkedin"])[0]
    actor = form_data.get("actor", ["sales"])[0]
    result = generate_lead_content_from_web(
        db,
        lead_id,
        platform=platform,
        actor=actor,
    )
    db.commit()
    return templates.TemplateResponse(
        request,
        "partials/lead_task_result.html",
        {"result": result},
    )


def _cron_fire_dates(cron_expr: str, tz_name: str, start: date, days: int = 28) -> list[datetime]:
    """Compute fire dates for a simple 5-field cron over a date range."""
    fields = cron_expr.strip().split()
    if len(fields) != 5:
        return []
    minute_f, hour_f, _day_f, _month_f, weekday_f = fields
    minute = int(minute_f) if minute_f.isdigit() else 0
    hour = int(hour_f) if hour_f.isdigit() else 9
    tz = ZoneInfo(tz_name or "America/New_York")
    results: list[datetime] = []
    for offset in range(days):
        d = start + timedelta(days=offset)
        candidate = datetime(d.year, d.month, d.day, hour, minute, tzinfo=tz)
        if weekday_f == "*" or not weekday_f.isdigit():
            results.append(candidate)
        else:
            target = (int(weekday_f) - 1) % 7
            if candidate.weekday() == target:
                results.append(candidate)
    return results


_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_CRON_WEEKDAYS = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}


def _cron_human_label(cron_expr: str) -> str:
    """Return a short human label like 'Every Tue 9:00 AM'."""
    fields = cron_expr.strip().split()
    if len(fields) != 5:
        return cron_expr
    minute_f, hour_f, _day_f, _month_f, weekday_f = fields
    minute = int(minute_f) if minute_f.isdigit() else 0
    hour = int(hour_f) if hour_f.isdigit() else 0
    ampm = "AM" if hour < 12 else "PM"
    display_hour = hour % 12 or 12
    time_str = f"{display_hour}:{minute:02d} {ampm}"
    if weekday_f == "*":
        return f"Every day {time_str}"
    if weekday_f.isdigit():
        day_name = _CRON_WEEKDAYS.get(int(weekday_f), weekday_f)
        return f"Every {day_name} {time_str}"
    return f"{cron_expr} ({time_str})"


def _build_calendar_data(db: Session, today: date) -> list[dict]:
    """Build 28-day rolling calendar data grouped by day."""
    end_date = today + timedelta(days=28)
    all_workflows = {str(wf.id): wf for wf in db.query(Workflow).all()}

    # Calendar rules (recurring)
    rules = db.query(CalendarRule).filter(CalendarRule.enabled.is_(True)).all()
    rule_fire_dates: dict[str, list[dict]] = {}
    for rule in rules:
        wf = all_workflows.get(str(rule.workflow_id))
        wf_name = wf.name if wf else "Unknown Workflow"
        wf_platform = wf.platform.value if wf and wf.platform else "x"
        fire_dates = _cron_fire_dates(rule.cron_expression, rule.timezone, today, 28)
        label = _cron_human_label(rule.cron_expression)
        for dt in fire_dates:
            day_key = dt.strftime("%Y-%m-%d")
            item = {
                "type": "rule",
                "platform": wf_platform,
                "title": wf_name,
                "time": dt.strftime("%I:%M %p").lstrip("0"),
                "status": "recurring",
                "detail": label,
            }
            rule_fire_dates.setdefault(day_key, []).append(item)

    # Scheduled drafts from KnowledgeNodes
    draft_items: dict[str, list[dict]] = {}
    today_start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, tzinfo=timezone.utc)
    bq_sched = BrainQuery(db)
    sched_drafts = (
        db.query(KnowledgeNode)
        .filter(
            KnowledgeNode.kind == "draft",
            KnowledgeNode.status == "scheduled",
            KnowledgeNode.valid_from.isnot(None),
            KnowledgeNode.valid_from >= today_start,
            KnowledgeNode.valid_from < end_dt,
        )
        .all()
    )
    for draft in sched_drafts:
        dt = draft.valid_from
        day_key = dt.strftime("%Y-%m-%d")
        status = draft.status or "scheduled"
        workflow = bq_sched.get_workflow_for_draft(draft.id)
        wf_name = workflow.canonical_name if workflow else "Draft"
        meta = draft.metadata_ or {}
        wf_platform = meta.get("platform", "unknown")
        preview = (draft.content[:80] + "...") if draft.content and len(draft.content) > 80 else (draft.content or "")
        item = {
            "type": "draft",
            "platform": wf_platform,
            "title": wf_name,
            "time": dt.strftime("%I:%M %p").lstrip("0"),
            "status": status,
            "detail": preview,
        }
        draft_items.setdefault(day_key, []).append(item)

    # Active campaigns
    campaign_items: dict[str, list[dict]] = {}
    campaigns = (
        db.query(Campaign)
        .filter(
            Campaign.status == CampaignStatus.ACTIVE,
            Campaign.start_date.isnot(None),
            Campaign.end_date.isnot(None),
            Campaign.start_date <= end_date,
            Campaign.end_date >= today,
        )
        .all()
    )
    for camp in campaigns:
        visible_start = max(camp.start_date, today)
        visible_end = min(camp.end_date, end_date - timedelta(days=1))
        d = visible_start
        while d <= visible_end:
            day_key = d.isoformat()
            is_start = d == camp.start_date
            is_end = d == camp.end_date
            pos = "start" if is_start else ("end" if is_end else "middle")
            item = {
                "type": "campaign",
                "platform": "",
                "title": camp.name,
                "time": "",
                "status": pos,
                "detail": camp.objective[:60] if camp.objective else "",
            }
            campaign_items.setdefault(day_key, []).append(item)
            d += timedelta(days=1)

    # Assemble day-by-day list
    calendar_days: list[dict] = []
    for offset in range(28):
        d = today + timedelta(days=offset)
        day_key = d.isoformat()
        day_name = _DAY_NAMES[d.weekday()]
        day_label = d.strftime(f"{day_name} %b %-d")
        items: list[dict] = []
        items.extend(campaign_items.get(day_key, []))
        items.extend(sorted(rule_fire_dates.get(day_key, []), key=lambda x: x["time"]))
        items.extend(sorted(draft_items.get(day_key, []), key=lambda x: x["time"]))
        is_today = d == today
        is_weekend = d.weekday() >= 5
        calendar_days.append({
            "date": day_key,
            "day_label": day_label,
            "is_today": is_today,
            "is_weekend": is_weekend,
            "items": items,
        })
    return calendar_days


@web_router.get("/workflows")
def workflows_list_view(request: Request, db: Session = Depends(get_db)):
    workflows = db.query(Workflow).order_by(Workflow.name).all()
    workflow_cards = []
    for wf in workflows:
        active_version = db.query(WorkflowVersion).filter(WorkflowVersion.id == wf.active_version_id).first() if wf.active_version_id else None
        # Count drafts via brain EntityNode → KnowledgeNode via edges
        bq_wf = BrainQuery(db)
        wf_entity = bq_wf.get_entity_by_slug("workflow", wf.slug)
        published = 0
        rejected = 0
        expired = 0
        last_draft = None
        if wf_entity:
            prod_edges = bq_wf.get_edges_from(wf_entity.id, relation="produced")
            draft_ids = [e.target_id for e in prod_edges]
            for did in draft_ids:
                node = bq_wf.get_knowledge_node(did)
                if node and node.kind == "draft":
                    if node.status == "active":
                        published += 1
                    elif node.status == "rejected":
                        rejected += 1
                    elif node.status == "expired":
                        expired += 1
                    if last_draft is None or (node.created_at and last_draft.created_at and node.created_at > last_draft.created_at):
                        last_draft = node

        # Build trigger description from calendar rules or partner sources
        trigger_desc = ""
        trigger_type = "calendar"
        calendar_rule = db.query(CalendarRule).filter(CalendarRule.workflow_id == wf.id, CalendarRule.enabled == True).first()
        if calendar_rule:
            # Convert cron to human-readable
            cron = calendar_rule.cron_expression or ""
            cron_parts = cron.split()
            day_names = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}
            if len(cron_parts) >= 5:
                cron_min, cron_hr = cron_parts[0], cron_parts[1]
                cron_dow = cron_parts[4]
                time_str = f"{int(cron_hr)}:{cron_min.zfill(2)} AM" if int(cron_hr) < 12 else f"{int(cron_hr)-12 if int(cron_hr) > 12 else 12}:{cron_min.zfill(2)} PM"
                if cron_dow == "*":
                    day_str = "Every day"
                else:
                    day_str = "Every " + ", ".join(day_names.get(int(d), d) for d in cron_dow.split(",") if d.isdigit())
                trigger_desc = f"{day_str} at {time_str} ET"
            else:
                trigger_desc = f"Schedule: {cron}"
        else:
            # Check for external trigger events
            last_trigger = (
                db.query(TriggerEvent)
                .filter(TriggerEvent.workflow_id == wf.id, TriggerEvent.trigger_type == TriggerType.EXTERNAL)
                .order_by(TriggerEvent.created_at.desc())
                .first()
            )
            if last_trigger:
                trigger_type = "external"
                partner = db.query(PartnerSource).filter(PartnerSource.id == last_trigger.partner_source_id).first() if last_trigger.partner_source_id else None
                partner_label = partner.display_name if partner else "External"
                event_label = last_trigger.external_event_type or "event"
                trigger_desc = f"On {partner_label} {event_label}"

        # Extract config data for display
        config = active_version.config if active_version else {}
        tone_notes = ""
        target_audience = ""
        if isinstance(config, dict):
            prompt_cfg = config.get("prompt", {})
            routing_cfg = config.get("routing", {})
            tone_notes = prompt_cfg.get("tone_notes", "")
            target_audience = routing_cfg.get("target_audience_segment", "")

        workflow_cards.append({
            "id": str(wf.id),
            "slug": wf.slug,
            "name": wf.name,
            "platform": wf.platform.value if wf.platform else "unknown",
            "content_type": wf.content_type,
            "mode": wf.mode.value if hasattr(wf, 'mode') and wf.mode else "manual",
            "trigger_type": trigger_type,
            "enabled": wf.enabled,
            "active_version_number": active_version.version_number if active_version else None,
            "published_count": published,
            "rejected_count": rejected,
            "expired_count": expired,
            "last_run_label": _format_dt(last_draft.created_at) if last_draft else None,
            "trigger_description": trigger_desc,
            "tone_summary": (tone_notes[:80] + "...") if len(tone_notes) > 80 else tone_notes,
            "target_audience": target_audience,
        })

    # Load partner sources for the wizard dropdown
    partner_sources = _safe_fetch(
        "partner_sources",
        lambda: [{"slug": ps.slug, "display_name": ps.display_name} for ps in db.query(PartnerSource).filter(PartnerSource.enabled == True).all()],
        list,
    )

    # Load last 5 published posts per platform for the platform detail panels
    bq_plat = BrainQuery(db)
    recent_posts_by_platform: dict[str, list[dict[str, Any]]] = {}
    for plat in ["linkedin", "x", "instagram", "newsletter"]:
        try:
            recent_drafts = bq_plat.list_drafts_by_status("active", limit=5, platform=plat)
            recent_posts_by_platform[plat] = []
            for d in recent_drafts:
                meta = d.metadata_ or {}
                workflow = bq_plat.get_workflow_for_draft(d.id)
                wf_name = workflow.canonical_name if workflow else "Unknown"
                pub_at_str = meta.get("published_at")
                pub_label = None
                if pub_at_str:
                    try:
                        pub_label = _format_dt(datetime.fromisoformat(pub_at_str))
                    except Exception:
                        pass
                recent_posts_by_platform[plat].append({
                    "content": (d.content[:140] + "...") if d.content and len(d.content) > 140 else (d.content or ""),
                    "published_label": pub_label,
                    "workflow_name": wf_name,
                    "post_url": meta.get("post_url"),
                })
        except Exception as exc:
            logger.warning("Recent posts for %s unavailable: %s", plat, exc)
            recent_posts_by_platform[plat] = []

    # Workflow counts per platform
    workflow_counts = {}
    for plat in ["linkedin", "x", "instagram", "newsletter"]:
        workflow_counts[plat] = len([w for w in workflow_cards if w["platform"] == plat])

    today = date.today()
    calendar_days = _build_calendar_data(db, today)
    return templates.TemplateResponse(
        request,
        "workflows.html",
        {
            "page": "workflows",
            "review_count": db.query(KnowledgeNode).filter(KnowledgeNode.kind == "draft", KnowledgeNode.status == "review_required").count(),
            "create_error": request.query_params.get("error", ""),
            "workflows": workflow_cards,
            "partner_sources": partner_sources,
            "calendar_days": calendar_days,
            "recent_posts_by_platform": recent_posts_by_platform,
            "workflow_counts": workflow_counts,
        },
    )


PLATFORM_DATA = {
    "linkedin": {
        "key": "linkedin",
        "name": "LinkedIn",
        "icon": "in",
        "purpose": "Highest-value platform for B2B credibility, investor visibility, enterprise lead generation",
        "audience": "Coaches, front office executives, event directors, integration partners",
        "voice": "Professional but not corporate. Founder-in-the-arena, not press release. Short paragraphs. Data-backed claims.",
        "content_types": ["Thought Leadership", "Data Insight", "Company Update", "Partner Proof", "Case Study"],
        "hashtags": "3-5 max. Mix evergreen (#MentalPerformance, #SportsAnalytics) + topical",
        "cta": 'Soft -- "Thoughts?" / "Anyone else seeing this?" / "DM me"',
        "posting_windows": "Tue-Thu, 7-9 AM and 12-1 PM ET",
        "max_chars": "3,000",
        "images": "Thought leadership headers, partner announcements",
        "automation": "Campaign Planner assigns weekly slots, compliance check, scheduler queues",
        "post_label": "LinkedIn Posts",
        "post_label_singular": "post",
        "short_desc": "B2B credibility & investor visibility",
    },
    "x": {
        "key": "x",
        "name": "X (Twitter)",
        "icon": "X",
        "purpose": "Fastest-moving channel -- real-time commentary, hot takes, data drops",
        "audience": "Sports community, coaches, recruiting coordinators, fans",
        "voice": "Punchy. Contrarian. Sports bar meets data lab. Never sounds like a brand account.",
        "content_types": ["Hot Take", "Data Drop", "Trend Jack", "Thread", "Reactive Content"],
        "hashtags": "1-2 max",
        "cta": "Embedded in voice, no hard sell",
        "posting_windows": "Speed-first. Trend jacks within 20 minutes.",
        "max_chars": "280",
        "images": "Stat cards, quote graphics, assessment previews. Media gets 2-3x engagement.",
        "automation": "Real-time monitoring for reactive + scheduled baseline queue",
        "post_label": "X Posts",
        "post_label_singular": "post",
        "short_desc": "Real-time hot takes & data drops",
    },
    "instagram": {
        "key": "instagram",
        "name": "Instagram",
        "icon": "IG",
        "purpose": "Brand-building and athlete-facing. Visual-first.",
        "audience": "Student-athletes, coaches, sports fans",
        "voice": "Bold, visual-first. Hook must stand alone. Lead with tension or provocative truth.",
        "content_types": [
            "Athlete Spotlight", "Commitment Post", "Clutch Certified",
            "Event Leaderboard", "Bold Statement", "Carousel", "Reel", "Story",
        ],
        "hashtags": "6-10 per post. Always at end.",
        "cta": "One per post. Rotate: tag, link in bio, comment, share.",
        "posting_windows": "Tue-Fri, 11 AM-1 PM and 7-9 PM ET",
        "max_chars": "2,200. Caption formula: Hook (1-2 lines) -> Body (2-4 lines) -> CTA (1 line)",
        "images": "ALWAYS. Canva templates for stat cards, athlete spotlights, bold statements. Carousels for events.",
        "automation": "Visual asset pipeline populates Canva templates",
        "post_label": "Instagram Posts",
        "post_label_singular": "post",
        "short_desc": "Visual brand-building & athletes",
    },
    "newsletter": {
        "key": "newsletter",
        "name": "Newsletter",
        "icon": "&#9993;",
        "purpose": "Monthly value delivery. Dan reviews before send.",
        "audience": "Segment 1 = coaches/scouts. Segment 2 = partners/event directors.",
        "voice": "Data insight hook, client proof, product update, CTA. No fluff.",
        "content_types": ["Monthly Digest", "Segment Update"],
        "hashtags": "Not applicable",
        "cta": "One primary CTA per section. Direct and clear.",
        "posting_windows": "Monthly. Skip if not strong enough.",
        "max_chars": "No hard limit. Structure: Data hook + proof point + product update + CTA",
        "images": "Optional. Clean formatting prioritized over visuals.",
        "automation": "Engine generates draft, Dan reviews before send. Double opt-in, SPF/DKIM/DMARC, monitor deliverability.",
        "post_label": "Newsletter Sends",
        "post_label_singular": "send",
        "short_desc": "Monthly value delivery",
    },
}


@web_router.get("/workflows/platform/{platform_key}")
def platform_detail_view(request: Request, platform_key: str, db: Session = Depends(get_db)):
    platform_info = PLATFORM_DATA.get(platform_key)
    if not platform_info:
        raise HTTPException(status_code=404, detail=f"Unknown platform: {platform_key}")

    # Load workflows for this platform
    workflows = db.query(Workflow).filter(Workflow.platform == Platform(platform_key)).order_by(Workflow.name).all()
    workflow_cards = []
    for wf in workflows:
        active_version = db.query(WorkflowVersion).filter(WorkflowVersion.id == wf.active_version_id).first() if wf.active_version_id else None
        bq_pd = BrainQuery(db)
        wf_entity_pd = bq_pd.get_entity_by_slug("workflow", wf.slug)
        published = 0
        rejected = 0
        expired = 0
        last_draft = None
        if wf_entity_pd:
            prod_edges = bq_pd.get_edges_from(wf_entity_pd.id, relation="produced")
            for edge in prod_edges:
                node = bq_pd.get_knowledge_node(edge.target_id)
                if node and node.kind == "draft":
                    if node.status == "active":
                        published += 1
                    elif node.status == "rejected":
                        rejected += 1
                    elif node.status == "expired":
                        expired += 1
                    if last_draft is None or (node.created_at and last_draft.created_at and node.created_at > last_draft.created_at):
                        last_draft = node

        trigger_desc = ""
        trigger_type = "calendar"
        calendar_rule = db.query(CalendarRule).filter(CalendarRule.workflow_id == wf.id, CalendarRule.enabled == True).first()
        if calendar_rule:
            cron = calendar_rule.cron_expression or ""
            cron_parts = cron.split()
            day_names = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}
            if len(cron_parts) >= 5:
                cron_min, cron_hr = cron_parts[0], cron_parts[1]
                cron_dow = cron_parts[4]
                time_str = f"{int(cron_hr)}:{cron_min.zfill(2)} AM" if int(cron_hr) < 12 else f"{int(cron_hr)-12 if int(cron_hr) > 12 else 12}:{cron_min.zfill(2)} PM"
                if cron_dow == "*":
                    day_str = "Every day"
                else:
                    day_str = "Every " + ", ".join(day_names.get(int(d), d) for d in cron_dow.split(",") if d.isdigit())
                trigger_desc = f"{day_str} at {time_str} ET"
            else:
                trigger_desc = f"Schedule: {cron}"
        else:
            last_trigger = (
                db.query(TriggerEvent)
                .filter(TriggerEvent.workflow_id == wf.id, TriggerEvent.trigger_type == TriggerType.EXTERNAL)
                .order_by(TriggerEvent.created_at.desc())
                .first()
            )
            if last_trigger:
                trigger_type = "external"
                partner = db.query(PartnerSource).filter(PartnerSource.id == last_trigger.partner_source_id).first() if last_trigger.partner_source_id else None
                partner_label = partner.display_name if partner else "External"
                event_label = last_trigger.external_event_type or "event"
                trigger_desc = f"On {partner_label} {event_label}"

        config = active_version.config if active_version else {}
        tone_notes = ""
        target_audience = ""
        if isinstance(config, dict):
            prompt_cfg = config.get("prompt", {})
            routing_cfg = config.get("routing", {})
            tone_notes = prompt_cfg.get("tone_notes", "")
            target_audience = routing_cfg.get("target_audience_segment", "")

        workflow_cards.append({
            "id": str(wf.id),
            "slug": wf.slug,
            "name": wf.name,
            "platform": wf.platform.value if wf.platform else "unknown",
            "content_type": wf.content_type,
            "mode": wf.mode.value if hasattr(wf, "mode") and wf.mode else "manual",
            "trigger_type": trigger_type,
            "enabled": wf.enabled,
            "active_version_number": active_version.version_number if active_version else None,
            "published_count": published,
            "rejected_count": rejected,
            "expired_count": expired,
            "last_run_label": _format_dt(last_draft.created_at) if last_draft else None,
            "trigger_description": trigger_desc,
            "tone_summary": (tone_notes[:80] + "...") if len(tone_notes) > 80 else tone_notes,
            "target_audience": target_audience,
        })

    # Load recent published posts (last 10) via brain KnowledgeNodes
    bq_plat_detail = BrainQuery(db)
    recent_posts: list[dict[str, Any]] = []
    try:
        recent_drafts = bq_plat_detail.list_drafts_by_status("active", limit=10, platform=platform_key)
        recent_posts = []
        for d in recent_drafts:
            meta = d.metadata_ or {}
            workflow = bq_plat_detail.get_workflow_for_draft(d.id)
            wf_name = workflow.canonical_name if workflow else "Unknown"
            pub_at_str = meta.get("published_at")
            pub_label = None
            if pub_at_str:
                try:
                    pub_label = _format_dt(datetime.fromisoformat(pub_at_str))
                except Exception:
                    pass
            recent_posts.append({
                "content": (d.content[:140] + "...") if d.content and len(d.content) > 140 else (d.content or ""),
                "published_label": pub_label,
                "workflow_name": wf_name,
                "post_url": meta.get("post_url"),
            })
    except Exception as exc:
        logger.warning("Recent posts for %s unavailable: %s", platform_key, exc)

    partner_sources = _safe_fetch(
        "partner_sources",
        lambda: [{"slug": ps.slug, "display_name": ps.display_name} for ps in db.query(PartnerSource).filter(PartnerSource.enabled == True).all()],
        list,
    )

    return templates.TemplateResponse(
        request,
        "platform_detail.html",
        {
            "page": "workflows",
            "review_count": db.query(KnowledgeNode).filter(KnowledgeNode.kind == "draft", KnowledgeNode.status == "review_required").count(),
            "platform": platform_info,
            "workflows": workflow_cards,
            "recent_posts": recent_posts,
            "partner_sources": partner_sources,
        },
    )


@web_router.get("/workflows/{workflow_slug}")
def workflow_detail_view(request: Request, workflow_slug: str, db: Session = Depends(get_db)):
    try:
        detail = load_workflow_detail(db, workflow_slug)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    workflow = detail["workflow"]

    # Load calendar rules for this workflow
    calendar_rules = _safe_fetch(
        "calendar_rules",
        lambda: db.query(CalendarRule).filter(CalendarRule.workflow_id == workflow.id).all(),
        list,
    )

    # Load partner trigger info if external
    partner_trigger = None
    last_external = _safe_fetch(
        "partner_trigger",
        lambda: (
            db.query(TriggerEvent)
            .filter(TriggerEvent.workflow_id == workflow.id, TriggerEvent.trigger_type == TriggerType.EXTERNAL)
            .order_by(TriggerEvent.created_at.desc())
            .first()
        ),
        lambda: None,
    )
    if last_external:
        partner = db.query(PartnerSource).filter(PartnerSource.id == last_external.partner_source_id).first() if last_external.partner_source_id else None
        partner_trigger = {
            "partner_name": partner.display_name if partner else "External",
            "event_type": last_external.external_event_type or "event",
        }

    # Parse the active version config for display
    active_version = detail.get("active_version")
    config = None
    if active_version and active_version.config:
        try:
            config = WorkflowVersionConfig.model_validate(active_version.config)
        except Exception:
            config = None

    # Load recent outputs (last 5 drafts from this workflow via brain graph)
    def _load_recent_outputs():
        bq_detail = BrainQuery(db)
        wf_entity = bq_detail.get_entity_by_slug("workflow", workflow.slug)
        if not wf_entity:
            return []
        prod_edges = bq_detail.get_edges_from(wf_entity.id, relation="produced")
        nodes = []
        for edge in prod_edges:
            node = bq_detail.get_knowledge_node(edge.target_id)
            if node and node.kind == "draft":
                nodes.append(node)
        nodes.sort(key=lambda n: n.created_at or datetime.min, reverse=True)
        return [_serialize_brain_card(db, n) for n in nodes[:5]]

    recent_outputs = _safe_fetch("recent_outputs", _load_recent_outputs, list)

    return templates.TemplateResponse(
        request,
        "workflow_detail.html",
        {
            "page": "workflows",
            "review_count": db.query(KnowledgeNode).filter(KnowledgeNode.kind == "draft", KnowledgeNode.status == "review_required").count(),
            "calendar_rules": calendar_rules,
            "partner_trigger": partner_trigger,
            "config": config,
            "recent_outputs": recent_outputs,
            **detail,
        },
    )


@web_router.post("/workflows/{workflow_slug}/improve", response_class=HTMLResponse)
async def workflow_improve_fragment(
    request: Request,
    workflow_slug: str,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    feedback = form_data.get("feedback", [""])[0]
    actor = form_data.get("actor", ["admin"])[0]
    draft_id = form_data.get("draft_id", [None])[0]
    try:
        proposal = WorkflowEditor(db).propose_version(
            workflow_slug,
            feedback=feedback,
            actor=actor,
            draft_id=draft_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return templates.TemplateResponse(
        request,
        "partials/workflow_proposal.html",
        {"proposal": proposal},
    )


@web_router.post("/workflows/{workflow_slug}/versions/{version_number}/activate", response_class=HTMLResponse)
def workflow_activate_fragment(
    request: Request,
    workflow_slug: str,
    version_number: int,
    db: Session = Depends(get_db),
):
    try:
        version = WorkflowEditor(db).activate_version(workflow_slug, version_number)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    db.commit()
    return templates.TemplateResponse(
        request,
        "partials/action_result.html",
        {
            "result": {
                "status_label": "Workflow Updated",
                "status_class": "badge-success",
                "message": f"Activated workflow version v{version.version_number}.",
            }
        },
    )


@web_router.post("/workflows/create")
async def workflow_create(request: Request, db: Session = Depends(get_db)):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    name = form_data.get("name", [""])[0].strip()
    slug = form_data.get("slug", [""])[0].strip()
    platform_val = form_data.get("platform", ["x"])[0]
    content_type = form_data.get("content_type", ["general"])[0].strip()
    mode_val = form_data.get("mode", ["manual"])[0]
    description = form_data.get("description", [""])[0].strip()

    # New wizard fields
    trigger_type_val = form_data.get("trigger_type", ["calendar"])[0]
    target_audience = form_data.get("target_audience", [""])[0].strip()
    content_pillar = form_data.get("content_pillar", [""])[0].strip()
    intent_tag = form_data.get("intent_tag", [""])[0].strip()
    tone_notes = form_data.get("tone_notes", [""])[0].strip()
    cta_preferences = form_data.get("cta_preferences", [""])[0].strip()
    hashtag_rules = form_data.get("hashtag_rules", [""])[0].strip()
    cron_expression = form_data.get("cron_expression", [""])[0].strip()
    trigger_time = form_data.get("trigger_time", [""])[0].strip()
    publish_time = form_data.get("publish_time", [""])[0].strip()
    timezone = form_data.get("timezone", ["America/New_York"])[0].strip()
    partner_source_slug = form_data.get("partner_source", [""])[0].strip()
    event_type = form_data.get("event_type", [""])[0].strip()

    if not name or not slug:
        return _workflow_create_error_response("Name and slug are required.")

    existing = db.query(Workflow).filter(Workflow.slug == slug).first()
    if existing:
        return _workflow_create_error_response(f"Workflow with slug '{slug}' already exists.")

    try:
        platform = Platform(platform_val)
    except ValueError:
        return _workflow_create_error_response(f"Invalid platform: {platform_val}")

    try:
        mode = WorkflowMode(mode_val)
    except ValueError:
        mode = WorkflowMode.MANUAL

    workflow = Workflow(
        id=uuid.uuid4(),
        name=name,
        slug=slug,
        description=description or None,
        platform=platform,
        content_type=content_type,
        mode=mode,
        timezone=timezone,
        enabled=True,
    )
    db.add(workflow)
    db.flush()

    # Build the version config from wizard fields
    config = WorkflowVersionConfig(
        prompt=PromptConfig(
            tone_notes=tone_notes,
        ),
        routing=RoutingConfig(
            target_pillar=content_pillar or None,
            target_intent=intent_tag or None,
            target_content_type=content_type or None,
            target_audience_segment=target_audience or None,
        ),
        cta=CtaConfig(
            cta_rules=cta_preferences,
        ),
    )

    # Apply hashtag rules to formatting config
    if hashtag_rules:
        config.prompt.system_prompt_additions = f"Hashtag rules: {hashtag_rules}"

    version = WorkflowVersion(
        id=uuid.uuid4(),
        workflow_id=workflow.id,
        version_number=1,
        config=config.model_dump(),
        version_note="Initial version from workflow wizard",
        author="admin",
        is_active=True,
    )
    db.add(version)
    db.flush()

    workflow.active_version_id = version.id

    # Create calendar rule if calendar-based trigger
    if trigger_type_val == "calendar" and cron_expression:
        publish_hour = None
        publish_minute = None
        if mode == WorkflowMode.AUTOMATIC and publish_time:
            parts = publish_time.split(":")
            if len(parts) == 2:
                publish_hour = int(parts[0])
                publish_minute = int(parts[1])

        calendar_rule = CalendarRule(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            cron_expression=cron_expression,
            timezone=timezone,
            enabled=True,
            publish_hour_local=publish_hour,
            publish_minute_local=publish_minute,
        )
        db.add(calendar_rule)

    db.commit()

    return RedirectResponse(url="/control-room/workflows", status_code=303)


@web_router.post("/workflows/{workflow_slug}/toggle-mode", response_class=HTMLResponse)
async def workflow_toggle_mode(
    request: Request,
    workflow_slug: str,
    db: Session = Depends(get_db),
):
    workflow = db.query(Workflow).filter(Workflow.slug == workflow_slug).first()
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_slug}' not found")

    if workflow.mode == WorkflowMode.MANUAL:
        workflow.mode = WorkflowMode.AUTOMATIC
        workflow.paused_at = None
    else:
        workflow.mode = WorkflowMode.MANUAL
    db.commit()

    new_label = workflow.mode.value.title()
    badge_class = "badge-info" if workflow.mode == WorkflowMode.AUTOMATIC else "badge-muted"
    button_label = "Switch to Manual" if workflow.mode == WorkflowMode.AUTOMATIC else "Switch to Automatic"

    return HTMLResponse(
        f'<div id="mode-toggle-area">'
        f'<span class="badge {badge_class}">{new_label}</span> '
        f'<button class="btn btn-sm btn-ghost" '
        f'hx-post="/control-room/workflows/{workflow_slug}/toggle-mode" '
        f'hx-target="#mode-toggle-area" hx-swap="outerHTML">'
        f'{button_label}</button>'
        f'</div>'
    )


@web_router.get("/status")
def status_view(request: Request, db: Session = Depends(get_db)):
    try:
        review_count = db.query(KnowledgeNode).filter(KnowledgeNode.kind == "draft", KnowledgeNode.status == "review_required").count()
    except Exception:
        review_count = 0
    summary = _safe_fetch(
        "status summary",
        lambda: load_settings_summary(db),
        lambda: {
            "timezone": get_settings().control_room_default_timezone,
            "auth_required": control_room_auth_enabled(),
            "scheduler_status": {
                "paused_workflows": 0,
                "unhealthy_workflows": 0,
                "upcoming_24h": 0,
                "due_rules": 0,
                "due_drafts": 0,
            },
            "publishers": {},
            "canva": {"renderer": "mock", "has_api_key": False, "brand_template_set": "default"},
            "legacy_mode_note": "",
        },
    )
    return templates.TemplateResponse(
        request,
        "status.html",
        {
            "page": "status",
            "review_count": review_count,
            "summary": summary,
            "session": getattr(request.state, "user", None),
        },
    )



@web_router.post("/settings/connections", response_class=HTMLResponse)
async def settings_connection_action(
    request: Request,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    service = PublishingConnectionService(db)
    service.upsert_connection(
        channel=form_data.get("channel", [""])[0],
        provider_key=form_data.get("provider_key", ["custom"])[0],
        auth_mode=form_data.get("auth_mode", ["manual"])[0],
        connection_label=form_data.get("connection_label", [""])[0] or None,
        status=form_data.get("status", ["connected"])[0],
        config_json=_parse_json_field(form_data.get("config_json", ["{}"])[0]),
        credential_json=_parse_json_field(form_data.get("credential_json", ["{}"])[0]),
    )
    db.commit()
    return templates.TemplateResponse(
        request,
        "partials/action_result.html",
        {
            "result": {
                "id": "settings-connection",
                "status_label": "Saved",
                "status_class": "badge-info",
                "message": f"Saved {form_data.get('channel', ['connection'])[0]} connection.",
            }
        },
    )


@web_router.post("/settings/destinations", response_class=HTMLResponse)
async def settings_destination_action(
    request: Request,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    service = PublishingConnectionService(db)
    service.add_destination(
        channel=form_data.get("channel", [""])[0],
        external_id=form_data.get("external_id", [""])[0],
        destination_type=form_data.get("destination_type", ["account"])[0],
        label=form_data.get("label", [""])[0],
        config_json=_parse_json_field(form_data.get("config_json", ["{}"])[0]),
        activate=form_data.get("activate", ["false"])[0].lower() in {"true", "1", "on", "yes"},
    )
    db.commit()
    return templates.TemplateResponse(
        request,
        "partials/action_result.html",
        {
            "result": {
                "id": "settings-destination",
                "status_label": "Saved",
                "status_class": "badge-info",
                "message": f"Added destination for {form_data.get('channel', ['channel'])[0]}.",
            }
        },
    )


@web_router.post("/settings/destinations/{destination_id}/activate", response_class=HTMLResponse)
async def activate_settings_destination(
    destination_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    PublishingConnectionService(db).set_active_destination(
        form_data.get("channel", [""])[0],
        uuid.UUID(destination_id),
    )
    db.commit()
    return templates.TemplateResponse(
        request,
        "partials/action_result.html",
        {
            "result": {
                "id": destination_id,
                "status_label": "Updated",
                "status_class": "badge-info",
                "message": "Switched active destination.",
            }
        },
    )


@web_router.post("/settings/destinations/{destination_id}/delete", response_class=HTMLResponse)
async def delete_settings_destination(
    destination_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    PublishingConnectionService(db).remove_destination(
        form_data.get("channel", [""])[0],
        uuid.UUID(destination_id),
    )
    db.commit()
    return templates.TemplateResponse(
        request,
        "partials/action_result.html",
        {
            "result": {
                "id": destination_id,
                "status_label": "Removed",
                "status_class": "badge-info",
                "message": "Removed destination.",
            }
        },
    )


@web_router.post("/status/actions", response_class=HTMLResponse)
async def status_action_fragment(
    request: Request,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    action = form_data.get("action", [""])[0]
    result = apply_settings_action(db, action)
    return templates.TemplateResponse(
        request,
        "partials/action_result.html",
        {"result": result},
    )


@web_router.post("/status/connect", response_class=HTMLResponse)
async def status_connect_platform(
    request: Request,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    channel = form_data.get("channel", [""])[0]
    service = PublishingConnectionService(db)

    credential = {}
    config = {}
    label = ""

    if channel == "x":
        credential = {
            "api_key": form_data.get("api_key", [""])[0],
            "api_secret": form_data.get("api_secret", [""])[0],
            "access_token": form_data.get("access_token", [""])[0],
            "access_token_secret": form_data.get("access_token_secret", [""])[0],
        }
        label = "X / Twitter"
    elif channel == "linkedin":
        credential = {
            "access_token": form_data.get("access_token", [""])[0],
        }
        config = {
            "organization_urn": form_data.get("organization_urn", [""])[0],
        }
        label = "LinkedIn"
    elif channel == "instagram":
        credential = {
            "access_token": form_data.get("access_token", [""])[0],
        }
        config = {
            "business_account_id": form_data.get("business_account_id", [""])[0],
        }
        label = "Instagram"
    elif channel == "newsletter":
        credential = {
            "api_key": form_data.get("api_key", [""])[0],
        }
        config = {
            "server_prefix": form_data.get("server_prefix", [""])[0],
            "list_id": form_data.get("list_id", [""])[0],
        }
        label = "Newsletter (Mailchimp)"

    service.upsert_connection(
        channel=channel,
        provider_key=channel,
        auth_mode="manual",
        connection_label=label,
        status="connected",
        config_json=config,
        credential_json=credential,
    )
    db.commit()

    return templates.TemplateResponse(
        request,
        "partials/action_result.html",
        {"result": {
            "id": f"connect-{channel}",
            "status_label": "Connected",
            "status_class": "badge-info",
            "message": f"{label} connected successfully.",
        }},
    )


@web_router.post("/status/disconnect", response_class=HTMLResponse)
async def status_disconnect_platform(
    request: Request,
    db: Session = Depends(get_db),
):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    channel = form_data.get("channel", [""])[0]
    service = PublishingConnectionService(db)
    service.upsert_connection(
        channel=channel,
        provider_key=channel,
        auth_mode="manual",
        connection_label=channel.upper(),
        status="disconnected",
        config_json={},
        credential_json={},
    )
    db.commit()

    return templates.TemplateResponse(
        request,
        "partials/action_result.html",
        {"result": {
            "id": f"disconnect-{channel}",
            "status_label": "Disconnected",
            "status_class": "badge-muted",
            "message": f"{channel.upper()} disconnected.",
        }},
    )


@web_router.get("/login")
def control_room_login(request: Request):
    if not control_room_auth_enabled():
        return RedirectResponse("/control-room/", status_code=303)
    return RedirectResponse(get_cognito_login_url(), status_code=303)


@web_router.get("/auth/callback")
def cognito_callback(request: Request, code: str = ""):
    if not code:
        return RedirectResponse("/control-room/login", status_code=303)
    try:
        tokens = exchange_code_for_tokens(code)
    except Exception:
        return RedirectResponse("/control-room/login", status_code=303)
    session_id = create_session(tokens)
    response = RedirectResponse("/control-room/", status_code=303)
    response.set_cookie(
        CONTROL_ROOM_SESSION_COOKIE,
        session_id,
        httponly=True,
        samesite="lax",
        max_age=30 * 24 * 3600,
    )
    return response


@web_router.get("/logout")
def control_room_logout():
    response = RedirectResponse(get_cognito_logout_url(), status_code=303)
    response.delete_cookie(CONTROL_ROOM_SESSION_COOKIE)
    return response


@web_router.get("/graph", response_class=HTMLResponse)
def graph_view(request: Request, topic: str = "all", db: Session = Depends(get_db)):
    effective_topic = None if topic == "all" else topic
    data = BrainQuery(db).get_graph_data(topic_key=effective_topic)
    nodes = (
        [{"id": str(e.id), "label": e.canonical_name, "group": "entity", "type": e.entity_type} for e in data["entities"]]
        + [{"id": str(k.id), "label": k.title, "group": "knowledge", "type": k.kind} for k in data["knowledge"]]
    )
    links = (
        [{"source": str(e.source_id), "target": str(e.target_id), "relation": e.relation} for e in data["entity_edges"]]
        + [{"source": str(e.source_id), "target": str(e.target_id), "relation": e.relation} for e in data["knowledge_edges"]]
    )
    topics = db.query(TopicProfile).filter(TopicProfile.enabled == True).order_by(TopicProfile.priority.asc()).all()  # noqa: E712
    return templates.TemplateResponse(request, "graph.html", {
        "request": request,
        "nodes_json": json.dumps(nodes),
        "links_json": json.dumps(links),
        "current_topic": topic,
        "topics": topics,
    })


@web_router.get("/graph/data")
def graph_data(topic: str = "all", db: Session = Depends(get_db)):
    effective_topic = None if topic == "all" else topic
    data = BrainQuery(db).get_graph_data(topic_key=effective_topic)
    return {
        "entities": [{"id": str(e.id), "type": e.entity_type, "label": e.canonical_name, "status": e.status} for e in data["entities"]],
        "knowledge": [{"id": str(k.id), "type": k.kind, "label": k.title, "status": k.status} for k in data["knowledge"]],
        "entity_edges": [{"source": str(e.source_id), "target": str(e.target_id), "relation": e.relation} for e in data["entity_edges"]],
        "knowledge_edges": [{"source": str(e.source_id), "target": str(e.target_id), "relation": e.relation} for e in data["knowledge_edges"]],
    }


# ─── Brain Pages ─────────────────────────────────────────────────────

@web_router.get("/brain/", response_class=HTMLResponse)
def brain_overview(request: Request, db: Session = Depends(get_db)):
    entity_count = db.query(sa_func.count(EntityNode.id)).scalar() or 0
    knowledge_count = db.query(sa_func.count(KnowledgeNode.id)).scalar() or 0
    edge_count = db.query(sa_func.count(EntityEdge.id)).scalar() or 0
    source_count = (
        db.query(sa_func.count(KnowledgeNode.id))
        .filter(KnowledgeNode.kind == "reference_content")
        .scalar()
        or 0
    )
    recent_knowledge = (
        db.query(KnowledgeNode)
        .order_by(KnowledgeNode.created_at.desc())
        .limit(8)
        .all()
    )
    topics = db.query(TopicProfile).order_by(TopicProfile.priority.asc()).all()
    sidebar_topics = _brain_sidebar_topics(db)
    return templates.TemplateResponse(request, "brain_overview.html", {
        "request": request,
        "page": "brain_overview",
        "entity_count": entity_count,
        "knowledge_count": knowledge_count,
        "edge_count": edge_count,
        "source_count": source_count,
        "recent_knowledge": recent_knowledge,
        "topics": topics,
        "sidebar_topics": sidebar_topics,
    })


@web_router.get("/brain/graph", response_class=HTMLResponse)
def brain_graph_view(request: Request, topic: str = "all", db: Session = Depends(get_db)):
    effective_topic = None if topic == "all" else topic
    data = BrainQuery(db).get_graph_data(topic_key=effective_topic)
    nodes = (
        [{"id": str(e.id), "label": e.canonical_name, "group": "entity", "type": e.entity_type, "description": e.description or ""} for e in data["entities"]]
        + [{"id": str(k.id), "label": k.title, "group": "knowledge", "type": k.kind, "content": (k.content or "")[:400], "confidence": k.confidence, "trust_score": k.trust_score} for k in data["knowledge"]]
    )
    links = (
        [{"source": str(e.source_id), "target": str(e.target_id), "relation": e.relation} for e in data["entity_edges"]]
        + [{"source": str(e.source_id), "target": str(e.target_id), "relation": e.relation} for e in data["knowledge_edges"]]
    )
    topics = db.query(TopicProfile).filter(TopicProfile.enabled == True).order_by(TopicProfile.priority.asc()).all()  # noqa: E712
    return templates.TemplateResponse(request, "graph.html", {
        "request": request,
        "page": "brain_graph",
        "nodes_json": json.dumps(nodes),
        "links_json": json.dumps(links),
        "current_topic": topic,
        "topics": topics,
        "sidebar_topics": _brain_sidebar_topics(db),
    })


@web_router.get("/brain/knowledge", response_class=HTMLResponse)
def brain_knowledge(request: Request, db: Session = Depends(get_db)):
    kind = request.query_params.get("kind", "")
    status = request.query_params.get("status", "")
    q = db.query(KnowledgeNode)
    if kind:
        q = q.filter(KnowledgeNode.kind == kind)
    if status:
        q = q.filter(KnowledgeNode.status == status)
    nodes = q.order_by(KnowledgeNode.created_at.desc()).limit(200).all()
    # Collect distinct kinds and statuses for filter dropdowns
    all_kinds = [r[0] for r in db.query(KnowledgeNode.kind).distinct().all()]
    all_statuses = [r[0] for r in db.query(KnowledgeNode.status).distinct().all()]
    return templates.TemplateResponse(request, "brain_knowledge.html", {
        "request": request,
        "page": "brain_knowledge",
        "nodes": nodes,
        "filter_kind": kind,
        "filter_status": status,
        "all_kinds": sorted(all_kinds),
        "all_statuses": sorted(all_statuses),
        "sidebar_topics": _brain_sidebar_topics(db),
    })


@web_router.get("/brain/review", response_class=HTMLResponse)
def brain_review(request: Request, db: Session = Depends(get_db)):
    drafts = (
        db.query(DraftVariant)
        .filter(DraftVariant.state == DraftState.MANUAL_READY)
        .order_by(DraftVariant.created_at.desc())
        .limit(50)
        .all()
    )
    # Enrich drafts with job/workflow info
    enriched = []
    for draft in drafts:
        job = db.query(ContentJob).filter(ContentJob.id == draft.content_job_id).first() if draft.content_job_id else None
        wf = db.query(Workflow).filter(Workflow.id == job.workflow_id).first() if job and job.workflow_id else None
        enriched.append({
            "id": str(draft.id),
            "title": wf.name if wf else "Untitled Draft",
            "platform": draft.platform.value if hasattr(draft.platform, "value") else str(draft.platform),
            "pillar": getattr(wf, "pillar", None) or "",
            "mode": wf.mode.value if wf and hasattr(wf.mode, "value") else "",
            "content": (draft.content or "")[:200],
            "created_at": draft.created_at,
        })
    return templates.TemplateResponse(request, "brain_review.html", {
        "request": request,
        "page": "brain_review",
        "drafts": enriched,
        "sidebar_topics": _brain_sidebar_topics(db),
    })


@web_router.get("/brain/sources", response_class=HTMLResponse)
def brain_sources(request: Request, db: Session = Depends(get_db)):
    sources = (
        db.query(KnowledgeNode)
        .filter(KnowledgeNode.kind == "reference_content")
        .order_by(KnowledgeNode.created_at.desc())
        .limit(200)
        .all()
    )
    return templates.TemplateResponse(request, "brain_sources.html", {
        "request": request,
        "page": "brain_sources",
        "sources": sources,
        "sidebar_topics": _brain_sidebar_topics(db),
    })


@web_router.get("/brain/topics", response_class=HTMLResponse)
def brain_topics(request: Request, db: Session = Depends(get_db)):
    topics = db.query(TopicProfile).order_by(TopicProfile.priority.asc()).all()
    # Enrich with counts
    enriched = []
    for topic in topics:
        entity_count = (
            db.query(sa_func.count(EntityNode.id))
            .filter(EntityNode.primary_topic_key == topic.topic_key)
            .scalar()
            or 0
        )
        knowledge_count = (
            db.query(sa_func.count(KnowledgeNode.id))
            .filter(KnowledgeNode.primary_topic_key == topic.topic_key)
            .scalar()
            or 0
        )
        enriched.append({
            "topic": topic,
            "entity_count": entity_count,
            "knowledge_count": knowledge_count,
        })
    return templates.TemplateResponse(request, "brain_topics.html", {
        "request": request,
        "page": "brain_topics",
        "topics": enriched,
        "sidebar_topics": _brain_sidebar_topics(db),
    })


@web_router.get("/brain/topics/{topic_key}", response_class=HTMLResponse)
def brain_topic_detail(request: Request, topic_key: str, db: Session = Depends(get_db)):
    topic = db.query(TopicProfile).filter(TopicProfile.topic_key == topic_key).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    entities = (
        db.query(EntityNode)
        .filter(EntityNode.primary_topic_key == topic_key)
        .order_by(EntityNode.canonical_name)
        .all()
    )
    knowledge = (
        db.query(KnowledgeNode)
        .filter(KnowledgeNode.primary_topic_key == topic_key)
        .order_by(KnowledgeNode.created_at.desc())
        .all()
    )

    # Collect all node IDs to find relevant edges
    entity_ids = {e.id for e in entities}
    knowledge_ids = {k.id for k in knowledge}
    all_ids = entity_ids | knowledge_ids

    entity_edges = (
        db.query(EntityEdge)
        .filter(
            EntityEdge.source_id.in_(all_ids) | EntityEdge.target_id.in_(all_ids)
        )
        .all()
        if all_ids
        else []
    )

    # Build a lookup for entity/knowledge names
    name_lookup = {}
    for e in entities:
        name_lookup[e.id] = e.canonical_name
    for k in knowledge:
        name_lookup[k.id] = k.title

    enriched_edges = []
    for edge in entity_edges:
        enriched_edges.append({
            "source_name": name_lookup.get(edge.source_id, str(edge.source_id)[:8]),
            "target_name": name_lookup.get(edge.target_id, str(edge.target_id)[:8]),
            "relation": edge.relation,
            "confidence": edge.confidence,
        })

    source_count = sum(1 for k in knowledge if k.kind == "reference_content")

    return templates.TemplateResponse(request, "brain_topic_detail.html", {
        "request": request,
        "page": "brain_topic_detail",
        "topic": topic,
        "entities": entities,
        "knowledge": knowledge,
        "edges": enriched_edges,
        "source_count": source_count,
        "sidebar_topics": _brain_sidebar_topics(db),
    })


# ─── Public iCal Feed ────────────────────────────────────────────────

def _ical_escape(text: str) -> str:
    """Escape text for iCal DESCRIPTION/SUMMARY fields."""
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ical_dt(dt: datetime) -> str:
    """Format a datetime as iCal UTC timestamp."""
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y%m%dT%H%M%SZ")


def _ical_date(d: date) -> str:
    """Format a date as iCal DATE value."""
    return d.strftime("%Y%m%d")


@public_router.get("/calendar.ics")
def ical_feed(db: Session = Depends(get_db)):
    today = date.today()
    range_start = today - timedelta(days=7)
    range_end = today + timedelta(days=90)
    range_days = (range_end - range_start).days

    events: list[str] = []

    # --- Recurring calendar rules ---
    all_workflows = {str(wf.id): wf for wf in db.query(Workflow).all()}
    rules = db.query(CalendarRule).filter(CalendarRule.enabled.is_(True)).all()
    for rule in rules:
        wf = all_workflows.get(str(rule.workflow_id))
        wf_name = wf.name if wf else "Workflow"
        platform = wf.platform.value if wf and wf.platform else "content"
        fire_dates = _cron_fire_dates(rule.cron_expression, rule.timezone, range_start, range_days)
        human_label = _cron_human_label(rule.cron_expression)
        for dt in fire_dates:
            uid = f"rule-{rule.id}-{dt.strftime('%Y%m%d')}@ntangible"
            end_dt = dt + timedelta(hours=1)
            events.append(
                f"BEGIN:VEVENT\r\n"
                f"UID:{uid}\r\n"
                f"DTSTART:{_ical_dt(dt)}\r\n"
                f"DTEND:{_ical_dt(end_dt)}\r\n"
                f"SUMMARY:{_ical_escape(f'[{platform.upper()}] {wf_name}')}\r\n"
                f"DESCRIPTION:{_ical_escape(f'Recurring: {human_label}')}\r\n"
                f"END:VEVENT"
            )

    # --- Scheduled / published drafts ---
    drafts = (
        db.query(DraftVariant)
        .filter(
            DraftVariant.state.in_([
                DraftState.MANUAL_READY, DraftState.AUTOMATIC_READY,
                DraftState.SCHEDULED_MANUAL, DraftState.PUBLISHED,
            ])
        )
        .order_by(DraftVariant.created_at.desc())
        .limit(500)
        .all()
    )
    for draft in drafts:
        if draft.scheduled_publish_at:
            dt = draft.scheduled_publish_at
        elif draft.recommended_publish_at:
            dt = draft.recommended_publish_at
        else:
            continue
        if dt.date() < range_start or dt.date() >= range_end:
            continue
        job = db.query(ContentJob).filter(ContentJob.id == draft.content_job_id).first() if draft.content_job_id else None
        wf = all_workflows.get(str(job.workflow_id)) if job and job.workflow_id else None
        title = wf.name if wf else "Scheduled Post"
        platform = draft.platform.value if hasattr(draft.platform, "value") else str(draft.platform)
        state_val = draft.state.value if hasattr(draft.state, "value") else str(draft.state)
        preview = (draft.content[:100] + "...") if draft.content and len(draft.content) > 100 else (draft.content or "")
        end_dt = dt + timedelta(minutes=30)
        uid = f"draft-{draft.id}@ntangible"
        events.append(
            f"BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\n"
            f"DTSTART:{_ical_dt(dt)}\r\n"
            f"DTEND:{_ical_dt(end_dt)}\r\n"
            f"SUMMARY:{_ical_escape(f'[{platform.upper()}] {title}')}\r\n"
            f"DESCRIPTION:{_ical_escape(f'Status: {state_val}\\n{preview}')}\r\n"
            f"END:VEVENT"
        )

    # --- Active campaigns ---
    campaigns = (
        db.query(Campaign)
        .filter(
            Campaign.status == CampaignStatus.ACTIVE,
            Campaign.start_date.isnot(None),
            Campaign.end_date.isnot(None),
            Campaign.start_date <= range_end,
            Campaign.end_date >= range_start,
        )
        .all()
    )
    for camp in campaigns:
        uid = f"campaign-{camp.id}@ntangible"
        end_date = camp.end_date + timedelta(days=1)  # iCal DTEND is exclusive for DATE
        events.append(
            f"BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\n"
            f"DTSTART;VALUE=DATE:{_ical_date(camp.start_date)}\r\n"
            f"DTEND;VALUE=DATE:{_ical_date(end_date)}\r\n"
            f"SUMMARY:{_ical_escape(camp.name)}\r\n"
            f"DESCRIPTION:{_ical_escape(camp.objective[:200] if camp.objective else '')}\r\n"
            f"END:VEVENT"
        )

    body = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//NTangible//Marketing Engine//EN\r\n"
        "X-WR-CALNAME:NTangible Content Schedule\r\n"
        "X-WR-TIMEZONE:America/New_York\r\n"
        + "\r\n".join(events) + ("\r\n" if events else "")
        + "END:VCALENDAR\r\n"
    )

    return PlainTextResponse(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": "inline; filename=calendar.ics"},
    )
