import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.compliance import run_compliance_checks
from app.agents.content_writer import generate_tweets
from app.models.brain import KnowledgeNode
from app.publishers import get_publisher
from app.services.brain_query import BrainQuery
from app.services.publishing_connection_service import PublishingConnectionService


def generate_partner_x_item(request_data: dict, db: Session) -> KnowledgeNode:
    bq = BrainQuery(db)
    variations, log_data = generate_tweets(
        content_type=request_data["content_type"],
        pillar=request_data["pillar"],
        claims=request_data.get("claims", []),
        context=request_data.get("context"),
    )
    if not variations:
        raise ValueError("No valid X variations generated")

    selected_variation = None
    selected_compliance = None
    for variation in variations:
        compliance_result = run_compliance_checks(
            variation,
            requested_claims=request_data.get("claims", []),
            dynamic_value_groups=request_data.get("dynamic_value_groups"),
        )
        if compliance_result.passed:
            selected_variation = variation
            selected_compliance = compliance_result
            break

    if selected_variation is None or selected_compliance is None:
        raise ValueError("No X variations passed compliance")

    draft = bq.create_draft(
        title=f"X post: {(selected_compliance.corrected_content or selected_variation['content'])[:50]}",
        content=selected_compliance.corrected_content or selected_variation["content"],
        platform="x",
        intent=selected_variation.get("intent", "partner"),
        pillar=request_data["pillar"],
        hashtags=selected_compliance.corrected_hashtags or [],
        mode="manual",
        status="pending",
        extra_metadata={
            "content_type": request_data["content_type"],
            "request_payload": request_data,
            "compliance_result": {
                "passed": True,
                "checks_run": selected_compliance.checks_run,
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
    return publish_partner_x_item(draft.id, db)


def publish_partner_x_item(content_id: uuid.UUID | str, db: Session) -> KnowledgeNode:
    bq = BrainQuery(db)
    item = bq.get_knowledge_node(content_id if isinstance(content_id, uuid.UUID) else uuid.UUID(str(content_id)))
    if item is None:
        raise ValueError("X content not found")
    if item.status != "pending":
        raise ValueError(f"Cannot publish X content in status '{item.status}'")

    item.status = "publishing"
    db.commit()
    db.refresh(item)

    target = PublishingConnectionService(db).resolve_active_publish_target("x")
    runtime_config = None
    if target is not None:
        runtime_config = {
            **dict(target.get("credentials") or {}),
            **dict(target.get("config") or {}),
        }

    publisher = (
        get_publisher(platform="x", runtime_config=runtime_config)
        if runtime_config is not None
        else get_publisher(platform="x")
    )
    post_result = publisher.post_tweet(item.content)
    meta = dict(item.metadata_)
    if post_result.success:
        item.status = "active"
        meta["platform_post_id"] = post_result.tweet_id
        meta["post_url"] = post_result.tweet_url
        meta["published_at"] = datetime.now(timezone.utc).isoformat()
    elif post_result.error and post_result.error.startswith("unknown:"):
        item.status = "publishing_unknown"
        meta["failure_reason"] = post_result.error
    else:
        item.status = "failed"
        meta["failure_reason"] = post_result.error
    item.metadata_ = meta

    db.commit()
    db.refresh(item)
    return item
