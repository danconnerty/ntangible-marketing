# Phase 10 Newsletter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a canonical `newsletter` platform lane that generates segment-aware monthly newsletter drafts, routes them through the existing control-room review queue, and delivers approved drafts through a newsletter publisher abstraction with a Mailchimp adapter.

**Architecture:** Extend the existing workflow, draft, review, publication, analytics, and memory layers rather than creating a newsletter-only subsystem. Newsletter support should plug into the same `Workflow -> DraftVariant -> ReviewAction -> PublicationRecord` path as X, LinkedIn, and Instagram, while carrying subject, preview, segment, and ESP metadata inside validated config and existing JSON payload fields.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Alembic, Jinja2 templates, pytest, httpx

---

## File Structure

- Create: `app/agents/newsletter_writer.py`
  Purpose: generate structured newsletter drafts with subject, preview text, body, and segment metadata.
- Create: `app/agents/newsletter_compliance.py`
  Purpose: validate newsletter structure and deliverability readiness before drafts enter the queue.
- Create: `app/publishers/newsletter_base.py`
  Purpose: define the normalized newsletter publisher contract and result shape.
- Create: `app/publishers/newsletter_factory.py`
  Purpose: load the configured newsletter publisher.
- Create: `app/publishers/newsletter_mock.py`
  Purpose: provide deterministic local/test sending without network access.
- Create: `app/publishers/mailchimp_http.py`
  Purpose: implement one real ESP adapter using Mailchimp campaign create/content/send endpoints.
- Create: `tests/test_newsletter_writer.py`
  Purpose: unit tests for newsletter prompt construction and response parsing.
- Create: `tests/test_newsletter_compliance.py`
  Purpose: unit tests for required sections, spam-risk checks, and segment validation.
- Create: `tests/test_newsletter_publisher.py`
  Purpose: unit tests for publisher factory selection and Mailchimp payload behavior.
- Create: `tests/test_phase10_newsletter_integration.py`
  Purpose: integration tests for platform generation, review queue publish flow, and manual-card rendering.
- Modify: `app/models/workflow.py`
  Purpose: add `newsletter` to the canonical `Platform` enum.
- Modify: `app/schemas/workflow_config.py`
  Purpose: validate newsletter-specific routing and formatting fields without schema sprawl.
- Modify: `app/config.py`
  Purpose: add newsletter publisher and Mailchimp settings.
- Modify: `tests/conftest.py`
  Purpose: provide newsletter env defaults in tests.
- Modify: `app/services/platform_generation.py`
  Purpose: dispatch newsletter generation and return canonical draft candidates.
- Modify: `app/publishers/base.py`
  Purpose: allow generic publisher implementations to accept structured publish payload metadata.
- Modify: `app/publishers/__init__.py`
  Purpose: route `platform="newsletter"` through a newsletter adapter.
- Modify: `app/services/review_queue.py`
  Purpose: publish newsletter drafts through the generic review path and preserve newsletter metadata.
- Modify: `app/api/control_room_routes.py`
  Purpose: return newsletter subject, preview, and segment metadata in draft responses.
- Modify: `app/web/routes.py`
  Purpose: surface newsletter card metadata and detail-panel metadata in the control-room UI.
- Modify: `app/web/templates/partials/manual_card.html`
  Purpose: show newsletter subject, preview, and segment badges in the manual queue.
- Modify: `app/services/memory_retrieval.py`
  Purpose: include newsletter drafts in control-room memory with searchable subject/segment metadata.
- Modify: `app/services/analytics_ingest.py`
  Purpose: preserve newsletter publication metadata and accept newsletter platform rollups.
- Modify: `app/main.py`
  Purpose: ensure no route/import assumptions break after adding newsletter support.
- Modify: `tests/test_workflow_models.py`
  Purpose: verify `newsletter` is part of the canonical platform enum.
- Modify: `tests/test_review_queue.py`
  Purpose: verify newsletter drafts publish via the review queue and record publication metadata.
- Modify: `tests/test_web_manual_view.py`
  Purpose: verify newsletter cards render queue metadata correctly.
- Modify: `tests/test_publisher_factory.py`
  Purpose: verify the generic publisher factory supports newsletter.
- Create: `alembic/versions/20260406_add_newsletter_phase10_support.py`
  Purpose: migrate the platform enum and add any newsletter-specific draft/publication columns if required.

### Task 1: Add Newsletter Platform And Config Validation

**Files:**
- Modify: `app/models/workflow.py`
- Modify: `app/schemas/workflow_config.py`
- Modify: `app/config.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_workflow_models.py`

