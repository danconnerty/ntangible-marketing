import hashlib
import logging
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.brain import KnowledgeNode
from app.models.review import ContentJob, DraftVariant
from app.models.trigger import TriggerEvent
from app.models.workflow import DraftState, Platform, Workflow
from app.services.brain_query import BrainQuery


logger = logging.getLogger(__name__)

PLATFORM_SCORE_BENCHMARKS: dict[Platform, dict[str, float]] = {
    Platform.X: {"engagement_rate": 0.03, "depth_rate": 0.006, "amplification_rate": 0.004},
    Platform.LINKEDIN: {"engagement_rate": 0.045, "depth_rate": 0.008, "amplification_rate": 0.005},
    Platform.INSTAGRAM: {"engagement_rate": 0.06, "depth_rate": 0.01, "amplification_rate": 0.008},
    Platform.NEWSLETTER: {"engagement_rate": 0.35, "depth_rate": 0.03, "amplification_rate": 0.01},
    Platform.BLOG: {"engagement_rate": 0.025, "depth_rate": 0.01, "amplification_rate": 0.002},
}


def _metric_number(metrics: dict[str, Any], key: str) -> float:
    value = metrics.get(key, 0.0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _extract_engagement_rate_from_dict(metrics: dict[str, Any]) -> float:
    """Extract engagement rate from a raw metrics dict."""
    direct = _metric_number(metrics, "engagement_rate")
    if direct > 0:
        return min(direct, 1.0)

    impressions = _metric_number(metrics, "impressions")
    if impressions <= 0:
        return 0.0

    engagements = _metric_number(metrics, "engagements")
    if engagements > 0:
        return min(engagements / impressions, 1.0)

    interactions = sum(
        _metric_number(metrics, key)
        for key in ("likes", "comments", "shares", "clicks", "saves")
    )
    if interactions <= 0:
        return 0.0
    return min(interactions / impressions, 1.0)


def _extract_engagement_rate_from_metrics(metrics: dict[str, Any]) -> float:
    return _extract_engagement_rate_from_dict(metrics)


def _promotion_recommendation(confidence: float) -> str:
    if confidence >= 0.8:
        return "candidate"
    if confidence >= 0.55:
        return "watch"
    return "manual_only"


def _bounded_ratio(value: float, benchmark: float, *, ceiling: float = 1.5) -> float:
    if benchmark <= 0:
        return 0.0
    return min(max(value / benchmark, 0.0), ceiling) / ceiling


def score_content_metrics(platform: Platform, metrics: dict[str, Any]) -> dict[str, Any]:
    benchmark = PLATFORM_SCORE_BENCHMARKS.get(platform, PLATFORM_SCORE_BENCHMARKS[Platform.LINKEDIN])
    engagement_rate = _extract_engagement_rate_from_metrics(metrics)

    impressions = max(_metric_number(metrics, "impressions"), 1.0)
    depth_actions = sum(_metric_number(metrics, key) for key in ("comments", "clicks", "saves", "replies"))
    amplification_actions = sum(_metric_number(metrics, key) for key in ("shares", "reposts", "retweets", "forwards"))

    if platform == Platform.NEWSLETTER:
        engagement_rate = max(engagement_rate, _metric_number(metrics, "open_rate"))
        depth_rate = _metric_number(metrics, "click_rate")
        amplification_rate = _metric_number(metrics, "forward_rate")
    else:
        depth_rate = depth_actions / impressions
        amplification_rate = amplification_actions / impressions

    score = round(
        (
            _bounded_ratio(engagement_rate, benchmark["engagement_rate"], ceiling=1.75) * 55
            + _bounded_ratio(depth_rate, benchmark["depth_rate"], ceiling=1.5) * 25
            + _bounded_ratio(amplification_rate, benchmark["amplification_rate"], ceiling=1.5) * 20
        ),
        1,
    )
    recycle_recommended = score >= 75.0
    if score >= 85:
        score_label = "excellent"
    elif score >= 75:
        score_label = "strong"
    elif score >= 60:
        score_label = "watch"
    else:
        score_label = "weak"

    return {
        "content_score": score,
        "score_label": score_label,
        "recycle_recommended": recycle_recommended,
        "score_breakdown": {
            "engagement_rate": round(engagement_rate, 4),
            "depth_rate": round(depth_rate, 4),
            "amplification_rate": round(amplification_rate, 4),
        },
    }


def _node_metrics(node: KnowledgeNode) -> dict[str, Any]:
    """Extract the 'metrics' sub-dict from a metric KnowledgeNode's metadata."""
    meta = node.metadata_ or {}
    return meta.get("metrics", meta)


def _node_engagement_rate(node: KnowledgeNode) -> float:
    return _extract_engagement_rate_from_dict(_node_metrics(node))


def calculate_workflow_rollup(
    *,
    drafts: list[DraftVariant],
    publications: list[Any],
    snapshots: list[Any],
    workflow: Workflow | Any,
    platform: Platform,
    trigger_type: str | None,
    window_days: int = 30,
) -> dict[str, Any]:
    total_drafts = len(drafts)
    published_count = sum(1 for draft in drafts if draft.state == DraftState.PUBLISHED)
    rejected_count = sum(1 for draft in drafts if draft.state == DraftState.REJECTED)
    expired_count = sum(1 for draft in drafts if draft.state == DraftState.EXPIRED)

    denominator = total_drafts if total_drafts > 0 else 1
    approval_rate = published_count / denominator
    rejection_rate = rejected_count / denominator
    expiration_rate = expired_count / denominator
    publication_success_rate = len(publications) / denominator

    # snapshots may be KnowledgeNodes or dicts — extract engagement rate accordingly
    engagement_values = []
    content_scores_list = []
    recycle_candidate_count = 0
    for snapshot in snapshots:
        if isinstance(snapshot, KnowledgeNode):
            metrics = _node_metrics(snapshot)
        elif hasattr(snapshot, "metrics"):
            metrics = snapshot.metrics or {}
        else:
            metrics = {}
        er = _extract_engagement_rate_from_dict(metrics)
        if er > 0:
            engagement_values.append(er)
        cs = _metric_number(metrics, "content_score")
        if cs > 0:
            content_scores_list.append(cs)
        if bool(metrics.get("recycle_recommended")):
            recycle_candidate_count += 1

    engagement_percentile = (
        round(sum(engagement_values) / len(engagement_values), 4) if engagement_values else 0.0
    )
    average_content_score = round(sum(content_scores_list) / len(content_scores_list), 1) if content_scores_list else 0.0

    confidence = (
        (publication_success_rate * 0.4)
        + (approval_rate * 0.25)
        + ((1.0 - rejection_rate) * 0.1)
        + ((1.0 - expiration_rate) * 0.05)
        + (engagement_percentile * 0.2)
    )
    if len(publications) < 3:
        confidence *= 0.85
    confidence = round(min(max(confidence, 0.0), 1.0), 4)

    return {
        "workflow_id": str(getattr(workflow, "id")),
        "workflow_name": getattr(workflow, "name", "Unknown Workflow"),
        "workflow_slug": getattr(workflow, "slug", ""),
        "platform": platform.value if isinstance(platform, Platform) else str(platform),
        "trigger_type": trigger_type,
        "window_days": window_days,
        "approval_rate": approval_rate,
        "rejection_rate": rejection_rate,
        "expiration_rate": expiration_rate,
        "publication_success_rate": publication_success_rate,
        "engagement_percentile": engagement_percentile,
        "promotion_confidence": confidence,
        "promotion_recommendation": _promotion_recommendation(confidence),
        "record_count": len(publications),
        "average_content_score": average_content_score,
        "recycle_candidate_count": recycle_candidate_count,
    }


def record_publication(
    db: Session,
    *,
    draft: DraftVariant | KnowledgeNode,
    publish_result: dict[str, Any],
) -> KnowledgeNode | None:
    """Record a publication event as a KnowledgeNode(kind='metric').

    When review_queue already created the publication metric node this function
    is a no-op thin wrapper — it returns None without creating a duplicate.
    If draft is a legacy DraftVariant the function creates a metric node so
    callers that bypass review_queue still get a record.
    """
    if isinstance(draft, KnowledgeNode):
        # review_queue.py already handles metric node creation for brain drafts
        return None

    # Legacy DraftVariant path
    job = db.query(ContentJob).filter(ContentJob.id == draft.content_job_id).first()
    if not isinstance(job, ContentJob):
        logger.warning("Skipping publication record for draft %s: content job missing", draft.id)
        return None

    published_at = draft.published_at or datetime.now(timezone.utc)
    bq = BrainQuery(db)
    node = bq.create_knowledge_node(
        kind="metric",
        title=f"publication:{draft.platform.value}:{draft.id}",
        status="active",
        metadata={
            "metric_type": "publication",
            "draft_variant_id": str(draft.id),
            "content_job_id": str(job.id),
            "workflow_id": str(job.workflow_id),
            "workflow_version_id": str(job.workflow_version_id) if job.workflow_version_id else None,
            "trigger_event_id": str(job.trigger_event_id) if job.trigger_event_id else None,
            "platform": draft.platform.value,
            "platform_post_id": draft.platform_post_id,
            "post_url": draft.post_url,
            "published_at": published_at.isoformat(),
            "publish_result": publish_result,
        },
    )
    return node


def _save_workflow_metric(
    db: Session,
    *,
    workflow_id: uuid.UUID,
    workflow_version_id: uuid.UUID | None,
    rollup: dict[str, Any],
) -> KnowledgeNode:
    """Upsert a workflow metric KnowledgeNode for the given rollup.

    Looks for an existing active node with matching workflow_id, platform,
    trigger_type, and window_days in its metadata. Updates it in-place if
    found, otherwise creates a new one.
    """
    bq = BrainQuery(db)
    platform_val = rollup["platform"]
    trigger_type = rollup["trigger_type"]
    window_days = rollup["window_days"]

    # Try to find an existing metric node for this workflow / platform combo
    existing_nodes = bq.list_knowledge_by_kind("metric", status="active")
    existing: KnowledgeNode | None = None
    for node in existing_nodes:
        meta = node.metadata_ or {}
        if (
            meta.get("metric_type") == "workflow_metric"
            and meta.get("workflow_id") == str(workflow_id)
            and meta.get("platform") == platform_val
            and meta.get("trigger_type") == trigger_type
            and meta.get("window_days") == window_days
        ):
            existing = node
            break

    meta_payload: dict[str, Any] = {
        "metric_type": "workflow_metric",
        "workflow_id": str(workflow_id),
        "workflow_version_id": str(workflow_version_id) if workflow_version_id else None,
        "platform": platform_val,
        "trigger_type": trigger_type,
        "window_days": window_days,
        "approval_rate": rollup["approval_rate"],
        "rejection_rate": rollup["rejection_rate"],
        "expiration_rate": rollup["expiration_rate"],
        "publication_success_rate": rollup["publication_success_rate"],
        "engagement_percentile": rollup["engagement_percentile"],
        "promotion_confidence": rollup["promotion_confidence"],
        "record_count": rollup["record_count"],
    }

    if existing is None:
        existing = bq.create_knowledge_node(
            kind="metric",
            title=f"workflow_metric:{workflow_id}:{platform_val}",
            status="active",
            metadata=meta_payload,
        )
    else:
        existing.metadata_ = meta_payload
        db.flush()

    return existing


def _list_publication_metric_nodes(
    db: Session,
    *,
    platform: Platform | None = None,
    cutoff: datetime | None = None,
) -> list[KnowledgeNode]:
    """Return publication metric KnowledgeNodes, optionally filtered."""
    q = db.query(KnowledgeNode).filter(
        KnowledgeNode.kind == "metric",
        KnowledgeNode.status == "active",
    )
    nodes = q.all()
    result = []
    for node in nodes:
        meta = node.metadata_ or {}
        if meta.get("metric_type") != "publication":
            continue
        if platform is not None and meta.get("platform") != platform.value:
            continue
        if cutoff is not None:
            pub_at_str = meta.get("published_at")
            if pub_at_str:
                try:
                    pub_at = datetime.fromisoformat(pub_at_str)
                    if pub_at.tzinfo is None:
                        pub_at = pub_at.replace(tzinfo=timezone.utc)
                    if pub_at < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass
        result.append(node)
    return result


def _list_analytics_snapshot_nodes(
    db: Session,
    *,
    publication_node_ids: list[str] | None = None,
) -> list[KnowledgeNode]:
    """Return analytics_snapshot metric KnowledgeNodes."""
    q = db.query(KnowledgeNode).filter(
        KnowledgeNode.kind == "metric",
        KnowledgeNode.status == "active",
    )
    nodes = q.all()
    result = []
    for node in nodes:
        meta = node.metadata_ or {}
        if meta.get("metric_type") != "analytics_snapshot":
            continue
        if publication_node_ids is not None and meta.get("publication_node_id") not in publication_node_ids:
            continue
        result.append(node)
    return result


def ingest_analytics_snapshot(
    db: Session,
    *,
    publication_record_id: uuid.UUID,
    metrics: dict[str, Any],
) -> KnowledgeNode:
    """Ingest analytics metrics for a published post.

    Looks up the publication metric node by its legacy id stored in metadata,
    enriches the metrics with a content score, then creates an analytics_snapshot
    metric KnowledgeNode.
    """
    # Find the publication metric node matching this id
    pub_nodes = _list_publication_metric_nodes(db)
    publication_node: KnowledgeNode | None = None
    for node in pub_nodes:
        meta = node.metadata_ or {}
        # Support both a stored node id and a legacy draft_variant_id lookup
        if str(node.id) == str(publication_record_id):
            publication_node = node
            break

    platform_val: str = "linkedin"
    workflow_id: str | None = None
    workflow_version_id: str | None = None

    if publication_node is not None:
        pub_meta = publication_node.metadata_ or {}
        platform_val = pub_meta.get("platform", "linkedin")
        workflow_id = pub_meta.get("workflow_id")
        workflow_version_id = pub_meta.get("workflow_version_id")
    else:
        logger.warning(
            "Publication metric node %s not found; creating analytics snapshot anyway",
            publication_record_id,
        )

    try:
        platform_enum = Platform(platform_val)
    except ValueError:
        platform_enum = Platform.LINKEDIN

    enriched_metrics = {
        **metrics,
        **score_content_metrics(platform_enum, metrics),
    }

    bq = BrainQuery(db)
    snapshot_node = bq.create_knowledge_node(
        kind="metric",
        title=f"analytics_snapshot:{publication_record_id}",
        status="active",
        metadata={
            "metric_type": "analytics_snapshot",
            "publication_node_id": str(publication_record_id),
            "platform": platform_val,
            "workflow_id": workflow_id,
            "workflow_version_id": workflow_version_id,
            "metrics": enriched_metrics,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Recompute workflow metrics if we have a workflow
    if workflow_id is not None:
        try:
            wf_uuid = uuid.UUID(workflow_id)
            wf_ver_uuid = uuid.UUID(workflow_version_id) if workflow_version_id else None
            workflow = db.query(Workflow).filter(Workflow.id == wf_uuid).first()
            if workflow is not None:
                rollup = compute_workflow_metrics(
                    db,
                    workflow_id=wf_uuid,
                    workflow_version_id=wf_ver_uuid,
                    platform=platform_enum,
                )
                _save_workflow_metric(
                    db,
                    workflow_id=wf_uuid,
                    workflow_version_id=wf_ver_uuid,
                    rollup=rollup,
                )
        except Exception:
            logger.exception("Failed to recompute workflow metrics after analytics ingest")

    return snapshot_node


def _within_window(value: datetime | None, cutoff: datetime) -> bool:
    if value is None:
        return True
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value >= cutoff


def _resolve_platform(platform: str | Platform | None) -> Platform | None:
    if platform is None or platform == "":
        return None
    if isinstance(platform, Platform):
        return platform
    return Platform(platform)


def _resolve_trigger_type(job_ids: list[uuid.UUID], db: Session) -> str | None:
    if not job_ids:
        return None
    jobs = db.query(ContentJob).filter(ContentJob.id.in_(job_ids)).all()
    trigger_ids = [job.trigger_event_id for job in jobs if job.trigger_event_id]
    if not trigger_ids:
        return None
    triggers = db.query(TriggerEvent).filter(TriggerEvent.id.in_(trigger_ids)).all()
    if not triggers:
        return None

    counts: dict[str, int] = {}
    for trigger in triggers:
        key = trigger.trigger_type.value
        counts[key] = counts.get(key, 0) + 1
    return max(counts, key=counts.get)


def compute_workflow_metrics(
    db: Session,
    *,
    workflow_id: uuid.UUID,
    workflow_version_id: uuid.UUID | None = None,
    platform: Platform | None = None,
    trigger_type: str | None = None,
    days: int = 30,
) -> dict[str, Any]:
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if workflow is None:
        raise ValueError(f"Workflow {workflow_id} not found")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    jobs = db.query(ContentJob).filter(ContentJob.workflow_id == workflow_id).all()
    if workflow_version_id is not None:
        jobs = [job for job in jobs if job.workflow_version_id == workflow_version_id]
    jobs = [job for job in jobs if _within_window(getattr(job, "created_at", None), cutoff)]
    job_ids = [job.id for job in jobs]

    drafts = db.query(DraftVariant).filter(DraftVariant.content_job_id.in_(job_ids)).all() if job_ids else []
    if platform is not None:
        drafts = [draft for draft in drafts if draft.platform == platform]

    # Gather publication metric nodes for this workflow
    pub_nodes = _list_publication_metric_nodes(db, platform=platform, cutoff=cutoff)
    pub_nodes_for_workflow = [
        n for n in pub_nodes
        if (n.metadata_ or {}).get("workflow_id") == str(workflow_id)
    ]
    if workflow_version_id is not None:
        pub_nodes_for_workflow = [
            n for n in pub_nodes_for_workflow
            if (n.metadata_ or {}).get("workflow_version_id") == str(workflow_version_id)
        ]

    # Gather analytics snapshot nodes for these publications
    pub_node_ids = [str(n.id) for n in pub_nodes_for_workflow]
    snap_nodes = _list_analytics_snapshot_nodes(db, publication_node_ids=pub_node_ids)

    # Filter snapshot nodes by cutoff
    filtered_snaps = []
    for node in snap_nodes:
        meta = node.metadata_ or {}
        captured_str = meta.get("captured_at")
        if captured_str:
            try:
                captured = datetime.fromisoformat(captured_str)
                if captured.tzinfo is None:
                    captured = captured.replace(tzinfo=timezone.utc)
                if captured >= cutoff:
                    filtered_snaps.append(node)
            except (ValueError, TypeError):
                filtered_snaps.append(node)
        else:
            filtered_snaps.append(node)

    resolved_platform = platform or workflow.platform
    resolved_trigger_type = trigger_type or _resolve_trigger_type(job_ids, db)

    return calculate_workflow_rollup(
        drafts=drafts,
        publications=pub_nodes_for_workflow,
        snapshots=filtered_snaps,
        workflow=workflow,
        platform=resolved_platform,
        trigger_type=resolved_trigger_type,
        window_days=days,
    )


def _aggregate_platform_metrics(workflow_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for metric in workflow_metrics:
        buckets.setdefault(metric["platform"], []).append(metric)

    results = []
    for platform, items in sorted(buckets.items()):
        count = len(items)
        results.append(
            {
                "platform": platform,
                "promotion_confidence": round(sum(item["promotion_confidence"] for item in items) / count, 4),
                "publication_success_rate": round(
                    sum(item["publication_success_rate"] for item in items) / count,
                    4,
                ),
                "approval_rate": round(sum(item["approval_rate"] for item in items) / count, 4),
                "engagement_percentile": round(
                    sum(item["engagement_percentile"] for item in items) / count,
                    4,
                ),
                "record_count": sum(item["record_count"] for item in items),
                "average_content_score": round(sum(item["average_content_score"] for item in items) / count, 1),
                "recycle_candidate_count": sum(item["recycle_candidate_count"] for item in items),
            }
        )
    return results


def _aggregate_dashboard_summary(workflow_metrics: list[dict[str, Any]], days: int) -> dict[str, Any]:
    if not workflow_metrics:
        return {
            "window_days": days,
            "promotion_confidence": 0.0,
            "publication_success_rate": 0.0,
            "approval_rate": 0.0,
            "rejection_rate": 0.0,
            "expiration_rate": 0.0,
            "engagement_percentile": 0.0,
            "record_count": 0,
            "workflow_count": 0,
            "promotion_recommendation": "manual_only",
            "average_content_score": 0.0,
            "recycle_candidate_count": 0,
        }

    count = len(workflow_metrics)
    promotion_confidence = round(sum(item["promotion_confidence"] for item in workflow_metrics) / count, 4)
    return {
        "window_days": days,
        "promotion_confidence": promotion_confidence,
        "publication_success_rate": round(
            sum(item["publication_success_rate"] for item in workflow_metrics) / count,
            4,
        ),
        "approval_rate": round(sum(item["approval_rate"] for item in workflow_metrics) / count, 4),
        "rejection_rate": round(sum(item["rejection_rate"] for item in workflow_metrics) / count, 4),
        "expiration_rate": round(sum(item["expiration_rate"] for item in workflow_metrics) / count, 4),
        "engagement_percentile": round(
            sum(item["engagement_percentile"] for item in workflow_metrics) / count,
            4,
        ),
        "record_count": sum(item["record_count"] for item in workflow_metrics),
        "workflow_count": count,
        "promotion_recommendation": _promotion_recommendation(promotion_confidence),
        "average_content_score": round(sum(item["average_content_score"] for item in workflow_metrics) / count, 1),
        "recycle_candidate_count": sum(item["recycle_candidate_count"] for item in workflow_metrics),
    }


def list_recycle_candidates(
    db: Session,
    *,
    platform: str | Platform | None = None,
    days: int = 90,
    limit: int = 25,
) -> list[dict[str, Any]]:
    resolved_platform = _resolve_platform(platform)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    pub_nodes = _list_publication_metric_nodes(db, platform=resolved_platform, cutoff=cutoff)
    if not pub_nodes:
        return []

    pub_node_ids = [str(n.id) for n in pub_nodes]
    snap_nodes = _list_analytics_snapshot_nodes(db, publication_node_ids=pub_node_ids)

    # Build a mapping: publication_node_id -> latest snapshot node
    latest_snap_by_pub: dict[str, KnowledgeNode] = {}
    for node in snap_nodes:
        meta = node.metadata_ or {}
        pub_id = meta.get("publication_node_id", "")
        if pub_id not in latest_snap_by_pub:
            latest_snap_by_pub[pub_id] = node

    # Gather related drafts and workflows
    draft_ids: list[uuid.UUID] = []
    workflow_ids: list[uuid.UUID] = []
    for node in pub_nodes:
        meta = node.metadata_ or {}
        try:
            draft_ids.append(uuid.UUID(meta["draft_variant_id"]))
        except (KeyError, ValueError):
            pass
        try:
            workflow_ids.append(uuid.UUID(meta["workflow_id"]))
        except (KeyError, ValueError):
            pass

    drafts = db.query(DraftVariant).filter(DraftVariant.id.in_(draft_ids)).all() if draft_ids else []
    workflows = db.query(Workflow).filter(Workflow.id.in_(workflow_ids)).all() if workflow_ids else []
    drafts_by_id = {str(d.id): d for d in drafts}
    workflows_by_id = {str(w.id): w for w in workflows}

    candidates: list[dict[str, Any]] = []
    for pub_node in pub_nodes:
        pub_meta = pub_node.metadata_ or {}
        snap_node = latest_snap_by_pub.get(str(pub_node.id))
        if snap_node is None:
            continue
        snap_metrics = _node_metrics(snap_node)
        score = _metric_number(snap_metrics, "content_score")
        if score < 75:
            continue
        draft = drafts_by_id.get(pub_meta.get("draft_variant_id", ""))
        workflow = workflows_by_id.get(pub_meta.get("workflow_id", ""))
        content = draft.content if draft else ""
        candidates.append(
            {
                "publication_id": str(pub_node.id),
                "draft_variant_id": pub_meta.get("draft_variant_id", ""),
                "platform": pub_meta.get("platform", ""),
                "workflow_name": workflow.name if workflow is not None else "Unknown Workflow",
                "workflow_slug": workflow.slug if workflow is not None else "",
                "content_preview": (content[:180] + "…") if content and len(content) > 180 else content,
                "content_score": score,
                "score_label": snap_metrics.get("score_label"),
                "recycle_recommended": bool(snap_metrics.get("recycle_recommended")),
                "published_at": pub_meta.get("published_at"),
            }
        )

    candidates.sort(key=lambda item: (item["content_score"], item["published_at"] or ""), reverse=True)
    return candidates[:limit]


def build_analytics_summary(
    db: Session,
    *,
    platform: str | Platform | None = None,
    workflow_slug: str | None = None,
    days: int = 30,
) -> dict[str, Any]:
    resolved_platform = _resolve_platform(platform)

    workflow_query = db.query(Workflow).filter(Workflow.enabled == True)
    if resolved_platform is not None:
        workflow_query = workflow_query.filter(Workflow.platform == resolved_platform)
    if workflow_slug:
        workflow_query = workflow_query.filter(Workflow.slug == workflow_slug)
    workflows = workflow_query.order_by(Workflow.name.asc()).all()

    workflow_metrics = []
    for workflow in workflows:
        rollup = compute_workflow_metrics(
            db,
            workflow_id=workflow.id,
            workflow_version_id=workflow.active_version_id,
            platform=resolved_platform or workflow.platform,
            days=days,
        )
        workflow_metrics.append(rollup)
        _save_workflow_metric(
            db,
            workflow_id=workflow.id,
            workflow_version_id=workflow.active_version_id,
            rollup=rollup,
        )

    return {
        "summary": _aggregate_dashboard_summary(workflow_metrics, days),
        "workflow_metrics": workflow_metrics,
        "platform_metrics": _aggregate_platform_metrics(workflow_metrics),
        "recycle_candidates": list_recycle_candidates(
            db,
            platform=resolved_platform,
            days=max(days, 30),
        ),
        "filters": {
            "platform": resolved_platform.value if resolved_platform else None,
            "workflow_slug": workflow_slug,
            "days": days,
        },
    }


def get_publication_analytics_detail(
    db: Session,
    incoming_publication_id: uuid.UUID,
) -> dict[str, Any] | None:
    pub_node = db.query(KnowledgeNode).filter(KnowledgeNode.id == incoming_publication_id).first()
    if pub_node is None:
        return None
    pub_meta = pub_node.metadata_ or {}
    if pub_meta.get("metric_type") != "publication":
        return None

    snap_nodes = _list_analytics_snapshot_nodes(db, publication_node_ids=[str(pub_node.id)])
    return {
        "publication": {
            "id": str(pub_node.id),
            "draft_variant_id": pub_meta.get("draft_variant_id"),
            "content_job_id": pub_meta.get("content_job_id"),
            "workflow_id": pub_meta.get("workflow_id"),
            "workflow_version_id": pub_meta.get("workflow_version_id"),
            "platform": pub_meta.get("platform"),
            "platform_post_id": pub_meta.get("platform_post_id"),
            "post_url": pub_meta.get("post_url"),
            "published_at": pub_meta.get("published_at"),
            "publish_result": pub_meta.get("publish_result"),
        },
        "snapshots": [
            {
                "id": str(sn.id),
                "captured_at": (sn.metadata_ or {}).get("captured_at"),
                "metrics": _node_metrics(sn),
            }
            for sn in snap_nodes
        ],
    }


def _simulate_content_score(draft: DraftVariant) -> dict[str, Any]:
    """Generate a deterministic simulated score for drafts without real analytics.

    Uses content quality signals: length, hashtag count, media presence,
    question/CTA patterns, and platform-appropriate formatting.
    """
    content = draft.content or ""
    hashtags = draft.hashtags or []

    # Deterministic seed from draft id so repeated calls return same score
    seed = int(hashlib.md5(str(draft.id).encode()).hexdigest()[:8], 16) % 100

    # --- Content length score (0-20) ---
    char_count = len(content)
    platform_ideal = {
        Platform.X: (80, 250),
        Platform.LINKEDIN: (200, 1200),
        Platform.INSTAGRAM: (100, 800),
        Platform.NEWSLETTER: (500, 3000),
        Platform.BLOG: (800, 5000),
    }
    lo, hi = platform_ideal.get(draft.platform, (100, 1000))
    if lo <= char_count <= hi:
        length_score = 20.0
    elif char_count < lo:
        length_score = max(5.0, 20.0 * (char_count / lo))
    else:
        length_score = max(10.0, 20.0 * (1 - min((char_count - hi) / hi, 0.5)))

    # --- Hashtag score (0-10) ---
    tag_count = len(hashtags)
    ideal_tags = {Platform.X: 2, Platform.LINKEDIN: 3, Platform.INSTAGRAM: 8, Platform.NEWSLETTER: 0, Platform.BLOG: 0}
    ideal = ideal_tags.get(draft.platform, 2)
    if ideal == 0:
        hashtag_score = 10.0 if tag_count == 0 else max(5.0, 10.0 - tag_count)
    else:
        hashtag_score = max(0.0, 10.0 - abs(tag_count - ideal) * 2.0)

    # --- CTA / question hook (0-15) ---
    has_question = bool(re.search(r"\?", content))
    has_cta = bool(re.search(r"(check out|learn more|sign up|subscribe|click|visit|join|get started|book|schedule)", content, re.IGNORECASE))
    hook_score = (7.5 if has_question else 0.0) + (7.5 if has_cta else 0.0)

    # --- Media indicator (0-10) ---
    has_media = bool(re.search(r"(https?://\S+\.(jpg|png|gif|mp4|webp)|\[image\]|\[video\]|media_url)", content, re.IGNORECASE))
    media_score = 10.0 if has_media else 3.0

    # --- Deterministic noise from seed to vary scores (0-15) ---
    noise = (seed / 100.0) * 15.0

    raw = length_score + hashtag_score + hook_score + media_score + noise
    # Scale to 0-100 range (max possible raw ~ 70)
    score = round(min(max(raw * (100.0 / 70.0), 5.0), 95.0), 1)

    recycle_recommended = score >= 75.0
    if score >= 85:
        score_label = "excellent"
    elif score >= 75:
        score_label = "strong"
    elif score >= 60:
        score_label = "watch"
    else:
        score_label = "weak"

    return {
        "content_score": score,
        "score_label": score_label,
        "recycle_recommended": recycle_recommended,
        "score_breakdown": {
            "length_score": round(length_score, 1),
            "hashtag_score": round(hashtag_score, 1),
            "hook_score": round(hook_score, 1),
            "media_score": round(media_score, 1),
            "noise": round(noise, 1),
        },
    }


def generate_weekly_digest(
    db: Session,
    *,
    reference_date: datetime | None = None,
) -> dict[str, Any]:
    """Build a weekly analytics digest covering the last 7 days.

    Returns a dict with top_performers, underperformers, platform_breakdown,
    intent_split, and recommendations.
    """
    now = reference_date or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)

    # Gather all publication metric nodes from the last 7 days
    pub_nodes = _list_publication_metric_nodes(db, cutoff=cutoff)

    if not pub_nodes:
        return _empty_digest(now, cutoff)

    pub_node_ids = [str(n.id) for n in pub_nodes]

    # Fetch related analytics snapshot nodes
    snap_nodes = _list_analytics_snapshot_nodes(db, publication_node_ids=pub_node_ids)
    latest_snap: dict[str, KnowledgeNode] = {}
    for snap in snap_nodes:
        pub_id = (snap.metadata_ or {}).get("publication_node_id", "")
        if pub_id not in latest_snap:
            latest_snap[pub_id] = snap

    # Fetch related DraftVariants for content preview and intent
    draft_ids: list[uuid.UUID] = []
    for node in pub_nodes:
        meta = node.metadata_ or {}
        try:
            draft_ids.append(uuid.UUID(meta["draft_variant_id"]))
        except (KeyError, ValueError):
            pass

    drafts = db.query(DraftVariant).filter(DraftVariant.id.in_(draft_ids)).all() if draft_ids else []
    drafts_by_id = {str(d.id): d for d in drafts}

    # Also look for draft metric nodes for drafts without publication analytics
    draft_snap_nodes = _list_analytics_snapshot_nodes(db)
    draft_snaps_by_draft: dict[str, KnowledgeNode] = {}
    for ds in draft_snap_nodes:
        meta = ds.metadata_ or {}
        draft_id = meta.get("draft_variant_id", "")
        if draft_id and draft_id not in draft_snaps_by_draft:
            draft_snaps_by_draft[draft_id] = ds

    # Build scored post entries
    scored_posts: list[dict[str, Any]] = []
    for pub_node in pub_nodes:
        pub_meta = pub_node.metadata_ or {}
        draft_id_str = pub_meta.get("draft_variant_id", "")
        draft = drafts_by_id.get(draft_id_str)
        content = draft.content if draft else ""
        intent = draft.intent if draft else "brand"

        try:
            platform_enum = Platform(pub_meta.get("platform", "linkedin"))
        except ValueError:
            platform_enum = Platform.LINKEDIN

        # Find score -- prefer publication analytics snapshot, fall back to draft snapshot
        score = 0.0
        score_label = "unknown"
        snap = latest_snap.get(str(pub_node.id))
        if snap is not None:
            metrics = _node_metrics(snap)
            score = _metric_number(metrics, "content_score")
            score_label = metrics.get("score_label", "unknown")
            if score == 0.0:
                scored_result = score_content_metrics(platform_enum, metrics)
                score = scored_result["content_score"]
                score_label = scored_result["score_label"]
        elif draft_id_str in draft_snaps_by_draft:
            ds_metrics = _node_metrics(draft_snaps_by_draft[draft_id_str])
            score = _metric_number(ds_metrics, "content_score")
            score_label = ds_metrics.get("score_label", "unknown")

        # If still no score, simulate
        if score == 0.0 and draft is not None:
            sim = _simulate_content_score(draft)
            score = sim["content_score"]
            score_label = sim["score_label"]

        published_at = pub_meta.get("published_at")
        scored_posts.append({
            "publication_id": str(pub_node.id),
            "draft_variant_id": draft_id_str,
            "platform": pub_meta.get("platform", ""),
            "intent": intent,
            "content_preview": (content[:160] + "...") if len(content) > 160 else content,
            "content_score": score,
            "score_label": score_label,
            "recycle_recommended": score >= 75.0,
            "published_at": published_at,
        })

    scored_posts.sort(key=lambda x: x["content_score"], reverse=True)

    # Top and bottom performers
    top_performers = scored_posts[:5]
    underperformers = list(reversed(scored_posts[-5:])) if len(scored_posts) >= 5 else list(reversed(scored_posts))
    # Remove overlap if fewer than 10 total posts
    if len(scored_posts) < 10:
        top_ids = {p["publication_id"] for p in top_performers}
        underperformers = [p for p in underperformers if p["publication_id"] not in top_ids]

    # Add diagnosis to underperformers
    for post in underperformers:
        post["diagnosis"] = _diagnose_underperformer(post)

    # Platform breakdown
    platform_buckets: dict[str, list[dict[str, Any]]] = {}
    for post in scored_posts:
        platform_buckets.setdefault(post["platform"], []).append(post)

    platform_breakdown = []
    for plat, posts in sorted(platform_buckets.items()):
        scores = [p["content_score"] for p in posts]
        recycle_count = sum(1 for p in posts if p["recycle_recommended"])
        platform_breakdown.append({
            "platform": plat,
            "post_count": len(posts),
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "max_score": max(scores) if scores else 0.0,
            "min_score": min(scores) if scores else 0.0,
            "recycle_candidates": recycle_count,
        })

    # Intent split
    intent_counter: Counter = Counter()
    for post in scored_posts:
        intent_counter[post["intent"]] += 1
    total_posts = len(scored_posts)
    intent_split = {
        intent: round((count / total_posts) * 100, 1)
        for intent, count in intent_counter.most_common()
    }

    # Recommendations
    recommendations = _build_digest_recommendations(
        scored_posts=scored_posts,
        platform_breakdown=platform_breakdown,
        intent_split=intent_split,
    )

    return {
        "period_start": cutoff.isoformat(),
        "period_end": now.isoformat(),
        "total_posts": total_posts,
        "avg_score": round(sum(p["content_score"] for p in scored_posts) / total_posts, 1) if total_posts else 0.0,
        "top_performers": top_performers,
        "underperformers": underperformers,
        "platform_breakdown": platform_breakdown,
        "intent_split": intent_split,
        "recommendations": recommendations,
    }


def _empty_digest(now: datetime, cutoff: datetime) -> dict[str, Any]:
    return {
        "period_start": cutoff.isoformat(),
        "period_end": now.isoformat(),
        "total_posts": 0,
        "avg_score": 0.0,
        "top_performers": [],
        "underperformers": [],
        "platform_breakdown": [],
        "intent_split": {},
        "recommendations": ["No posts published this week. Consider scheduling content to maintain consistency."],
    }


def _diagnose_underperformer(post: dict[str, Any]) -> str:
    score = post["content_score"]
    platform = post["platform"]
    preview = post["content_preview"]

    issues = []
    if score < 30:
        issues.append("Very low engagement signals")
    elif score < 50:
        issues.append("Below-average engagement")

    if len(preview) < 60:
        issues.append("Content may be too short for the platform")
    if not re.search(r"\?", preview):
        issues.append("No question hook to drive interaction")
    if not re.search(r"(https?://|link|click|learn more)", preview, re.IGNORECASE):
        issues.append("Missing CTA or link")
    if platform in ("instagram", "x") and "#" not in preview:
        issues.append("No hashtags for discoverability")

    return "; ".join(issues) if issues else "Review content angle and posting time"


def _build_digest_recommendations(
    *,
    scored_posts: list[dict[str, Any]],
    platform_breakdown: list[dict[str, Any]],
    intent_split: dict[str, float],
) -> list[str]:
    recommendations: list[str] = []

    if not scored_posts:
        return ["No data to generate recommendations."]

    # Overall score analysis
    avg_score = sum(p["content_score"] for p in scored_posts) / len(scored_posts)
    if avg_score >= 75:
        recommendations.append(
            f"Strong week overall (avg score {avg_score:.1f}). "
            "Continue current content strategy."
        )
    elif avg_score >= 55:
        recommendations.append(
            f"Average performance (avg score {avg_score:.1f}). "
            "Experiment with stronger hooks and CTAs to boost engagement."
        )
    else:
        recommendations.append(
            f"Below-target performance (avg score {avg_score:.1f}). "
            "Consider revising content angles, testing different formats, or adjusting posting times."
        )

    # Platform-specific insights
    for plat in platform_breakdown:
        if plat["avg_score"] < 50 and plat["post_count"] >= 2:
            recommendations.append(
                f"{plat['platform'].upper()} is underperforming (avg {plat['avg_score']:.1f}). "
                "Review platform-specific best practices and benchmark content."
            )
        if plat["post_count"] == 1:
            recommendations.append(
                f"Only 1 post on {plat['platform'].upper()} this week. "
                "Increase frequency for better audience reach."
            )

    # Intent balance
    brand_pct = intent_split.get("brand", 0.0)
    partner_pct = intent_split.get("partner", 0.0)
    revenue_pct = intent_split.get("revenue", 0.0)
    if brand_pct > 70:
        recommendations.append(
            f"Content is {brand_pct:.0f}% brand-focused. "
            "Add more partner or revenue content for a balanced mix."
        )
    if revenue_pct > 50:
        recommendations.append(
            f"Revenue content at {revenue_pct:.0f}%. "
            "Balance with educational/brand content to avoid audience fatigue."
        )
    if partner_pct == 0 and len(scored_posts) >= 3:
        recommendations.append(
            "No partner content published this week. "
            "Partner posts can extend reach through co-promotion."
        )

    # Recycle candidates
    recycle_count = sum(1 for p in scored_posts if p["recycle_recommended"])
    if recycle_count > 0:
        recommendations.append(
            f"{recycle_count} post(s) scored 75+ and are flagged for repurposing. "
            "Adapt top performers for other platforms."
        )

    # A/B insight: question hooks vs no question hooks
    with_question = [p for p in scored_posts if "?" in p["content_preview"]]
    without_question = [p for p in scored_posts if "?" not in p["content_preview"]]
    if len(with_question) >= 2 and len(without_question) >= 2:
        avg_q = sum(p["content_score"] for p in with_question) / len(with_question)
        avg_nq = sum(p["content_score"] for p in without_question) / len(without_question)
        if avg_q > avg_nq + 5:
            recommendations.append(
                f"Posts with question hooks scored {avg_q:.1f} vs {avg_nq:.1f} without. "
                "Lean into question-based openers."
            )
        elif avg_nq > avg_q + 5:
            recommendations.append(
                f"Statement-led posts scored {avg_nq:.1f} vs {avg_q:.1f} for questions. "
                "Direct statements are resonating better this week."
            )

    return recommendations[:8]  # Cap at 8 recommendations


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def build_summary(self) -> dict[str, Any]:
        dashboard = build_analytics_summary(self.db)
        return {
            "totals": {
                "published": dashboard["summary"]["record_count"],
                "rejected": round(dashboard["summary"]["rejection_rate"] * max(dashboard["summary"]["workflow_count"], 1), 0),
                "expired": round(dashboard["summary"]["expiration_rate"] * max(dashboard["summary"]["workflow_count"], 1), 0),
            },
            "workflows": [
                {
                    "workflow_id": row["workflow_id"],
                    "workflow_name": row["workflow_name"],
                    "workflow_slug": row["workflow_slug"],
                    "platform": row["platform"],
                    "total_generated": row["record_count"],
                    "publish_rate": row["publication_success_rate"],
                    "approval_rate": row["approval_rate"],
                    "confidence_score": row["promotion_confidence"],
                }
                for row in dashboard["workflow_metrics"]
            ],
        }

    def capture_snapshots(self) -> list[KnowledgeNode]:
        """Capture workflow metric snapshots as KnowledgeNodes."""
        dashboard = build_analytics_summary(self.db)
        bq = BrainQuery(self.db)
        captured_at = datetime.now(timezone.utc).isoformat()
        snapshots: list[KnowledgeNode] = []
        for row in dashboard["workflow_metrics"]:
            node = bq.create_knowledge_node(
                kind="metric",
                title=f"workflow_snapshot:{row['workflow_id']}:{row['platform']}",
                status="active",
                metadata={
                    "metric_type": "workflow_analytics_snapshot",
                    "workflow_id": row["workflow_id"],
                    "workflow_name": row["workflow_name"],
                    "platform": row["platform"],
                    "total_generated": row["record_count"],
                    "total_published": round(row["publication_success_rate"] * row["record_count"]),
                    "total_rejected": round(row["rejection_rate"] * max(row["record_count"], 1)),
                    "total_expired": round(row["expiration_rate"] * max(row["record_count"], 1)),
                    "total_failed": 0,
                    "approval_rate": row["approval_rate"],
                    "publish_rate": row["publication_success_rate"],
                    "confidence_score": row["promotion_confidence"],
                    "captured_at": captured_at,
                },
            )
            snapshots.append(node)
        return snapshots

    def record_draft_metrics(self, draft_id: uuid.UUID, metrics: dict[str, Any]) -> KnowledgeNode:
        """Record metrics for a draft as a KnowledgeNode(kind='metric')."""
        draft = self.db.query(DraftVariant).filter(DraftVariant.id == draft_id).first()
        if draft is None:
            raise ValueError("Draft not found")
        bq = BrainQuery(self.db)
        node = bq.create_knowledge_node(
            kind="metric",
            title=f"draft_metric:{draft_id}",
            status="active",
            metadata={
                "metric_type": "draft_analytics_snapshot",
                "draft_variant_id": str(draft.id),
                "platform": draft.platform.value,
                "metrics": metrics,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return node

    def compute_content_score(self, draft_id: uuid.UUID) -> dict[str, Any]:
        """Look up a draft's publication/analytics and compute a 0-100 score.

        If real analytics snapshot nodes exist, scores from the latest one.
        Otherwise, generates a simulated score based on content quality signals
        (content length, hashtag count, has media, etc.) for mock publishers.
        """
        draft = self.db.query(DraftVariant).filter(DraftVariant.id == draft_id).first()
        if draft is None:
            raise ValueError(f"Draft {draft_id} not found")

        # Find a publication metric node for this draft
        pub_nodes = _list_publication_metric_nodes(self.db)
        pub_node: KnowledgeNode | None = None
        for node in pub_nodes:
            if (node.metadata_ or {}).get("draft_variant_id") == str(draft_id):
                pub_node = node
                break

        latest_snap_node: KnowledgeNode | None = None
        if pub_node is not None:
            snap_nodes = _list_analytics_snapshot_nodes(
                self.db, publication_node_ids=[str(pub_node.id)]
            )
            if snap_nodes:
                latest_snap_node = snap_nodes[0]

        if latest_snap_node is not None:
            metrics = _node_metrics(latest_snap_node)
            existing_score = _metric_number(metrics, "content_score")
            if existing_score > 0:
                return {
                    "draft_variant_id": str(draft.id),
                    "content_score": existing_score,
                    "score_label": metrics.get("score_label", "unknown"),
                    "recycle_recommended": bool(metrics.get("recycle_recommended")),
                    "score_breakdown": metrics.get("score_breakdown", {}),
                    "source": "analytics_snapshot",
                }
            scored = score_content_metrics(draft.platform, metrics)
            # Update metrics in the node
            snap_meta = latest_snap_node.metadata_ or {}
            snap_meta["metrics"] = {**metrics, **scored}
            latest_snap_node.metadata_ = snap_meta
            self.db.flush()
            return {
                "draft_variant_id": str(draft.id),
                **scored,
                "source": "analytics_snapshot",
            }

        # No real analytics -- simulate based on content quality signals
        scored = _simulate_content_score(draft)
        sim_metrics = {
            **scored,
            "simulated": True,
        }
        bq = BrainQuery(self.db)
        bq.create_knowledge_node(
            kind="metric",
            title=f"draft_metric:{draft_id}",
            status="active",
            metadata={
                "metric_type": "draft_analytics_snapshot",
                "draft_variant_id": str(draft.id),
                "platform": draft.platform.value,
                "metrics": sim_metrics,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {
            "draft_variant_id": str(draft.id),
            **scored,
            "source": "simulated",
        }
