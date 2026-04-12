from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import uuid

from sqlalchemy.orm import Session

from app.agents.instagram_compliance import run_instagram_compliance_checks
from app.agents.instagram_writer import generate_instagram_post
from app.models.asset import Asset
from app.models.brain import EntityNode, KnowledgeNode
from app.models.instagram import (
    InstagramGenerationLog,
    InstagramRenderJob,
    InstagramRenderStatus,
    PartnerDeliveryChannel,
    PartnerDeliveryPackage,
    PartnerPackageStatus,
)
from app.renderers.base import CanvaRenderRequest
from app.renderers.canva_factory import get_canva_renderer
from app.publishers.instagram_factory import get_instagram_publisher
from app.publishers.instagram_base import InstagramPublishResult
from app.schemas.workflow_config import WorkflowVersionConfig
from app.services.brain_query import BrainQuery
from app.services.publishing_connection_service import PublishingConnectionService


DEFAULT_TEMPLATE_FAMILY = {
    "athlete_spotlight": "athlete_spotlight",
    "education_carousel": "education_carousel",
    "reel": "bold_statement",
    "partner_content": "partner_event_spotlight",
    "story": "story_poll",
    "stat_card": "bold_statement",
}

DEFAULT_PUBLISH_MODE = {
    "education_carousel": "carousel",
    "reel": "reel",
    "story": "story",
}

# Status string constants (brain-native, replaces DraftState enum)
STATUS_REVIEW_REQUIRED = "review_required"
STATUS_SCHEDULED = "scheduled"
STATUS_ACTIVE = "active"
STATUS_FAILED = "failed"
STATUS_PUBLISHING = "publishing"
STATUS_RENDER_FAILED = "render_failed"
STATUS_NEEDS_DESIGN_REVIEW = "needs_design_review"


def determine_draft_status(mode: str, partner_name: str | None = None) -> str:
    """Return the brain-native status string for a new instagram draft."""
    if partner_name:
        return STATUS_REVIEW_REQUIRED
    if mode == "automatic":
        return STATUS_SCHEDULED
    return STATUS_REVIEW_REQUIRED


def build_instagram_caption(caption: str, hashtags: list[str]) -> str:
    if not hashtags:
        return caption
    return f"{caption}\n\n{' '.join(hashtags)}"


def _default_publish_mode(content_type: str) -> str:
    return DEFAULT_PUBLISH_MODE.get(content_type, "feed")


def _default_template_family(content_type: str) -> str:
    return DEFAULT_TEMPLATE_FAMILY.get(content_type, "bold_statement")


def _workflow_slug(content_type: str, approval_tier: str) -> str:
    return f"instagram-{content_type}-{approval_tier}"


def ensure_instagram_workflow_context(
    request_data: dict, db: Session
) -> tuple[EntityNode, KnowledgeNode, KnowledgeNode]:
    """Ensure an instagram workflow EntityNode, workflow_config KnowledgeNode, and trigger KnowledgeNode exist.

    Returns (workflow_entity, workflow_config_node, trigger_node).
    """
    bq = BrainQuery(db)
    approval_tier = request_data.get("approval_tier", "tier_1")
    slug = _workflow_slug(request_data["content_type"], approval_tier)

    workflow_entity = bq.get_entity_by_slug("workflow", slug)
    if workflow_entity is None:
        workflow_entity = bq.create_entity(
            entity_type="workflow",
            canonical_name=f"Instagram {request_data['content_type'].replace('_', ' ').title()}",
            slug=slug,
            status="active",
            description="Phase 4 Instagram workflow bootstrap",
            metadata={
                "platform": "instagram",
                "content_type": request_data["content_type"],
                "mode": "manual",
            },
        )

    # Find or create a workflow_config KnowledgeNode linked to this entity
    config_node = None
    try:
        existing_configs = bq.list_knowledge_by_kind("workflow_config", status="active", limit=20)
        for node in existing_configs:
            if node.metadata_.get("workflow_entity_id") == str(workflow_entity.id):
                config_node = node
                break
    except Exception:
        pass

    if config_node is None:
        config = WorkflowVersionConfig(
            formatting={"max_hashtags": 10, "max_chars": 2200},
            assets={
                "require_image": True,
                "asset_instructions": f"Render {request_data['content_type']} using approved Canva templates only.",
            },
            cta={"cta_preferences": ["comment", "share", "tag", "link_in_bio"]},
        )
        config_node = bq.create_knowledge_node(
            kind="workflow_config",
            title=f"Config: {slug}",
            content=None,
            status="active",
            confidence=1.0,
            trust_score=1.0,
            metadata={
                "workflow_entity_id": str(workflow_entity.id),
                "version_number": 1,
                "version_note": "Phase 4 Instagram bootstrap",
                "author": "phase4",
                "config": config.model_dump(),
            },
        )

    trigger_node = bq.create_knowledge_node(
        kind="trigger",
        title=f"Manual trigger: {slug}",
        content=None,
        status="active",
        confidence=1.0,
        trust_score=1.0,
        metadata={
            "trigger_type": "manual",
            "workflow_entity_id": str(workflow_entity.id),
            "request": request_data.get("context"),
            "partner_name": request_data.get("partner_name"),
            "source_event_type": request_data.get("source_event_type"),
        },
    )
    db.flush()
    return workflow_entity, config_node, trigger_node