- [ ] **Step 1: Write the failing enum and config tests**

```python
from app.models.workflow import Platform
from app.schemas.workflow_config import WorkflowVersionConfig


def test_platform_enum_includes_newsletter():
    assert Platform.NEWSLETTER.value == "newsletter"


def test_workflow_config_accepts_newsletter_segment_fields():
    config = WorkflowVersionConfig(
        routing={"target_content_type": "monthly_newsletter", "target_audience_segment": "coaches_front_offices"},
        formatting={"require_subject_line": True, "max_sections": 4},
    )

    assert config.routing.target_audience_segment == "coaches_front_offices"
    assert config.formatting.require_subject_line is True
    assert config.formatting.max_sections == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_workflow_models.py -q`
Expected: FAIL because `Platform.NEWSLETTER` and newsletter-specific workflow config fields do not exist yet.

- [ ] **Step 3: Write the minimal enum, config, and settings changes**

```python
class Platform(str, enum.Enum):
    X = "x"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    NEWSLETTER = "newsletter"
```

```python
class FormattingConfig(BaseModel):
    platform_rules_override: dict | None = None
    max_hashtags: int | None = None
    max_chars: int | None = None
    require_subject_line: bool = False
    max_sections: int | None = None


class RoutingConfig(BaseModel):
    target_pillar: str | None = None
    target_intent: str | None = None
    target_content_type: str | None = None
    target_audience_segment: str | None = None
```

```python
class Settings(BaseSettings):
    newsletter_publisher: str = "mock"
    newsletter_default_from_name: str = "NTangible"
    newsletter_reply_to_email: str = ""
    newsletter_coaches_list_id: str = ""
    newsletter_partners_list_id: str = ""
    mailchimp_api_key: str = ""
    mailchimp_server_prefix: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_workflow_models.py -q`
Expected: PASS including the newsletter enum and config validation coverage.

- [ ] **Step 5: Commit**

```bash
git add app/models/workflow.py app/schemas/workflow_config.py app/config.py tests/conftest.py tests/test_workflow_models.py
git commit -m "feat: add newsletter platform and config support"
```

### Task 2: Build Newsletter Writer And Compliance

**Files:**
- Create: `app/agents/newsletter_writer.py`
- Create: `app/agents/newsletter_compliance.py`
- Create: `tests/test_newsletter_writer.py`
- Create: `tests/test_newsletter_compliance.py`

- [ ] **Step 1: Write the failing writer and compliance tests**

```python
from app.agents.newsletter_writer import build_newsletter_prompt, parse_newsletter_response
from app.agents.newsletter_compliance import run_newsletter_compliance_checks


def test_build_newsletter_prompt_mentions_required_sections():
    prompt = build_newsletter_prompt(
        content_type="monthly_newsletter",
        pillar="blind_spot",
        claims=[],
        context="April recruiting pressure data",
        segment="coaches_front_offices",
    )

    assert "coaches_front_offices" in prompt["system"]
    assert "subject" in prompt["system"].lower()
    assert "preview_text" in prompt["system"]
    assert "proof_point" in prompt["system"]


def test_parse_newsletter_response_requires_subject_preview_and_body():
    parse_newsletter_response(
        {
            "segment": "coaches_front_offices",
            "subject": "Pressure data from April",
            "preview_text": "What coaches should actually pay attention to.",
            "hook": "Most recruiting misses start before film review.",
            "proof_point": "Alliance coaches saw earlier separation on pressure profiles.",
            "product_update": "Workflow previews now show rejected examples.",
            "cta": "Book a demo",
            "body_markdown": "## April\nBody",
        }
    )


def test_newsletter_compliance_rejects_missing_required_sections():
    result = run_newsletter_compliance_checks(
        {
            "segment": "coaches_front_offices",
            "subject": "APRIL UPDATE!!!",
            "preview_text": "Preview",
            "hook": "",
            "proof_point": "",
            "product_update": "",
            "cta": "",
            "body_markdown": "Body only",
        }
    )

    assert result.passed is False
    assert result.failed_check == "required_sections"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_newsletter_writer.py tests/test_newsletter_compliance.py -q`
Expected: FAIL because the newsletter writer and compliance modules do not exist yet.

- [ ] **Step 3: Write minimal newsletter generation and compliance logic**

```python
NEWSLETTER_REQUIRED_FIELDS = {
    "segment",
    "subject",
    "preview_text",
    "hook",
    "proof_point",
    "product_update",
    "cta",
    "body_markdown",
}
```

