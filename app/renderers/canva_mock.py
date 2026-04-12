import json
import logging
import uuid
from pathlib import Path

from app.config import get_canva_template, get_settings
from app.renderers.base import BaseCanvaRenderer, CanvaRenderRequest, CanvaRenderResult, RenderedAsset

logger = logging.getLogger(__name__)


class MockCanvaRenderer(BaseCanvaRenderer):
    def __init__(self):
        self.jobs: list[dict] = []

    def render(self, request: CanvaRenderRequest) -> CanvaRenderResult:
        root = Path(get_settings().rendered_asset_root)
        output_dir = root / request.template_family
        output_dir.mkdir(parents=True, exist_ok=True)

        # Look up the template configuration so we can log what WOULD be used
        template_config = get_canva_template(
            self._guess_platform(request), request.template_family
        )
        configured_template_id = (
            template_config["template_id"] if template_config else None
        )
        expected_data_fields = (
            template_config["data_fields"] if template_config else []
        )

        logger.info(
            "MockCanvaRenderer: template_family=%s  canva_template_id=%s  "
            "configured_template_id=%s  expected_fields=%s  text_fields=%s  "
            "numeric_fields=%s",
            request.template_family,
            request.canva_template_id,
            configured_template_id,
            expected_data_fields,
            list(request.text_fields.keys()),
            list(request.numeric_fields.keys()),
        )

        job_id = str(uuid.uuid4())
        roles = request.output_asset_roles or ["primary"]
        assets: list[RenderedAsset] = []

        for role in roles:
            filename = f"{request.template_family}-{role}-{job_id[:8]}.png"
            storage_path = output_dir / filename
            mock_manifest = {
                "mock": True,
                "template_family": request.template_family,
                "brand_mode": request.brand_mode,
                "canva_template_id": request.canva_template_id,
                "configured_template_id": configured_template_id,
                "expected_data_fields": expected_data_fields,
                "text_fields": request.text_fields,
                "numeric_fields": request.numeric_fields,
                "image_references": request.image_references,
                "asset_role": role,
                "title": request.title,
            }
            storage_path.write_text(
                json.dumps(mock_manifest, indent=2),
                encoding="utf-8",
            )
            placeholder_url = (
                f"https://mock.canva.local/{request.template_family}/{filename}"
            )
            assets.append(
                RenderedAsset(
                    asset_role=role,
                    storage_path=str(storage_path),
                    url=placeholder_url,
                )
            )
            logger.info(
                "MockCanvaRenderer: created placeholder asset role=%s  url=%s",
                role,
                placeholder_url,
            )

        self.jobs.append(
            {
                "job_id": job_id,
                "request": request,
                "asset_count": len(assets),
                "configured_template_id": configured_template_id,
                "expected_data_fields": expected_data_fields,
            }
        )
        design_id = f"mock-design-{job_id[:8]}"
        return CanvaRenderResult(
            success=True,
            assets=assets,
            provider_job_id=job_id,
            design_id=design_id,
            design_url=f"https://mock.canva.local/design/{design_id}/edit",
        )

    @staticmethod
    def _guess_platform(request: CanvaRenderRequest) -> str:
        """Infer platform from the template family so we can look up the right
        section in ``canva_templates.yaml``."""
        family = request.template_family.lower()
        if family in (
            "athlete_spotlight",
            "commitment_post",
            "clutch_certified",
            "event_leaderboard",
            "bold_statement",
            "education_carousel",
            "story_poll",
            "story_repost",
            "partner_event_spotlight",
        ):
            return "instagram"
        if family in ("stat_card", "quote_graphic"):
            return "x"
        if family in ("thought_leadership_header", "partner_announcement"):
            return "linkedin"
        if family in ("athlete_score_graphic",):
            return "shareable"
        # Fall back: try each platform section
        from app.config import get_canva_templates

        templates = get_canva_templates().get("templates", {})
        for platform, families in templates.items():
            if family in families:
                return platform
        return "unknown"