def _render_request_for_generated(request_data: dict, generated: dict) -> CanvaRenderRequest:
    asset_plan = generated.get("asset_plan", {})
    image_request = generated.get("image_request", {})
    roles = asset_plan.get("output_asset_roles")
    if not roles:
        slides = asset_plan.get("slides", [])
        roles = [f"slide_{index + 1}" for index in range(len(slides))] if slides else ["primary"]

    # Prefer image_request.template_family over asset_plan/default fallbacks
    template_family = (
        image_request.get("template_family")
        or generated.get("template_family")
        or _default_template_family(request_data["content_type"])
    )

    # Merge text_fields: image_request.data takes priority, asset_plan fills gaps
    text_fields = {**asset_plan.get("text_fields", {})}
    if image_request.get("data"):
        text_fields.update({str(k): str(v) for k, v in image_request["data"].items()})

    return CanvaRenderRequest(
        template_family=template_family,
        brand_mode="partner" if request_data.get("partner_name") else "owned",
        canva_template_id=request_data.get("canva_template_id") or template_family,
        text_fields=text_fields,
        numeric_fields=asset_plan.get("numeric_fields", {}),
        image_references=asset_plan.get("image_references", []),
        output_dimensions=asset_plan.get("output_dimensions"),
        output_asset_roles=roles,
        title=asset_plan.get("title"),
    )


def _create_asset_rows(
    draft: KnowledgeNode,
    workflow_entity: EntityNode,
    template_family: str,
    canva_template_id: str,
    publish_mode: str,
    render_result,
) -> list[Asset]:
    assets: list[Asset] = []
    for index, rendered_asset in enumerate(render_result.assets):
        path_name = Path(rendered_asset.storage_path).name if rendered_asset.storage_path else None
        assets.append(
            Asset(
                id=uuid.uuid4(),
                # Asset.draft_variant_id is a transition field — we store the KnowledgeNode id here
                draft_variant_id=draft.id,
                workflow_id=workflow_entity.id,
                asset_type="instagram_media",
                asset_role=rendered_asset.asset_role,
                provider="canva",
                render_status="succeeded",
                sort_order=index,
                filename=path_name,
                storage_path=rendered_asset.storage_path,
                url=rendered_asset.url,
                mime_type=rendered_asset.mime_type,
                platform_metadata={
                    "platform": "instagram",
                    "template_family": template_family,
                    "canva_template_id": canva_template_id,
                    "publish_mode": publish_mode,
                },
            )
        )
    return assets


def _apply_publish_result(draft: KnowledgeNode, publish_result: InstagramPublishResult) -> KnowledgeNode:
    meta = dict(draft.metadata_)
    if publish_result.success:
        draft.status = STATUS_ACTIVE
        meta["platform_post_id"] = publish_result.post_id
        meta["post_url"] = publish_result.post_url
        meta["published_at"] = datetime.now(timezone.utc).isoformat()
        meta.pop("failure_reason", None)
    else:
        draft.status = STATUS_FAILED
        meta["failure_reason"] = publish_result.error
    draft.metadata_ = meta
    return draft


