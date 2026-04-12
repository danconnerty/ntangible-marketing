import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.agents.compliance import ComplianceResult
from app.models.asset import Asset
from app.models.brain import EntityNode, KnowledgeNode
from app.models.instagram import InstagramRenderStatus, PartnerPackageStatus
from app.renderers.base import CanvaRenderResult, RenderedAsset
from app.publishers.instagram_base import InstagramPublishResult
from app.services.instagram_pipeline import (
    build_instagram_caption,
    determine_draft_status,
    generate_instagram_item,
    publish_instagram_variant,
    STATUS_REVIEW_REQUIRED,
    STATUS_SCHEDULED,
    STATUS_ACTIVE,
    STATUS_PUBLISHING,
)


class FakeDB:
    def __init__(self):
        self.added: list[object] = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        return None

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        return None


def _workflow_context(mode: str):
    """Create brain-native workflow entity, config node, and trigger node."""
    workflow_entity = EntityNode(
        id=uuid.uuid4(),
        entity_type="workflow",
        canonical_name="Instagram Workflow",
        slug=f"instagram-{mode}",
        status="active",
        metadata_={"platform": "instagram", "content_type": "partner_content", "mode": mode},
    )
    config_node = KnowledgeNode(
        id=uuid.uuid4(),
        kind="workflow_config",
        title=f"Config: instagram-{mode}",
        status="active",
        metadata_={"workflow_entity_id": str(workflow_entity.id), "version_number": 1},
    )
    trigger_node = KnowledgeNode(
        id=uuid.uuid4(),
        kind="trigger",
        title="Manual trigger",
        status="active",
        metadata_={
            "trigger_type": "manual",
            "workflow_entity_id": str(workflow_entity.id),
            "request": "Create an Instagram package",
        },
    )
    return workflow_entity, config_node, trigger_node


def test_determine_draft_status_follows_workflow_mode():
    assert determine_draft_status("manual") == STATUS_REVIEW_REQUIRED
    assert determine_draft_status("automatic") == STATUS_SCHEDULED


def test_determine_draft_status_partner_always_review_required():
    assert determine_draft_status("automatic", partner_name="Alliance Fastpitch") == STATUS_REVIEW_REQUIRED


def test_build_instagram_caption_places_hashtags_at_end():
    caption = build_instagram_caption("Hook\nBody\nComment below.", ["#one", "#two"])
    assert caption.endswith("#one #two")


def test_generate_partner_package_routes_to_manual_review(monkeypatch):
    db = FakeDB()
    workflow_entity, config_node, trigger_node = _workflow_context("manual")

    monkeypatch.setattr(
        "app.services.instagram_pipeline.ensure_instagram_workflow_context",
        lambda request_data, db: (workflow_entity, config_node, trigger_node),
    )
    monkeypatch.setattr(
        "app.services.instagram_pipeline.generate_instagram_post",
        lambda content_type, pillar, claims, context: (
            {
                "caption": "Pressure is visible.\nAlliance events expose it quickly.\nComment if your staff wants cleaner signal.",
                "content_type": "partner_content",
                "pillar": "client_proof",
                "claim_keys_used": [],
                "hashtags": ["#one", "#two", "#three", "#four", "#five", "#six"],
                "intent": "partner",
                "cta_type": "comment",
                "template_family": "partner_event_spotlight",
                "asset_plan": {
                    "text_fields": {"headline": "Alliance pressure snapshot"},
                    "numeric_fields": {},
                    "output_asset_roles": ["slide_1"],
                    "output_dimensions": {"width": 1080, "height": 1350},
                },
            },
            {
                "prompt_snapshot": "system\n---\nuser",
                "response": {"raw_text": "{}"},
                "model": "claude-sonnet-4-6",
                "tokens_in": 100,
                "tokens_out": 200,
                "cost_estimate": 0.01,
                "duration_ms": 1000,
            },
        ),
    )
    monkeypatch.setattr(
        "app.services.instagram_pipeline.run_instagram_compliance_checks",
        lambda draft, requested_claims: ComplianceResult(
            passed=True,
            corrected_content=draft["caption"],
            corrected_hashtags=draft["hashtags"],
            checks_run=["hashtags"],
        ),
    )

    class MockRenderer:
        def render(self, request):
            return CanvaRenderResult(
                success=True,
                provider_job_id="render-1",
                assets=[
                    RenderedAsset(
                        asset_role="slide_1",
                        storage_path="/tmp/slide-1.png",
                        url="https://cdn.example.com/slide-1.png",
                    )
                ],
            )

    monkeypatch.setattr("app.services.instagram_pipeline.get_canva_renderer", lambda: MockRenderer())
    monkeypatch.setattr("app.services.instagram_pipeline.get_instagram_publisher", lambda: None)

    result = generate_instagram_item(
        {
            "content_type": "partner_content",
            "pillar": "client_proof",
            "approval_tier": "tier_2",
            "partner_name": "Alliance Fastpitch",
            "source_event_type": "leaderboard_published",
            "claims": [],
            "context": "Alliance leaderboard update",
            "canva_template_id": "tmpl-123",
        },
        db,
    )

    assert result["draft"].status == STATUS_REVIEW_REQUIRED
    assert result["package"] is not None
    assert result["package"].status == PartnerPackageStatus.NEEDS_REVIEW
    assert result["render_job"].status == InstagramRenderStatus.SUCCEEDED


