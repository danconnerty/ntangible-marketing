import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.linkedin_compliance import run_linkedin_compliance_checks
from app.agents.linkedin_writer import generate_linkedin_post
from app.models.brain import KnowledgeNode
from app.publishers.linkedin_factory import get_linkedin_publisher
from app.services.brain_query import BrainQuery
from app.services.publishing_connection_service import PublishingConnectionService


def determine_initial_status(approval_tier: str) -> str:
    if approval_tier == "tier_1":
        return "pending"
    return "review_required"


def generate_linkedin_item(request_data: dict, db: Session) -> KnowledgeNode:
    bq = BrainQuery(db)
    approval_tier = request_data.get("approval_tier", "tier_1")
    generated, log_data = generate_linkedin_post(
        content_type=request_data["content_type"],
        pillar=request_data["pillar"],
        claims=request_data.get("claims", []),
        context=request_data.get("context"),
    )
    compliance_result = run_linkedin_compliance_checks(
        generated,
        requested_claims=request_data.get("claims", []),
        dynamic_value_groups=request_data.get("dynamic_value_groups"),
    )
    if not compliance_result.passed:
        raise ValueError(compliance_result.failure_reason or "LinkedIn compliance failed")

    initial_status = determine_initial_status(approval_tier)
    draft = bq.create_draft(
        title=f"LinkedIn: {(compliance_result.corrected_content or generated['content'])[:60]}",
        content=compliance_result.corrected_content or generated["content"],
        platform="linkedin",
        intent=generated.get("intent", "brand"),
        pillar=request_data["pillar"],
        hashtags=compliance_result.corrected_hashtags or [],
        mode="manual",
        status=initial_status,
        extra_metadata={
            "content_type": request_data["content_type"],
            "approval_tier": approval_tier,
            "request_payload": request_data,
            "compliance_result": {
                "passed": True,
                "checks_run": compliance_result.checks_run,
            },
        },
    )
    bq.create_knowledge_node(
        kind="generation_log",
        title=f"Gen log for {draft.id}",
        status="active",
        metadata={**log_data, "draft_id": str(draft.id)},
    )
    db.commit()
    db.refresh(draft)
    return draft


def approve_linkedin_item(post: KnowledgeNode, db: Session) -> KnowledgeNode:
    post.status = "scheduled"
    db.commit()
    db.refresh(post)
    return post


def reject_linkedin_item(post: KnowledgeNode, notes: str | None, db: Session) -> KnowledgeNode:
    post.status = "rejected"
    meta = dict(post.metadata_)
    if notes:
        meta["review_notes"] = notes
    post.metadata_ = meta
    db.commit()
    db.refresh(post)
    return post


def publish_linkedin_item(post_id: uuid.UUID | str, db: Session) -> KnowledgeNode:
    bq = BrainQuery(db)
    post = bq.get_knowledge_node(post_id if isinstance(post_id, uuid.UUID) else uuid.UUID(str(post_id)))
    if post is None:
        raise ValueError("LinkedIn post not found")
    if post.status not in {"pending", "scheduled"}:
        raise ValueError(f"Cannot publish post in status '{post.status}'")

    post.status = "publishing"
    db.commit()
    db.refresh(post)

    target = PublishingConnectionService(db).resolve_active_publish_target("linkedin")
    runtime_config = None
    if target is not None:
        runtime_config = {
            **dict(target.get("credentials") or {}),
            **dict(target.get("config") or {}),
        }

    publisher = (
        get_linkedin_publisher(runtime_config=runtime_config)
        if runtime_config is not None
        else get_linkedin_publisher()
    )
    publish_result = publisher.publish_post(post.content)
    meta = dict(post.metadata_)
    if publish_result.success:
        post.status = "active"
        meta["platform_post_id"] = publish_result.post_id
        meta["post_url"] = publish_result.post_url
        meta["published_at"] = datetime.now(timezone.utc).isoformat()
    elif publish_result.error and "timeout" in publish_result.error.lower():
        post.status = "publishing_unknown"
        meta["failure_reason"] = publish_result.error
    else:
        post.status = "failed"
        meta["failure_reason"] = publish_result.error
    post.metadata_ = meta

    db.commit()
    db.refresh(post)
    return post