def _publish_draft_with_assets(
    draft: KnowledgeNode,
    assets: list[Asset],
    publish_mode: str,
    runtime_config: dict | None = None,
):
    asset_urls = [asset.url or asset.storage_path for asset in assets if asset.url or asset.storage_path]
    if not asset_urls:
        raise ValueError("Instagram publish requires at least one rendered asset")
    hashtags = draft.metadata_.get("hashtags") or []
    publisher = (
        get_instagram_publisher(runtime_config=runtime_config)
        if runtime_config is not None
        else get_instagram_publisher()
    )
    publish_result = publisher.publish_post(
        build_instagram_caption(draft.content, hashtags),
        asset_urls,
        publish_mode=publish_mode,
    )
    return _apply_publish_result(draft, publish_result)


def publish_instagram_variant(draft_id: uuid.UUID | str | KnowledgeNode, db: Session) -> KnowledgeNode:
    bq = BrainQuery(db)
    if isinstance(draft_id, KnowledgeNode):
        draft = draft_id
    else:
        node_id = draft_id if isinstance(draft_id, uuid.UUID) else uuid.UUID(str(draft_id))
        draft = bq.get_knowledge_node(node_id)
    if draft is None:
        raise ValueError("Instagram draft not found")

    assets = (
        db.query(Asset)
        .filter(Asset.draft_variant_id == draft.id)
        .order_by(Asset.sort_order.asc())
        .all()
    )
    publish_mode = "feed"
    compliance = draft.metadata_.get("compliance_result") or {}
    if isinstance(compliance, dict):
        publish_mode = compliance.get("publish_mode", publish_mode)

    target = PublishingConnectionService(db).resolve_active_publish_target("instagram")
    runtime_config = None
    if target is not None:
        runtime_config = {
            **dict(target.get("credentials") or {}),
            **dict(target.get("config") or {}),
        }

    draft.status = STATUS_PUBLISHING
    _publish_draft_with_assets(draft, assets, publish_mode, runtime_config=runtime_config)

    db.commit()
    return draft