def test_generate_tier_1_owned_post_stays_manual_when_workflow_is_manual(monkeypatch):
    db = FakeDB()
    workflow_entity, config_node, trigger_node = _workflow_context("manual")

    monkeypatch.setattr(
        "app.services.instagram_pipeline.ensure_instagram_workflow_context",
        lambda request_data, db: (workflow_entity, config_node, trigger_node),
    )
    monkeypatch.setattr(
        "app.services.instagram_pipeline.generate_instagram_post",
        lambda content_type, pillar, claims, context: (
            {
                "caption": "Pressure is visible.\nMost staffs still guess.\nComment if you want cleaner signal.",
                "content_type": "stat_card",
                "pillar": "thought_leadership",
                "claim_keys_used": [],
                "hashtags": ["#one", "#two", "#three", "#four", "#five", "#six"],
                "intent": "brand",
                "cta_type": "comment",
                "template_family": "bold_statement",
                "asset_plan": {
                    "text_fields": {"headline": "Pressure reveals what training hides"},
                    "numeric_fields": {},
                    "output_asset_roles": ["primary"],
                },
            },
            {
                "prompt_snapshot": "system\n---\nuser",
                "response": {"raw_text": "{}"},
                "model": "claude-sonnet-4-6",
                "tokens_in": 100,
                "tokens_out": 200,
                "cost_estimate": 0.01,
                "duration_ms": 1000,
            },
        ),
    )
    monkeypatch.setattr(
        "app.services.instagram_pipeline.run_instagram_compliance_checks",
        lambda draft, requested_claims: ComplianceResult(
            passed=True,
            corrected_content=draft["caption"],
            corrected_hashtags=draft["hashtags"],
            checks_run=["hashtags"],
        ),
    )

    class MockRenderer:
        def render(self, request):
            return CanvaRenderResult(
                success=True,
                provider_job_id="render-1",
                assets=[
                    RenderedAsset(
                        asset_role="primary",
                        storage_path="/tmp/post.png",
                        url="https://cdn.example.com/post.png",
                    )
                ],
            )

    class MockPublisher:
        def publish_post(self, caption, asset_urls, publish_mode="feed"):
            raise AssertionError("manual workflows should not auto-publish")

    monkeypatch.setattr("app.services.instagram_pipeline.get_canva_renderer", lambda: MockRenderer())
    monkeypatch.setattr("app.services.instagram_pipeline.get_instagram_publisher", lambda: MockPublisher())

    result = generate_instagram_item(
        {
            "content_type": "stat_card",
            "pillar": "thought_leadership",
            "approval_tier": "tier_1",
            "claims": [],
            "context": "Pressure is visible",
            "canva_template_id": "tmpl-123",
        },
        db,
    )

    assert result["draft"].status == STATUS_REVIEW_REQUIRED
    assert result["draft"].metadata_.get("platform_post_id") is None


