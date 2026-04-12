import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.brain import EntityNode, KnowledgeNode
from app.services.brain_query import BrainQuery


# Draft statuses that count as "in queue" (automatic pipeline)
QUEUE_STATUSES = ("scheduled", "review_required")


def _workflow_or_404(db: Session, workflow_id: str | uuid.UUID) -> EntityNode:
    workflow_uuid = workflow_id if isinstance(workflow_id, uuid.UUID) else uuid.UUID(str(workflow_id))
    entity = BrainQuery(db).get_entity(workflow_uuid)
    if entity is None:
        raise ValueError("Workflow not found")
    return entity


def _next_rule_for_workflow(db: Session, workflow_id: uuid.UUID) -> KnowledgeNode | None:
    """Return the soonest-firing active schedule_rule for the given workflow."""
    bq = BrainQuery(db)
    # Find all schedule_rule nodes linked to this workflow via entity edges
    edges = bq.get_edges_from(workflow_id, relation="has_schedule_rule")
    rule_ids = {edge.target_id for edge in edges}
    if not rule_ids:
        return None

    rules = (
        db.query(KnowledgeNode)
        .filter(
            KnowledgeNode.id.in_(rule_ids),
            KnowledgeNode.kind == "schedule_rule",
            KnowledgeNode.status == "active",
        )
        .all()
    )

    # Sort by next_fire_at in metadata (nulls last), then created_at
    def _sort_key(rule: KnowledgeNode):
        nfa = rule.metadata_.get("next_fire_at")
        return (nfa is None, nfa or "", str(rule.created_at))

    rules.sort(key=_sort_key)
    return rules[0] if rules else None


def _queued_drafts_for_workflow(db: Session, workflow_id: uuid.UUID) -> list[KnowledgeNode]:
    """Return draft KnowledgeNodes in the automatic queue for a workflow."""
    bq = BrainQuery(db)
    edges = bq.get_edges_from(workflow_id, relation="produced")
    draft_ids = {edge.target_id for edge in edges}
    if not draft_ids:
        return []

    drafts = (
        db.query(KnowledgeNode)
        .filter(
            KnowledgeNode.id.in_(draft_ids),
            KnowledgeNode.kind == "draft",
            KnowledgeNode.status.in_(QUEUE_STATUSES),
        )
        .all()
    )

    def _draft_sort_key(d: KnowledgeNode):
        vf = d.valid_from
        return (vf is None, vf or datetime.min.replace(tzinfo=timezone.utc), str(d.created_at))

    drafts.sort(key=_draft_sort_key)
    return drafts


def _health_after_resume(entity: EntityNode) -> str:
    if entity.metadata_.get("last_error"):
        return "unhealthy"
    return "healthy"


def set_workflow_pause_state(db: Session, workflow_id: str | uuid.UUID, *, paused: bool) -> EntityNode:
    entity = _workflow_or_404(db, workflow_id)
    meta = dict(entity.metadata_)
    meta["paused_at"] = datetime.now(timezone.utc).isoformat() if paused else None
    meta["health_status"] = "paused" if paused else _health_after_resume(entity)
    entity.metadata_ = meta
    db.flush()
    return entity


def move_workflow_to_manual(db: Session, workflow_id: str | uuid.UUID) -> EntityNode:
    entity = _workflow_or_404(db, workflow_id)
    meta = dict(entity.metadata_)
    meta["mode"] = "manual"
    meta["paused_at"] = None
    meta["health_status"] = "healthy"
    entity.metadata_ = meta

    # Move any "scheduled" (AUTOMATIC_READY/SCHEDULED_MANUAL) drafts to "review_required" (MANUAL_READY)
    drafts = _queued_drafts_for_workflow(db, entity.id)
    for draft in drafts:
        if draft.status == "scheduled":
            draft_meta = dict(draft.metadata_)
            draft_meta["state"] = "manual_ready"
            draft.metadata_ = draft_meta
            draft.status = "review_required"
            draft.valid_from = None

    db.flush()
    return entity