def generate_instagram_item(request_data: dict, db: Session) -> dict:
    bq = BrainQuery(db)
    approval_tier = request_data.get("approval_tier", "tier_1")
    workflow_entity, config_node, trigger_node = ensure_instagram_workflow_context(request_data, db)

    generated, log_data = generate_instagram_post(
        content_type=request_data["content_type"],
        pillar=request_data["pillar"],
        claims=request_data.get("claims", []),
        context=request_data.get("context"),
    )
    compliance_result = run_instagram_compliance_checks(generated, request_data.get("claims", []))
    if not compliance_result.passed:
        raise ValueError(compliance_result.failure_reason or "Instagram compliance failed")

    publish_mode = request_data.get("publish_mode") or _default_publish_mode(request_data["content_type"])
    workflow_mode = workflow_entity.metadata_.get("mode", "manual")

    job_node = bq.create_knowledge_node(
        kind="job",
        title=f"Job: Instagram {request_data['content_type']}",
        status="running",
        confidence=1.0,
        trust_score=1.0,
        metadata={
            "workflow_entity_id": str(workflow_entity.id),
            "trigger_id": str(trigger_node.id),
            "prompt_snapshot": {"prompt_snapshot": log_data["prompt_snapshot"]},
            "compliance_snapshot": None,
        },
    )
    bq.create_edge(
        source_id=trigger_node.id,
        target_id=job_node.id,
        source_type="knowledge",
        target_type="knowledge",
        relation="produced_job",
    )

    draft_status = determine_draft_status(workflow_mode, request_data.get("partner_name"))
    draft_node = bq.create_draft(
        title=f"Instagram {request_data['content_type']}: {(compliance_result.corrected_content or generated['caption'])[:60]}",
        content=compliance_result.corrected_content or generated["caption"],
        platform="instagram",
        intent="partner" if request_data.get("partner_name") else "brand",
        pillar=request_data.get("pillar", "thought_leadership"),
        hashtags=compliance_result.corrected_hashtags,
        mode=workflow_mode,
        status=draft_status,
        confidence=0.8,
        trust_score=0.8,
        extra_metadata={
            "compliance_result": {
                "passed": True,
                "checks_run": compliance_result.checks_run,
                "approval_tier": approval_tier,
                "cta_type": generated["cta_type"],
                "template_family": generated.get("template_family") or _default_template_family(request_data["content_type"]),
                "publish_mode": publish_mode,
                "asset_plan": generated.get("asset_plan", {}),
            },
            "timezone": "America/New_York",
            "partner_name": request_data.get("partner_name"),
            "source_event_type": request_data.get("source_event_type"),
        },
    )
    bq.create_edge(
        source_id=job_node.id,
        target_id=draft_node.id,
        source_type="knowledge",
        target_type="knowledge",
        relation="produced_draft",
    )
    bq.create_edge(
        source_id=workflow_entity.id,
        target_id=draft_node.id,
        source_type="entity",
        target_type="knowledge",
        relation="produced",
    )

    generation_log = InstagramGenerationLog(
        id=uuid.uuid4(),
        draft_variant_id=draft_node.id,
        prompt_snapshot=log_data["prompt_snapshot"],
        response=log_data["response"],
        model=log_data["model"],
        tokens_in=log_data["tokens_in"],
        tokens_out=log_data["tokens_out"],
        cost_estimate=log_data["cost_estimate"],
        duration_ms=log_data["duration_ms"],
    )
    db.add(generation_log)

    render_request = _render_request_for_generated(request_data, generated)
    render_job = InstagramRenderJob(
        id=uuid.uuid4(),
        draft_variant_id=draft_node.id,
        template_family=render_request.template_family,
        input_payload=asdict(render_request),
        status=InstagramRenderStatus.RENDERING,
        started_at=datetime.now(timezone.utc),
    )
    db.add(render_job)

    render_result = get_canva_renderer().render(render_request)
    assets: list[Asset] = []
    package = None

    if render_result.success:
        render_job.status = InstagramRenderStatus.SUCCEEDED
        render_job.provider_job_id = render_result.provider_job_id
        render_job.completed_at = datetime.now(timezone.utc)
        assets = _create_asset_rows(
            draft_node,
            workflow_entity,
            render_request.template_family,
            render_request.canva_template_id,
            publish_mode,
            render_result,
        )
        for asset in assets:
            db.add(asset)

        if request_data.get("partner_name"):
            package = PartnerDeliveryPackage(
                id=uuid.uuid4(),
                draft_variant_id=draft_node.id,
                partner_name=request_data["partner_name"],
                source_event_type=request_data.get("source_event_type"),
                status=PartnerPackageStatus.NEEDS_REVIEW,
                delivery_channel=PartnerDeliveryChannel.DASHBOARD,
                caption=draft_node.content,
                hashtags=draft_node.metadata_.get("hashtags", []),
                asset_ids=[asset.id for asset in assets],
                delivery_payload={
                    "asset_urls": [asset.url for asset in assets if asset.url],
                    "publish_mode": publish_mode,
                },
            )
            db.add(package)
        elif workflow_mode == "automatic":
            target = PublishingConnectionService(db).resolve_active_publish_target("instagram")
            runtime_config = None
            if target is not None:
                runtime_config = {
                    **dict(target.get("credentials") or {}),
                    **dict(target.get("config") or {}),
                }
            draft_node.status = STATUS_PUBLISHING
            _publish_draft_with_assets(draft_node, assets, publish_mode, runtime_config=runtime_config)
    else:
        if request_data.get("partner_name"):
            draft_node.status = STATUS_NEEDS_DESIGN_REVIEW
            render_job.status = InstagramRenderStatus.NEEDS_DESIGN_REVIEW
        else:
            draft_node.status = STATUS_RENDER_FAILED
            render_job.status = InstagramRenderStatus.FAILED
        meta = dict(draft_node.metadata_)
        meta["failure_reason"] = render_result.error
        draft_node.metadata_ = meta
        render_job.error_message = render_result.error
        render_job.completed_at = datetime.now(timezone.utc)

    job_meta = dict(job_node.metadata_)
    job_meta["compliance_snapshot"] = {
        "passed": compliance_result.passed,
        "checks_run": compliance_result.checks_run,
        "template_family": render_request.template_family,
        "publish_mode": publish_mode,
    }
    job_node.metadata_ = job_meta
    job_node.status = "completed"

    db.commit()
    return {"job": job_node, "draft": draft_node, "render_job": render_job, "assets": assets, "package": package}
