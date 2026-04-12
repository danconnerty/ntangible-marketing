import uuid

from app.models.workflow import (
    DraftState,
    Platform,
    Workflow,
    WorkflowMode,
    WorkflowVersion,
)
from app.models.trigger import (
    CalendarRule,
    PartnerSource,
    PartnerSourceType,
    TriggerEvent,
    TriggerProcessingStatus,
    TriggerType,
)
from app.models.review import (
    ContentJob,
    DraftVariant,
    ReviewAction,
    ReviewActionType,
)
from app.models.asset import Asset
from app.schemas.workflow_config import WorkflowVersionConfig


# --- Enum value tests ---


def test_workflow_mode_enum():
    assert WorkflowMode.MANUAL.value == "manual"
    assert WorkflowMode.AUTOMATIC.value == "automatic"


def test_platform_enum():
    assert Platform.X.value == "x"
    assert Platform.LINKEDIN.value == "linkedin"
    assert Platform.INSTAGRAM.value == "instagram"
    assert Platform.NEWSLETTER.value == "newsletter"
    assert Platform.BLOG.value == "blog"


def test_draft_state_enum():
    assert DraftState.GENERATED.value == "generated"
    assert DraftState.MANUAL_READY.value == "manual_ready"
    assert DraftState.SCHEDULED_MANUAL.value == "scheduled_manual"
    assert DraftState.AUTOMATIC_READY.value == "automatic_ready"
    assert DraftState.RENDER_FAILED.value == "render_failed"
    assert DraftState.NEEDS_DESIGN_REVIEW.value == "needs_design_review"
    assert DraftState.PUBLISHING.value == "publishing"
    assert DraftState.PUBLISHED.value == "published"
    assert DraftState.FAILED.value == "failed"
    assert DraftState.REJECTED.value == "rejected"
    assert DraftState.EXPIRED.value == "expired"


def test_trigger_type_enum():
    assert TriggerType.CALENDAR.value == "calendar"
    assert TriggerType.EXTERNAL.value == "external"
    assert TriggerType.MANUAL_REQUEST.value == "manual_request"


def test_partner_source_type_enum():
    assert PartnerSourceType.WEBHOOK.value == "webhook"
    assert PartnerSourceType.PORTAL.value == "portal"
    assert PartnerSourceType.SPREADSHEET.value == "spreadsheet"


def test_trigger_processing_status_enum():
    assert TriggerProcessingStatus.RECEIVED.value == "received"
    assert TriggerProcessingStatus.PROCESSED.value == "processed"
    assert TriggerProcessingStatus.FAILED.value == "failed"


def test_review_action_type_enum():
    assert ReviewActionType.POST_NOW.value == "post_now"
    assert ReviewActionType.SCHEDULE.value == "schedule"
    assert ReviewActionType.REJECT.value == "reject"
    assert ReviewActionType.EXPIRE.value == "expire"
    assert ReviewActionType.PAUSE.value == "pause"
    assert ReviewActionType.MOVE_TO_MANUAL.value == "move_to_manual"


# --- Model instantiation tests ---


def test_workflow_fields():
    wf = Workflow(
        id=uuid.uuid4(),
        name="Tuesday LinkedIn TL",
        slug="tuesday-linkedin-tl",
        description="Weekly thought leadership post",
        mode=WorkflowMode.MANUAL,
        platform=Platform.LINKEDIN,
        content_type="thought_leadership",
        enabled=True,
    )
    assert wf.name == "Tuesday LinkedIn TL"
    assert wf.mode == WorkflowMode.MANUAL
    assert wf.platform == Platform.LINKEDIN
    assert wf.active_version_id is None


def test_workflow_version_fields():
    config = WorkflowVersionConfig().model_dump()
    ver = WorkflowVersion(
        id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        version_number=1,
        config=config,
        version_note="Initial version",
        author="human",
        is_active=True,
    )
    assert ver.version_number == 1
    assert ver.author == "human"
    assert ver.config["prompt"]["system_prompt_additions"] == ""


def test_calendar_rule_fields():
    rule = CalendarRule(
        id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        cron_expression="0 8 * * 2",
        timezone="America/New_York",
        enabled=True,
    )
    assert rule.cron_expression == "0 8 * * 2"
    assert rule.timezone == "America/New_York"


def test_trigger_event_fields():
    event = TriggerEvent(
        id=uuid.uuid4(),
        trigger_type=TriggerType.CALENDAR,
        workflow_id=uuid.uuid4(),
        source_payload={"rule": "tuesday"},
    )
    assert event.trigger_type == TriggerType.CALENDAR
    assert event.calendar_rule_id is None


def test_partner_source_fields():
    source = PartnerSource(
        id=uuid.uuid4(),
        slug="alliance_fastpitch",
        display_name="Alliance Fastpitch",
        source_type=PartnerSourceType.WEBHOOK,
        webhook_secret="secret",
        enabled=True,
    )
    assert source.slug == "alliance_fastpitch"
    assert source.source_type == PartnerSourceType.WEBHOOK
    assert source.enabled is True