def list_automatic_workflow_cards(db: Session) -> list[dict]:
    bq = BrainQuery(db)
    entities = bq.list_entities_by_type("workflow", status="active")

    # Filter to automatic mode only
    workflows = [e for e in entities if e.metadata_.get("mode") == "automatic"]

    # Sort by canonical_name
    workflows.sort(key=lambda e: e.canonical_name)

    cards: list[dict] = []
    for entity in workflows:
        meta = entity.metadata_
        rule = _next_rule_for_workflow(db, entity.id)
        drafts = _queued_drafts_for_workflow(db, entity.id)

        # Extract next_fire_at from rule metadata (stored as ISO string)
        next_trigger_at = None
        publish_time_label = None
        if rule:
            next_trigger_at = rule.metadata_.get("next_fire_at")
            pub_hour = rule.metadata_.get("publish_hour_local")
            pub_minute = rule.metadata_.get("publish_minute_local") or 0
            if pub_hour is not None:
                publish_time_label = f"{pub_hour:02d}:{pub_minute:02d}"

        cards.append(
            {
                "workflow_id": str(entity.id),
                "workflow_name": entity.canonical_name,
                "workflow_slug": entity.slug,
                "platform": meta.get("platform", ""),
                "mode": meta.get("mode", "automatic"),
                "timezone": meta.get("timezone", "UTC"),
                "health_status": meta.get("health_status", "healthy"),
                "paused_at": meta.get("paused_at"),
                "last_run_at": meta.get("last_run_at"),
                "last_success_at": meta.get("last_success_at"),
                "last_error": meta.get("last_error"),
                "next_trigger_at": next_trigger_at,
                "publish_time_label": publish_time_label,
                "queued_draft_count": len(drafts),
                "drafts": drafts,
            }
        )
    return cards


def build_scheduler_status(db: Session, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    upcoming_window = now + timedelta(hours=24)
    bq = BrainQuery(db)

    all_workflows = bq.list_entities_by_type("workflow", status="active")
    paused_workflows = sum(1 for e in all_workflows if e.metadata_.get("paused_at") is not None)
    unhealthy_workflows = sum(1 for e in all_workflows if e.metadata_.get("health_status") == "unhealthy")

    # Count due schedule rules: active schedule_rule nodes whose next_fire_at <= now
    # and whose linked workflow is not paused
    paused_ids = {e.id for e in all_workflows if e.metadata_.get("paused_at") is not None}
    all_rules = bq.list_knowledge_by_kind("schedule_rule", status="active")
    due_rules = 0
    for rule in all_rules:
        nfa_str = rule.metadata_.get("next_fire_at")
        if not nfa_str:
            continue
        try:
            nfa = datetime.fromisoformat(nfa_str)
        except (ValueError, TypeError):
            continue
        if nfa > now:
            continue
        # Check workflow is not paused — find the workflow this rule belongs to
        edges = bq.get_edges_to(rule.id, relation="has_schedule_rule")
        workflow_ids = {e.source_id for e in edges}
        if workflow_ids & paused_ids:
            continue
        due_rules += 1

    # Count due drafts and upcoming drafts
    # "scheduled" status with valid_from set
    all_scheduled_drafts = bq.list_drafts_by_status("scheduled")
    due_drafts = 0
    upcoming_24h = 0
    for draft in all_scheduled_drafts:
        vf = draft.valid_from
        if vf is None:
            continue
        # Check workflow not paused
        edges = bq.get_edges_to(draft.id, relation="produced")
        workflow_ids = {e.source_id for e in edges}
        if not (workflow_ids & paused_ids):
            if vf <= now:
                due_drafts += 1
            elif vf <= upcoming_window:
                upcoming_24h += 1

    return {
        "paused_workflows": paused_workflows,
        "unhealthy_workflows": unhealthy_workflows,
        "upcoming_24h": upcoming_24h,
        "due_rules": due_rules,
        "due_drafts": due_drafts,
    }


def pause_all_workflows(db: Session) -> int:
    bq = BrainQuery(db)
    entities = bq.list_entities_by_type("workflow", status="active")
    automatic = [e for e in entities if e.metadata_.get("mode") == "automatic"]
    for entity in automatic:
        set_workflow_pause_state(db, entity.id, paused=True)
    db.flush()
    return len(automatic)


def resume_all_workflows(db: Session) -> int:
    bq = BrainQuery(db)
    entities = bq.list_entities_by_type("workflow", status="active")
    automatic = [e for e in entities if e.metadata_.get("mode") == "automatic"]
    for entity in automatic:
        set_workflow_pause_state(db, entity.id, paused=False)
    db.flush()
    return len(automatic)