```python
def run_newsletter_compliance_checks(draft: dict) -> ComplianceResult:
    subject = draft.get("subject", "").strip()
    preview_text = draft.get("preview_text", "").strip()
    segment = draft.get("segment", "").strip()
    required = {
        "hook": draft.get("hook", "").strip(),
        "proof_point": draft.get("proof_point", "").strip(),
        "product_update": draft.get("product_update", "").strip(),
        "cta": draft.get("cta", "").strip(),
    }

    if not subject or not preview_text or not segment:
        return ComplianceResult(passed=False, failed_check="metadata", failure_reason="Missing newsletter metadata")
    if any(not value for value in required.values()):
        return ComplianceResult(passed=False, failed_check="required_sections", failure_reason="Missing required newsletter sections")
    if subject == subject.upper() or subject.count("!") > 1:
        return ComplianceResult(passed=False, failed_check="spam_risk", failure_reason="Subject line reads like spam")

    return ComplianceResult(passed=True, corrected_content=draft["body_markdown"], checks_run=["metadata", "required_sections", "spam_risk"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_newsletter_writer.py tests/test_newsletter_compliance.py -q`
Expected: PASS for newsletter prompt, parse, and compliance validation.

- [ ] **Step 5: Commit**

```bash
git add app/agents/newsletter_writer.py app/agents/newsletter_compliance.py tests/test_newsletter_writer.py tests/test_newsletter_compliance.py
git commit -m "feat: add newsletter generation and compliance"
```

### Task 3: Integrate Newsletter Generation And Publisher Routing

**Files:**
- Modify: `app/services/platform_generation.py`
- Create: `app/publishers/newsletter_base.py`
- Create: `app/publishers/newsletter_factory.py`
- Create: `app/publishers/newsletter_mock.py`
- Create: `app/publishers/mailchimp_http.py`
- Modify: `app/publishers/base.py`
- Modify: `app/publishers/__init__.py`
- Create: `tests/test_newsletter_publisher.py`
- Modify: `tests/test_publisher_factory.py`
- Create: `tests/test_phase10_newsletter_integration.py`

- [ ] **Step 1: Write the failing platform-generation and publisher tests**

```python
from app.models.workflow import Platform
from app.services.platform_generation import PlatformGenerationService


def test_platform_generation_supports_newsletter(monkeypatch):
    workflow = type("Workflow", (), {"platform": Platform.NEWSLETTER})()
    version = type("Version", (), {"config": {}})()
    payload = {
        "content_type": "monthly_newsletter",
        "pillar": "blind_spot",
        "claims": [],
        "context": "April insights",
        "workflow_version_config": {"routing": {"target_audience_segment": "coaches_front_offices"}},
    }

    monkeypatch.setattr(
        "app.services.platform_generation.generate_newsletter_draft",
        lambda **kwargs: (
            {
                "segment": "coaches_front_offices",
                "subject": "Pressure data from April",
                "preview_text": "What coaches should know.",
                "hook": "Hook",
                "proof_point": "Proof",
                "product_update": "Update",
                "cta": "Reply to this email",
                "body_markdown": "Body",
            },
            {"response": {"raw_text": "{}"}, "prompt_snapshot": "snapshot"},
        ),
    )

    candidates = PlatformGenerationService(None).generate(workflow, version, payload)
    assert candidates[0].content == "Body"
    assert candidates[0].compliance_result["segment"] == "coaches_front_offices"
```

```python
def test_get_publisher_returns_newsletter_adapter(monkeypatch):
    from app.publishers import get_publisher
    import app.publishers as publishers_module

    class DummyNewsletterPublisher:
        def send_campaign(self, **kwargs):
            from app.publishers.newsletter_base import NewsletterPublishResult
            return NewsletterPublishResult(success=True, campaign_id="cmp-123", archive_url="https://mailchi.mp/test")

    monkeypatch.setattr(publishers_module, "get_newsletter_publisher", lambda: DummyNewsletterPublisher())
    publisher = get_publisher(platform="newsletter")
    result = publisher.publish(
        "Body",
        metadata={"subject": "Subject", "preview_text": "Preview", "segment": "coaches_front_offices"},
    )
    assert result.success is True
    assert result.platform_post_id == "cmp-123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_publisher_factory.py tests/test_phase10_newsletter_integration.py -q`
Expected: FAIL because newsletter generation and publisher routing are not wired yet.

- [ ] **Step 3: Write minimal newsletter generation and publisher integration**

```python
if workflow.platform == Platform.NEWSLETTER:
    return self._generate_newsletter(payload)
```