def test_external_trigger_event_partner_fields():
    event = TriggerEvent(
        id=uuid.uuid4(),
        trigger_type=TriggerType.EXTERNAL,
        workflow_id=uuid.uuid4(),
        partner_source_id=uuid.uuid4(),
        external_event_type="commitment_update",
        external_event_id="evt-123",
        processing_status=TriggerProcessingStatus.RECEIVED,
        dedupe_key="alliance_fastpitch:evt-123:x",
        source_payload={"athlete_name": "Jane Smith"},
    )
    assert event.partner_source_id is not None
    assert event.external_event_type == "commitment_update"
    assert event.processing_status == TriggerProcessingStatus.RECEIVED
    assert event.dedupe_key == "alliance_fastpitch:evt-123:x"


def test_content_job_fields():
    job = ContentJob(
        id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        workflow_version_id=uuid.uuid4(),
        trigger_event_id=uuid.uuid4(),
        prompt_snapshot={"system": "test", "user": "test"},
        status="running",
    )
    assert job.status == "running"
    assert job.prompt_snapshot["system"] == "test"
    assert job.retrieved_memory_ids is None


def test_draft_variant_fields():
    draft = DraftVariant(
        id=uuid.uuid4(),
        content_job_id=uuid.uuid4(),
        platform=Platform.X,
        content="73% of athletes scoring above 800 CF were named All-American.",
        hashtags=["#ClutchFactor"],
        state=DraftState.MANUAL_READY,
        timezone="America/New_York",
        compliance_result={"passed": True},
    )
    assert draft.platform == Platform.X
    assert draft.state == DraftState.MANUAL_READY
    assert draft.platform_post_id is None


def test_draft_variant_without_explicit_state():
    """State defaults are applied at DB level; Python-side default is None when not set."""
    draft = DraftVariant(
        id=uuid.uuid4(),
        content_job_id=uuid.uuid4(),
        platform=Platform.LINKEDIN,
        content="Test post",
    )
    # The server_default handles this at insert time; in-memory it's None
    assert draft.state is None or draft.state == DraftState.GENERATED


def test_review_action_fields():
    action = ReviewAction(
        id=uuid.uuid4(),
        draft_variant_id=uuid.uuid4(),
        action=ReviewActionType.REJECT,
        actor="boss",
        notes="Tone is off",
    )
    assert action.action == ReviewActionType.REJECT
    assert action.notes == "Tone is off"


def test_asset_fields():
    asset = Asset(
        id=uuid.uuid4(),
        draft_variant_id=uuid.uuid4(),
        asset_type="image",
        filename="hero.png",
        storage_path="/data/assets/hero.png",
        mime_type="image/png",
    )
    assert asset.asset_type == "image"
    assert asset.workflow_id is None


# --- Database enum registration tests ---


def test_workflow_table_enums():
    enums = Workflow.__table__.c.mode.type.enums
    assert "manual" in enums
    assert "automatic" in enums


def test_draft_variant_table_enums():
    state_enums = DraftVariant.__table__.c.state.type.enums
    assert "manual_ready" in state_enums
    assert "render_failed" in state_enums
    assert "needs_design_review" in state_enums
    assert "expired" in state_enums

    platform_enums = DraftVariant.__table__.c.platform.type.enums
    assert "x" in platform_enums
    assert "linkedin" in platform_enums


# --- WorkflowVersionConfig Pydantic tests ---


def test_workflow_version_config_defaults():
    config = WorkflowVersionConfig()
    assert config.prompt.system_prompt_additions == ""
    assert config.retrieval.max_examples == 5
    assert config.formatting.max_hashtags is None
    assert config.routing.target_pillar is None
    assert config.timing.publish_delay_minutes == 0
    assert config.assets.require_image is False
    assert config.cta.cta_preferences == []


def test_workflow_version_config_roundtrip():
    config = WorkflowVersionConfig(
        prompt={"system_prompt_additions": "Be punchy.", "tone_notes": "contrarian"},
        retrieval={"max_examples": 3, "filter_by_pillar": True},
        cta={"cta_preferences": ["DM us", "Link in bio"]},
    )
    dumped = config.model_dump()
    restored = WorkflowVersionConfig(**dumped)
    assert restored.prompt.system_prompt_additions == "Be punchy."
    assert restored.retrieval.max_examples == 3
    assert restored.cta.cta_preferences == ["DM us", "Link in bio"]


def test_workflow_version_config_partial_override():
    """Only override some sections, rest get defaults."""
    config = WorkflowVersionConfig(prompt={"tone_notes": "aggressive"})
    assert config.prompt.tone_notes == "aggressive"
    assert config.prompt.system_prompt_additions == ""
    assert config.retrieval.max_examples == 5


def test_workflow_version_config_accepts_newsletter_fields():
    config = WorkflowVersionConfig(
        routing={
            "target_content_type": "monthly_newsletter",
            "target_audience_segment": "coaches_front_offices",
        },
        formatting={
            "require_subject_line": True,
            "max_sections": 4,
        },
    )

    assert config.routing.target_content_type == "monthly_newsletter"
    assert config.routing.target_audience_segment == "coaches_front_offices"
    assert config.formatting.require_subject_line is True
    assert config.formatting.max_sections == 4
