import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.agents.blog_compliance import run_blog_compliance_checks
from app.agents.blog_writer import generate_blog_draft
from app.agents.compliance import run_compliance_checks
from app.agents.content_writer import generate_tweets
from app.agents.instagram_compliance import run_instagram_compliance_checks
from app.agents.instagram_writer import generate_instagram_post
from app.agents.linkedin_compliance import run_linkedin_compliance_checks
from app.agents.linkedin_writer import generate_linkedin_post
from app.agents.newsletter_compliance import run_newsletter_compliance_checks
from app.agents.newsletter_writer import generate_newsletter_draft
from app.config import get_canva_template
from app.models.workflow import Platform, Workflow, WorkflowVersion
from app.renderers.base import CanvaRenderRequest
from app.renderers.canva_factory import get_canva_renderer, get_image_renderer
from app.services.instagram_pipeline import (
    _default_publish_mode,
    _render_request_for_generated,
)


logger = logging.getLogger(__name__)

MAX_COMPLIANCE_RETRIES = 2

# X content types that should produce an image asset
_X_IMAGE_CONTENT_TYPES: dict[str, str] = {
    "stat_card": "stat_card",
    "quote_graphic": "quote_graphic",
    "assessment_preview": "stat_card",  # reuse stat_card template
}

# LinkedIn content types that should produce a header image
_LINKEDIN_IMAGE_CONTENT_TYPES: dict[str, str] = {
    "thought_leadership": "thought_leadership_header",
    "company_update": "partner_announcement",
}


@dataclass
class GeneratedAssetPayload:
    asset_type: str
    asset_role: str | None
    provider: str | None
    render_status: str | None
    sort_order: int
    filename: str | None
    storage_path: str | None
    url: str | None
    mime_type: str | None
    platform_metadata: dict[str, Any] | None = None


@dataclass
class GeneratedCandidate:
    content: str
    hashtags: list[str]
    compliance_result: dict[str, Any]
    generation_trace: dict[str, Any]
    prompt_snapshot: str
    failure_reason: str | None = None
    asset_payloads: list[GeneratedAssetPayload] = field(default_factory=list)