```python
def _generate_newsletter(self, payload: dict[str, Any]) -> list[GeneratedCandidate]:
    segment = payload["workflow_version_config"].get("routing", {}).get("target_audience_segment") or "coaches_front_offices"
    generated, log_data = generate_newsletter_draft(
        content_type=payload["content_type"],
        pillar=payload["pillar"],
        claims=payload["claims"],
        context=payload["context"],
        segment=segment,
    )
    result = run_newsletter_compliance_checks(generated)
    if not result.passed:
        raise ValueError(result.failure_reason or "Newsletter compliance failed")
    return [
        GeneratedCandidate(
            content=generated["body_markdown"],
            hashtags=[],
            compliance_result={
                "passed": True,
                "segment": generated["segment"],
                "subject": generated["subject"],
                "preview_text": generated["preview_text"],
                "hook": generated["hook"],
                "proof_point": generated["proof_point"],
                "product_update": generated["product_update"],
                "cta": generated["cta"],
                "checks_run": result.checks_run,
            },
            generation_trace=log_data["response"],
            prompt_snapshot=log_data["prompt_snapshot"],
        )
    ]
```

```python
class NewsletterPublisherAdapter(BasePublisher):
    def __init__(self, publisher) -> None:
        self.publisher = publisher

    def publish(self, text: str, media: str | None = None, metadata: dict | None = None) -> PostResult:
        payload = metadata or {}
        result = self.publisher.send_campaign(
            subject=payload["subject"],
            preview_text=payload.get("preview_text", ""),
            body_markdown=text,
            body_html=payload.get("body_html"),
            segment=payload["segment"],
            scheduled_at=payload.get("scheduled_at"),
        )
        return PostResult(
            success=result.success,
            platform_post_id=result.campaign_id,
            post_url=result.archive_url,
            posted_at=result.sent_at,
            error=result.error,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_publisher_factory.py tests/test_phase10_newsletter_integration.py -q`
Expected: PASS for newsletter platform generation and publisher factory coverage.

- [ ] **Step 5: Commit**

```bash
git add app/services/platform_generation.py app/publishers/base.py app/publishers/__init__.py app/publishers/newsletter_base.py app/publishers/newsletter_factory.py app/publishers/newsletter_mock.py app/publishers/mailchimp_http.py tests/test_newsletter_publisher.py tests/test_publisher_factory.py tests/test_phase10_newsletter_integration.py
git commit -m "feat: integrate newsletter generation and publisher routing"
```

### Task 4: Publish Newsletter Drafts Through The Review Queue And UI

**Files:**
- Modify: `app/services/review_queue.py`
- Modify: `app/api/control_room_routes.py`
- Modify: `app/web/routes.py`
- Modify: `app/web/templates/partials/manual_card.html`
- Modify: `tests/test_review_queue.py`
- Modify: `tests/test_web_manual_view.py`

- [ ] **Step 1: Write the failing review-queue and web-card tests**

```python
@patch("app.services.review_queue.get_publisher")
def test_post_now_newsletter_uses_subject_preview_and_segment_metadata(mock_get_pub):
    mock_pub = MagicMock()
    mock_pub.publish.return_value = PostResult(success=True, platform_post_id="cmp-123", post_url="https://mailchi.mp/archive")
    mock_get_pub.return_value = mock_pub

    draft = _make_draft(
        platform=Platform.NEWSLETTER,
        hashtags=[],
        compliance_result={"subject": "April pressure data", "preview_text": "Preview", "segment": "coaches_front_offices"},
    )
    db = _mock_db([draft])
    queue = ReviewQueue(db)

    queue.act(draft_id=draft.id, action=ReviewActionType.POST_NOW, actor="boss")

    mock_pub.publish.assert_called_once_with(
        draft.content,
        metadata={"subject": "April pressure data", "preview_text": "Preview", "segment": "coaches_front_offices"},
    )
```

```python
def test_manual_view_renders_newsletter_subject_and_segment(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_manual_cards",
        lambda db, limit=50: [{
            "id": "draft-1",
            "platform": "newsletter",
            "content": "Newsletter body",
            "hashtags": [],
            "created_label": "Apr 06, 09:00",
            "recommended_label": None,
            "workflow_name": "Monthly Newsletter",
            "workflow_slug": "monthly-newsletter",
            "version_number": 1,
            "trigger_label": "Calendar Trigger",
            "trigger_class": "trigger-calendar",
            "trigger_reason": "Generated from recurring calendar rule.",
            "state": "manual_ready",
            "notes": None,
            "expires_label": "Apr 06, 23:59",
            "newsletter_subject": "April pressure data coaches should notice",
            "newsletter_preview_text": "What this month changed.",
            "newsletter_segment": "coaches_front_offices",
        }],
    )

    response = client.get("/control-room/manual")
    assert "April pressure data coaches should notice" in response.text
    assert "coaches_front_offices" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_review_queue.py tests/test_web_manual_view.py -q`