def test_publish_instagram_variant_uses_active_connection_target(monkeypatch):
    draft_id = uuid.uuid4()
    draft = KnowledgeNode(
        id=draft_id,
        kind="draft",
        title="Instagram draft",
        content="Pressure is visible.",
        status=STATUS_REVIEW_REQUIRED,
        metadata_={
            "platform": "instagram",
            "hashtags": ["#one", "#two"],
            "compliance_result": {"publish_mode": "carousel"},
        },
    )
    asset = Asset(
        id=uuid.uuid4(),
        draft_variant_id=draft_id,
        workflow_id=uuid.uuid4(),
        asset_type="instagram_media",
        asset_role="slide_1",
        provider="canva",
        render_status="succeeded",
        sort_order=0,
        storage_path="/tmp/slide-1.png",
        url="https://cdn.example.com/slide-1.png",
    )
    db = MagicMock()

    def query_side_effect(model):
        query = MagicMock()
        if model is KnowledgeNode:
            query.filter.return_value.first.return_value = draft
        elif model is Asset:
            query.filter.return_value.order_by.return_value.all.return_value = [asset]
        return query

    db.query.side_effect = query_side_effect

    captured: dict[str, object] = {}

    class FakeConnectionService:
        def __init__(self, incoming_db):
            assert incoming_db is db

        def resolve_active_publish_target(self, channel):
            assert channel == "instagram"
            return {
                "channel": "instagram",
                "connection": object(),
                "destination": object(),
                "credentials": {"access_token": "runtime-instagram-token"},
                "config": {
                    "provider_key": "instagram",
                    "business_account_id": "ig-business-123",
                },
            }

    def fake_get_instagram_publisher(*, runtime_config=None):
        captured["runtime_config"] = runtime_config
        return MagicMock(
            publish_post=MagicMock(
                return_value=InstagramPublishResult(
                    success=True,
                    post_id="ig-123",
                    post_url="https://instagram.com/p/ig-123",
                )
            )
        )

    monkeypatch.setattr(
        "app.services.instagram_pipeline.PublishingConnectionService",
        FakeConnectionService,
    )
    monkeypatch.setattr(
        "app.services.instagram_pipeline.get_instagram_publisher",
        fake_get_instagram_publisher,
    )

    result = publish_instagram_variant(draft.id, db)

    assert result.status == STATUS_ACTIVE
    assert captured["runtime_config"] == {
        "access_token": "runtime-instagram-token",
        "provider_key": "instagram",
        "business_account_id": "ig-business-123",
    }


def test_generate_tier_1_owned_post_auto_publishes(monkeypatch):
    db = FakeDB()
    workflow_entity, config_node, trigger_node = _workflow_context("automatic")

    monkeypatch.setattr(
        "app.services.instagram_pipeline.ensure_instagram_workflow_context",
        lambda request_data, db: (workflow_entity, config_node, trigger_node),
    )
    monkeypatch.setattr(
        "app.services.instagram_pipeline.generate_instagram_post",
        lambda content_type, pillar, claims, context: (
            {
                "caption": "Pressure is visible.\nMost staffs still guess.\nComment if you want cleaner signal.",
                "content_type": "stat_card",
                "pillar": "thought_leadership",
                "claim_keys_used": [],
                "hashtags": ["#one", "#two", "#three", "#four", "#five", "#six"],
                "intent": "brand",
                "cta_type": "comment",
                "template_family": "bold_statement",
                "asset_plan": {
                    "text_fields": {"headline": "Pressure reveals what training hides"},
                    "numeric_fields": {},
                    "output_asset_roles": ["primary"],
                },
            },
            {
                "prompt_snapshot": "system\n---\nuser",
                "response": {"raw_text": "{}"},
                "model": "claude-sonnet-4-6",
                "tokens_in": 100,
                "tokens_out": 200,
                "cost_estimate": 0.01,
                "duration_ms": 1000,
            },
        ),
    )
    monkeypatch.setattr(
        "app.services.instagram_pipeline.run_instagram_compliance_checks",
        lambda draft, requested_claims: ComplianceResult(
            passed=True,
            corrected_content=draft["caption"],
            corrected_hashtags=draft["hashtags"],
            checks_run=["hashtags"],
        ),
    )

    class MockRenderer:
        def render(self, request):
            return CanvaRenderResult(
                success=True,
                provider_job_id="render-1",
                assets=[
                    RenderedAsset(
                        asset_role="primary",
                        storage_path="/tmp/post.png",
                        url="https://cdn.example.com/post.png",
                    )
                ],
            )

    class MockPublisher:
        def publish_post(self, caption, asset_urls, publish_mode="feed"):
            assert publish_mode == "feed"
            return InstagramPublishResult(
                success=True,
                post_id="ig-123",
                post_url="https://www.instagram.com/p/ig-123/",
                posted_at=datetime.now(timezone.utc).isoformat(),
            )

    monkeypatch.setattr("app.services.instagram_pipeline.get_canva_renderer", lambda: MockRenderer())
    monkeypatch.setattr("app.services.instagram_pipeline.get_instagram_publisher", lambda: MockPublisher())

    result = generate_instagram_item(
        {
            "content_type": "stat_card",
            "pillar": "thought_leadership",
            "approval_tier": "tier_1",
            "claims": [],
            "context": "Pressure is visible",
            "canva_template_id": "tmpl-123",
        },
        db,
    )

    assert result["draft"].status == STATUS_ACTIVE
    assert result["draft"].metadata_.get("platform_post_id") == "ig-123"