class PlatformGenerationService:
    def __init__(self, db: Session):
        self.db = db

    def generate(
        self,
        workflow: Workflow,
        version: WorkflowVersion,
        payload: dict[str, Any],
    ) -> list[GeneratedCandidate]:
        if workflow.platform == Platform.X:
            return self._generate_x(payload)
        if workflow.platform == Platform.LINKEDIN:
            return self._generate_linkedin(payload)
        if workflow.platform == Platform.INSTAGRAM:
            return self._generate_instagram(workflow, payload)
        if workflow.platform == Platform.NEWSLETTER:
            return self._generate_newsletter(payload)
        if workflow.platform == Platform.BLOG:
            return self._generate_blog(payload)
        raise ValueError(f"Unsupported platform: {workflow.platform.value}")

    # ------------------------------------------------------------------
    # Shared asset-rendering helper
    # ------------------------------------------------------------------

    @staticmethod
    def _render_platform_assets(
        platform: str,
        template_family: str,
        text_fields: dict[str, str],
        numeric_fields: dict[str, str | int | float] | None = None,
        image_references: list[str] | None = None,
        asset_roles: list[str] | None = None,
        title: str | None = None,
        structured_data: dict[str, Any] | None = None,
    ) -> list[GeneratedAssetPayload]:
        """Render an image via the active image renderer.

        Phase 1+: defaults to the in-process Pillow renderer. Legacy Canva
        paths are reachable via ``IMAGE_RENDERER=canva_http``. Returns a list
        of ``GeneratedAssetPayload`` on success, or an empty list if the
        render fails (non-fatal for text-first platforms — Instagram wraps
        this helper and escalates failures separately).
        """
        template_config = get_canva_template(platform, template_family)
        canva_template_id = (
            template_config["template_id"] if template_config else template_family
        )

        render_request = CanvaRenderRequest(
            template_family=template_family,
            brand_mode="owned",
            canva_template_id=canva_template_id,
            text_fields=text_fields,
            numeric_fields=numeric_fields or {},
            image_references=image_references or [],
            output_asset_roles=asset_roles or ["primary"],
            title=title,
            structured_data=structured_data,
        )

        try:
            render_result = get_image_renderer().render(render_request)
        except Exception:
            logger.exception("Asset render failed for %s/%s", platform, template_family)
            return []

        if not render_result.success:
            logger.warning(
                "Asset render unsuccessful for %s/%s: %s",
                platform,
                template_family,
                render_result.error,
            )
            return []

        provider = "pillow"
        payloads: list[GeneratedAssetPayload] = []
        for index, asset in enumerate(render_result.assets):
            filename = asset.storage_path.split("/")[-1] if asset.storage_path else None
            payloads.append(
                GeneratedAssetPayload(
                    asset_type=f"{platform}_media",
                    asset_role=asset.asset_role,
                    provider=provider,
                    render_status="succeeded",
                    sort_order=index,
                    filename=filename,
                    storage_path=asset.storage_path,
                    url=asset.url,
                    mime_type=asset.mime_type,
                    platform_metadata={
                        "platform": platform,
                        "template_family": template_family,
                        "canva_template_id": canva_template_id,
                    },
                )
            )
        return payloads

    def _generate_x(self, payload: dict[str, Any]) -> list[GeneratedCandidate]:
        last_failure_reason: str | None = None
        for attempt in range(1, MAX_COMPLIANCE_RETRIES + 2):
            if attempt > 1:
                logger.info("X generation retry %d/%d", attempt - 1, MAX_COMPLIANCE_RETRIES)
            variations, log_data = generate_tweets(
                content_type=payload["content_type"],
                pillar=payload["pillar"],
                claims=payload["claims"],
                context=payload["context"],
            )
            candidates: list[GeneratedCandidate] = []
            for variation in variations:
                result = run_compliance_checks(
                    variation,
                    requested_claims=payload["claims"],
                    dynamic_value_groups=payload.get("dynamic_value_groups"),
                )
                if not result.passed:
                    last_failure_reason = result.failure_reason or "X compliance check failed"
                    continue

                # Render an image asset when the content type warrants one
                asset_payloads: list[GeneratedAssetPayload] = []
                image_request = variation.get("image_request")
                if image_request:
                    # Use structured image instructions from the writer agent
                    template_family = image_request.get("template_family") or _X_IMAGE_CONTENT_TYPES.get(payload["content_type"])
                    if template_family:
                        asset_payloads = self._render_platform_assets(
                            platform="x",
                            template_family=template_family,
                            text_fields={str(k): str(v) for k, v in image_request.get("data", {}).items()},
                            title=f"X {payload['content_type'].replace('_', ' ').title()}",
                        )
                elif _X_IMAGE_CONTENT_TYPES.get(payload["content_type"]):
                    # Fallback: no image_request from agent, use legacy hardcoded mapping
                    template_family = _X_IMAGE_CONTENT_TYPES[payload["content_type"]]
                    content_text = result.corrected_content or variation["content"]
                    asset_payloads = self._render_platform_assets(
                        platform="x",
                        template_family=template_family,
                        text_fields={
                            "headline": content_text[:120],
                            "context": payload.get("context") or "",
                        },
                        title=f"X {payload['content_type'].replace('_', ' ').title()}",
                    )

                candidates.append(
                    GeneratedCandidate(
                        content=result.corrected_content or variation["content"],
                        hashtags=result.corrected_hashtags or variation.get("hashtags", []),
                        compliance_result={
                            "passed": True,
                            "checks_run": result.checks_run,
                        },
                        generation_trace=log_data["response"],
                        prompt_snapshot=log_data["prompt_snapshot"],
                        asset_payloads=asset_payloads,
                    )
                )
            if candidates:
                return candidates
            logger.warning("X generation attempt %d: all variations failed compliance", attempt)
        raise ValueError(last_failure_reason or "No X variations passed compliance after retries")

    def _generate_linkedin(self, payload: dict[str, Any]) -> list[GeneratedCandidate]:
        last_failure_reason: str | None = None
        for attempt in range(1, MAX_COMPLIANCE_RETRIES + 2):
            if attempt > 1:
                logger.info("LinkedIn generation retry %d/%d", attempt - 1, MAX_COMPLIANCE_RETRIES)
            generated, log_data = generate_linkedin_post(
                content_type=payload["content_type"],
                pillar=payload["pillar"],
                claims=payload["claims"],
                context=payload["context"],
            )
            result = run_linkedin_compliance_checks(
                generated,
                requested_claims=payload["claims"],
                dynamic_value_groups=payload.get("dynamic_value_groups"),
            )
            if result.passed:
                # Render a header image when the content type warrants one
                asset_payloads: list[GeneratedAssetPayload] = []
                image_request = generated.get("image_request")
                if image_request:
                    # Use structured image instructions from the writer agent
                    template_family = image_request.get("template_family") or _LINKEDIN_IMAGE_CONTENT_TYPES.get(payload["content_type"])
                    if template_family:
                        asset_payloads = self._render_platform_assets(
                            platform="linkedin",
                            template_family=template_family,
                            text_fields={str(k): str(v) for k, v in image_request.get("data", {}).items()},
                            title=f"LinkedIn {payload['content_type'].replace('_', ' ').title()}",
                        )
                elif _LINKEDIN_IMAGE_CONTENT_TYPES.get(payload["content_type"]):
                    # Fallback: no image_request from agent, use legacy hardcoded mapping
                    template_family = _LINKEDIN_IMAGE_CONTENT_TYPES[payload["content_type"]]
                    content_text = result.corrected_content or generated["content"]
                    first_line = content_text.split("\n", 1)[0][:140]
                    asset_payloads = self._render_platform_assets(
                        platform="linkedin",
                        template_family=template_family,
                        text_fields={
                            "headline": first_line,
                            "subtitle": payload.get("context") or "",
                        },
                        title=f"LinkedIn {payload['content_type'].replace('_', ' ').title()}",
                    )

                return [
                    GeneratedCandidate(
                        content=result.corrected_content or generated["content"],
                        hashtags=result.corrected_hashtags or generated.get("hashtags", []),
                        compliance_result={
                            "passed": True,
                            "checks_run": result.checks_run,
                        },
                        generation_trace=log_data["response"],
                        prompt_snapshot=log_data["prompt_snapshot"],
                        asset_payloads=asset_payloads,
                    )
                ]
            last_failure_reason = result.failure_reason or "LinkedIn compliance failed"
            logger.warning("LinkedIn generation attempt %d failed compliance: %s", attempt, last_failure_reason)
        raise ValueError(last_failure_reason or "LinkedIn compliance failed after retries")

    def _generate_instagram(self, workflow: Workflow, payload: dict[str, Any]) -> list[GeneratedCandidate]:
        last_failure_reason: str | None = None
        for attempt in range(1, MAX_COMPLIANCE_RETRIES + 2):
            if attempt > 1:
                logger.info("Instagram generation retry %d/%d", attempt - 1, MAX_COMPLIANCE_RETRIES)
            generated, log_data = generate_instagram_post(
                content_type=payload["content_type"],
                pillar=payload["pillar"],
                claims=payload["claims"],
                context=payload["context"],
            )
            result = run_instagram_compliance_checks(
                generated,
                requested_claims=payload["claims"],
            )
            if not result.passed:
                last_failure_reason = result.failure_reason or "Instagram compliance failed"
                logger.warning("Instagram generation attempt %d failed compliance: %s", attempt, last_failure_reason)
                continue
            # Compliance passed — proceed to asset rendering (no retry on render failure)
            break
        else:
            raise ValueError(last_failure_reason or "Instagram compliance failed after retries")

        request_data = {
            "content_type": payload["content_type"],
            "partner_name": payload.get("partner_name"),
            "canva_template_id": payload.get("canva_template_id"),
            "publish_mode": payload.get("publish_mode") or _default_publish_mode(payload["content_type"]),
        }
        render_request = _render_request_for_generated(request_data, generated)
        render_result = get_canva_renderer().render(render_request)
        if not render_result.success:
            raise ValueError(render_result.error or "Instagram asset render failed")

        asset_payloads: list[GeneratedAssetPayload] = []
        template_family = generated.get("template_family") or render_request.template_family
        publish_mode = request_data["publish_mode"]
        for index, asset in enumerate(render_result.assets):
            filename = asset.storage_path.split("/")[-1] if asset.storage_path else None
            asset_payloads.append(
                GeneratedAssetPayload(
                    asset_type="instagram_media",
                    asset_role=asset.asset_role,
                    provider="canva",
                    render_status="succeeded",
                    sort_order=index,
                    filename=filename,
                    storage_path=asset.storage_path,
                    url=asset.url,
                    mime_type=asset.mime_type,
                    platform_metadata={
                        "platform": "instagram",
                        "template_family": template_family,
                        "publish_mode": publish_mode,
                    },
                )
            )

        return [
            GeneratedCandidate(
                content=result.corrected_content or generated["caption"],
                hashtags=result.corrected_hashtags or generated.get("hashtags", []),
                compliance_result={
                    "passed": True,
                    "checks_run": result.checks_run,
                    "template_family": template_family,
                    "publish_mode": publish_mode,
                    "asset_plan": generated.get("asset_plan", {}),
                },
                generation_trace=log_data["response"],
                prompt_snapshot=log_data["prompt_snapshot"],
                asset_payloads=asset_payloads,
            )
        ]

    def _generate_newsletter(self, payload: dict[str, Any]) -> list[GeneratedCandidate]:
        workflow_config = payload.get("workflow_version_config", {})
        routing = workflow_config.get("routing", {})
        segment = routing.get("target_audience_segment") or "coaches_front_offices"
        last_failure_reason: str | None = None
        for attempt in range(1, MAX_COMPLIANCE_RETRIES + 2):
            if attempt > 1:
                logger.info("Newsletter generation retry %d/%d", attempt - 1, MAX_COMPLIANCE_RETRIES)
            generated, log_data = generate_newsletter_draft(
                content_type=payload["content_type"],
                pillar=payload["pillar"],
                claims=payload["claims"],
                context=payload["context"],
                segment=segment,
            )
            result = run_newsletter_compliance_checks(generated)
            if result.passed:
                return [
                    GeneratedCandidate(
                        content=result.corrected_content or generated["body_markdown"],
                        hashtags=[],
                        compliance_result={
                            "passed": True,
                            "checks_run": result.checks_run,
                            "segment": generated["segment"],
                            "subject": generated["subject"],
                            "preview_text": generated["preview_text"],
                            "hook": generated["hook"],
                            "proof_point": generated["proof_point"],
                            "product_update": generated["product_update"],
                            "cta": generated["cta"],
                            "body_html": generated.get("body_html"),
                        },
                        generation_trace=log_data["response"],
                        prompt_snapshot=log_data["prompt_snapshot"],
                    )
                ]
            last_failure_reason = result.failure_reason or "Newsletter compliance failed"
            logger.warning("Newsletter generation attempt %d failed compliance: %s", attempt, last_failure_reason)
        raise ValueError(last_failure_reason or "Newsletter compliance failed after retries")

    def _generate_blog(self, payload: dict[str, Any]) -> list[GeneratedCandidate]:
        blog_context = payload.get("blog_context") or {}
        topic = blog_context.get("topic") or payload.get("content_type") or "NTangible article"
        audience = blog_context.get("audience") or "coaches and operators"
        target_keywords = list(blog_context.get("target_keywords") or [topic])
        angle = blog_context.get("angle")
        source_notes = list(blog_context.get("source_notes") or [])

        last_failure_reason: str | None = None
        for attempt in range(1, MAX_COMPLIANCE_RETRIES + 2):
            if attempt > 1:
                logger.info("Blog generation retry %d/%d", attempt - 1, MAX_COMPLIANCE_RETRIES)
            generated = generate_blog_draft(
                topic=topic,
                audience=audience,
                target_keywords=target_keywords,
                angle=angle,
                source_notes=source_notes,
            )
            result = run_blog_compliance_checks(generated)
            if result.passed:
                return [
                    GeneratedCandidate(
                        content=result.corrected_body_markdown or generated["body_markdown"],
                        hashtags=[],
                        compliance_result={
                            "passed": True,
                            "checks_run": result.checks_run,
                            "title": generated["title"],
                            "slug": generated["slug"],
                            "meta_description": generated["meta_description"],
                            "body_html": generated["body_html"],
                            "target_keywords": generated["target_keywords"],
                            "headings": generated["headings"],
                            "audience": generated["audience"],
                            "topic": generated["topic"],
                            "angle": generated["angle"],
                            "excerpt": generated.get("excerpt"),
                            "word_count": generated["word_count"],
                            "source_notes": source_notes,
                        },
                        generation_trace={"generator": "blog_writer"},
                        prompt_snapshot=payload.get("user", ""),
                    )
                ]
            last_failure_reason = result.failure_reason or "Blog compliance failed"
            logger.warning("Blog generation attempt %d failed compliance: %s", attempt, last_failure_reason)
        raise ValueError(last_failure_reason or "Blog compliance failed after retries")