Expected: FAIL because newsletter drafts are not published or rendered with metadata yet.

- [ ] **Step 3: Write minimal review-queue and UI serialization support**

```python
publish_metadata = None
if draft.platform == Platform.NEWSLETTER and isinstance(draft.compliance_result, dict):
    publish_metadata = {
        "subject": draft.compliance_result.get("subject"),
        "preview_text": draft.compliance_result.get("preview_text"),
        "segment": draft.compliance_result.get("segment"),
        "body_html": draft.compliance_result.get("body_html"),
    }
result = publisher.publish(draft.content, metadata=publish_metadata)
```

```python
"newsletter_subject": (draft.compliance_result or {}).get("subject"),
"newsletter_preview_text": (draft.compliance_result or {}).get("preview_text"),
"newsletter_segment": (draft.compliance_result or {}).get("segment"),
```

```html
{% if draft.newsletter_segment %}
<div class="text-muted text-small">{{ draft.newsletter_segment }}</div>
{% endif %}
{% if draft.newsletter_subject %}
<div class="draft-title">{{ draft.newsletter_subject }}</div>
{% endif %}
{% if draft.newsletter_preview_text %}
<div class="text-muted text-small">{{ draft.newsletter_preview_text }}</div>
{% endif %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_review_queue.py tests/test_web_manual_view.py -q`
Expected: PASS including newsletter send metadata and manual queue rendering.

- [ ] **Step 5: Commit**

```bash
git add app/services/review_queue.py app/api/control_room_routes.py app/web/routes.py app/web/templates/partials/manual_card.html tests/test_review_queue.py tests/test_web_manual_view.py
git commit -m "feat: add newsletter review queue and UI support"
```

### Task 5: Wire Newsletter Into Memory, Analytics, And Migration, Then Verify

**Files:**
- Modify: `app/services/memory_retrieval.py`
- Modify: `app/services/analytics_ingest.py`
- Create: `alembic/versions/20260406_add_newsletter_phase10_support.py`
- Modify: `tests/test_phase10_newsletter_integration.py`

- [ ] **Step 1: Write the failing memory and analytics tests**

```python
def test_memory_sync_indexes_newsletter_subject_and_segment(session, newsletter_draft):
    service = MemoryRetrievalService(session)
    created = service.sync_control_room_memory(limit=10)
    assert created >= 1

    results = service.search(query="pressure data coaches", platform=Platform.NEWSLETTER, limit=10)
    assert results[0]["platform"] == "newsletter"
    assert "coaches_front_offices" in results[0]["details"]["segment"]
```

```python
def test_record_publication_accepts_newsletter_platform(session, newsletter_draft):
    record = record_publication(
        session,
        draft=newsletter_draft,
        publish_result={"success": True, "platform_post_id": "cmp-123", "post_url": "https://mailchi.mp/archive"},
    )
    assert record.platform == Platform.NEWSLETTER
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_phase10_newsletter_integration.py -q`
Expected: FAIL because newsletter metadata is not yet indexed or persisted end to end.

- [ ] **Step 3: Write minimal memory, analytics, and migration support**

```python
search_text = " ".join(
    part
    for part in [
        title or "",
        draft.content or "",
        workflow.name if workflow else "",
        workflow.slug if workflow else "",
        (draft.compliance_result or {}).get("subject", ""),
        (draft.compliance_result or {}).get("preview_text", ""),
        (draft.compliance_result or {}).get("segment", ""),
    ]
    if part
)
```

```python
op.execute("ALTER TYPE platform_enum ADD VALUE IF NOT EXISTS 'newsletter'")
```

- [ ] **Step 4: Run focused and end-to-end verification**

Run: `pytest tests/test_workflow_models.py tests/test_newsletter_writer.py tests/test_newsletter_compliance.py tests/test_newsletter_publisher.py tests/test_phase10_newsletter_integration.py tests/test_review_queue.py tests/test_web_manual_view.py tests/test_publisher_factory.py -q`
Expected: PASS with newsletter coverage green.

Run: `pytest -q`
Expected: PASS, or only clearly pre-existing unrelated failures that were already present before Phase 10 work began.

- [ ] **Step 5: Commit**

```bash
git add app/services/memory_retrieval.py app/services/analytics_ingest.py alembic/versions/20260406_add_newsletter_phase10_support.py tests/test_phase10_newsletter_integration.py
git commit -m "feat: finish phase 10 newsletter lane"
```
