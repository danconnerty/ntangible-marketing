# Phase 4: Instagram Integration + Visual Asset Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Canva-first Instagram lane that generates compliant Instagram drafts, renders media assets, publishes NTangible-owned content, and creates partner delivery packages using the shared workflow/review architecture already in this repo.

**Architecture:** Reuse `Workflow` + `TriggerEvent` + `ContentJob` + `DraftVariant` + `Asset` as the primary queue and provenance model, then add Instagram-specific tables for render jobs, generation audit logs, and partner delivery packages. Keep providers mock-first with swappable `instagram` and `canva` adapters so the feature is testable locally without live Meta or Canva credentials.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, Anthropic SDK, httpx, pytest

---

### Task 1: Add Instagram/Canva config and platform rules

**Files:**
- Create: `app/config_data/platforms/instagram.yaml`
- Modify: `app/config.py`
- Modify: `.env.example`
- Modify: `tests/conftest.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing config test**

```python
def test_platform_instagram_loads():
    data = load_yaml("platforms/instagram.yaml")
    assert "instagram" in data
    instagram = data["instagram"]
    assert instagram["max_caption_chars"] == 2200
    assert instagram["min_hashtags"] == 6
    assert instagram["max_hashtags"] == 10
    assert instagram["auto_publish_default_tier"] == "tier_1"
    assert instagram["template_families"]["education_carousel"]["min_slides"] == 5
```

- [ ] **Step 2: Run the single test and verify it fails**

Run: `pytest tests/test_config.py::test_platform_instagram_loads -v`
Expected: FAIL because `platforms/instagram.yaml` does not exist yet

- [ ] **Step 3: Add platform YAML and environment-backed settings**

```python
class Settings(BaseSettings):
    instagram_publisher: str = "mock"
    instagram_access_token: str = ""
    instagram_business_account_id: str = ""
    instagram_graph_api_version: str = "v23.0"
    canva_renderer: str = "mock"
    canva_api_key: str = ""
    canva_brand_template_set: str = "default"
    rendered_asset_root: str = "data/rendered_assets"
```

```yaml
instagram:
  max_caption_chars: 2200
  min_hashtags: 6
  max_hashtags: 10
  auto_publish_default_tier: tier_1
  posting_windows_et:
    - "Tue-Fri 11:00-13:00"
    - "Tue-Fri 19:00-21:00"
  template_families:
    athlete_spotlight:
      min_slides: 1
      max_slides: 1
    education_carousel:
      min_slides: 5
      max_slides: 8
    story_poll:
      min_slides: 1
      max_slides: 3
```

- [ ] **Step 4: Run the config tests**

Run: `pytest tests/test_config.py -v`
Expected: PASS with the new Instagram config coverage

- [ ] **Step 5: Commit**

```bash
git add app/config.py app/config_data/platforms/instagram.yaml .env.example tests/conftest.py tests/test_config.py
git commit -m "feat: add instagram and canva configuration"
```

### Task 2: Add Instagram persistence models and migration

**Files:**
- Create: `app/models/instagram.py`
- Modify: `app/models/asset.py`
- Modify: `app/models/workflow.py`
- Modify: `app/models/__init__.py`
- Create: `alembic/versions/20260406_add_instagram_phase4_tables.py`
- Modify: `tests/test_workflow_models.py`
- Create: `tests/test_instagram_models.py`

- [ ] **Step 1: Write the failing model tests**

```python
def test_instagram_render_job_fields():
    job = InstagramRenderJob(
        draft_variant_id=uuid.uuid4(),
        template_family=InstagramTemplateFamily.EDUCATION_CAROUSEL,
        status=InstagramRenderStatus.PENDING,
        input_payload={"slides": 5},
    )
    assert job.status == InstagramRenderStatus.PENDING


def test_partner_delivery_package_fields():
    package = PartnerDeliveryPackage(
        draft_variant_id=uuid.uuid4(),
        partner_name="Alliance Fastpitch",
        status=PartnerPackageStatus.NEEDS_REVIEW,
        delivery_channel=PartnerDeliveryChannel.DASHBOARD,
        asset_ids=[],
    )
    assert package.partner_name == "Alliance Fastpitch"
```

- [ ] **Step 2: Run the new model tests and verify they fail**

Run: `pytest tests/test_instagram_models.py -v`
Expected: FAIL because the Instagram models do not exist yet

- [ ] **Step 3: Add Instagram-specific tables and shared asset fields**

```python
class InstagramRenderStatus(str, enum.Enum):
    PENDING = "pending"
    RENDERING = "rendering"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NEEDS_DESIGN_REVIEW = "needs_design_review"


class InstagramGenerationLog(Base):
    __tablename__ = "instagram_generation_logs"
    draft_variant_id = mapped_column(UUID(as_uuid=True), ForeignKey("draft_variants.id"), nullable=False)
    prompt_snapshot = mapped_column(Text, nullable=False)
    response = mapped_column(JSONB, nullable=False)


class InstagramRenderJob(Base):
    __tablename__ = "instagram_render_jobs"
    draft_variant_id = mapped_column(UUID(as_uuid=True), ForeignKey("draft_variants.id"), nullable=False)
    template_family = mapped_column(template_family_enum, nullable=False)
    status = mapped_column(render_status_enum, nullable=False, default=InstagramRenderStatus.PENDING)
    input_payload = mapped_column(JSONB, nullable=False)


class PartnerDeliveryPackage(Base):
    __tablename__ = "partner_delivery_packages"
    draft_variant_id = mapped_column(UUID(as_uuid=True), ForeignKey("draft_variants.id"), nullable=False)
    partner_name = mapped_column(String(128), nullable=False)
    status = mapped_column(package_status_enum, nullable=False, default=PartnerPackageStatus.NEEDS_REVIEW)
    asset_ids = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
```

- [ ] **Step 4: Add migration for new tables and enum values**

Run: `pytest tests/test_instagram_models.py tests/test_workflow_models.py -v`
Expected: PASS with `render_failed` and `needs_design_review` present on `DraftState` and the new Instagram tables importable

- [ ] **Step 5: Commit**

```bash
git add app/models/instagram.py app/models/asset.py app/models/workflow.py app/models/__init__.py alembic/versions/20260406_add_instagram_phase4_tables.py tests/test_instagram_models.py tests/test_workflow_models.py
git commit -m "feat: add instagram persistence models"
```

### Task 3: Add Instagram writer, compliance, Canva renderer, and Instagram publisher

**Files:**
- Create: `app/agents/instagram_writer.py`
- Create: `app/agents/instagram_compliance.py`
- Create: `app/renderers/__init__.py`
- Create: `app/renderers/base.py`
- Create: `app/renderers/canva_factory.py`
- Create: `app/renderers/canva_mock.py`
- Create: `app/renderers/canva_http.py`
- Create: `app/publishers/instagram_base.py`
- Create: `app/publishers/instagram_factory.py`
- Create: `app/publishers/instagram_mock.py`
- Create: `app/publishers/instagram_http.py`
- Modify: `tests/conftest.py`
- Create: `tests/test_instagram_writer.py`
- Create: `tests/test_instagram_compliance.py`
- Create: `tests/test_instagram_renderer.py`
- Create: `tests/test_instagram_publisher.py`

- [ ] **Step 1: Write failing unit tests for the Instagram lane**

```python
def test_build_instagram_prompt_mentions_hook_body_cta():
    prompt = build_instagram_prompt("education_carousel", "thought_leadership", [], "Portal pressure")
    assert "hook" in prompt["system"].lower()
    assert "6-10 hashtags" in prompt["system"]


def test_instagram_rejects_too_few_hashtags():
    result = run_instagram_compliance_checks(
        draft={"caption": "Hook\nBody\nComment below.", "hashtags": ["#one", "#two"], "claim_keys_used": [], "asset_plan": {}},
        requested_claims=[],
    )
    assert not result.passed
    assert result.failed_check == "hashtags"
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run: `pytest tests/test_instagram_writer.py tests/test_instagram_compliance.py tests/test_instagram_renderer.py tests/test_instagram_publisher.py -v`
Expected: FAIL because the writer, compliance runner, renderer, and publisher do not exist yet

- [ ] **Step 3: Implement the writer/compliance/provider layer**

```python
INSTAGRAM_REQUIRED_FIELDS = {
    "caption",
    "content_type",
    "pillar",
    "claim_keys_used",
    "hashtags",
    "intent",
    "cta_type",
    "template_family",
    "asset_plan",
}
```

```python
class BaseCanvaRenderer:
    def render(self, request: CanvaRenderRequest) -> CanvaRenderResult:
        raise NotImplementedError
```

```python
class BaseInstagramPublisher:
    def publish_post(self, caption: str, asset_urls: list[str], publish_mode: str) -> InstagramPublishResult:
        raise NotImplementedError
```

- [ ] **Step 4: Run the new unit tests**

Run: `pytest tests/test_instagram_writer.py tests/test_instagram_compliance.py tests/test_instagram_renderer.py tests/test_instagram_publisher.py -v`
Expected: PASS with mock-first writer/compliance/render/publish behavior

- [ ] **Step 5: Commit**

```bash
git add app/agents/instagram_writer.py app/agents/instagram_compliance.py app/renderers app/publishers/instagram_base.py app/publishers/instagram_factory.py app/publishers/instagram_mock.py app/publishers/instagram_http.py tests/test_instagram_writer.py tests/test_instagram_compliance.py tests/test_instagram_renderer.py tests/test_instagram_publisher.py
git commit -m "feat: add instagram writer compliance and providers"
```

### Task 4: Add the Instagram pipeline and API routes

**Files:**
- Create: `app/api/instagram_schemas.py`
- Create: `app/api/instagram_routes.py`
- Create: `app/services/instagram_pipeline.py`
- Modify: `app/main.py`
- Modify: `app/services/review_queue.py`
- Modify: `app/publishers/__init__.py`
- Create: `tests/test_instagram_pipeline.py`
- Create: `tests/test_instagram_api.py`
- Modify: `tests/test_review_queue.py`

- [ ] **Step 1: Write failing pipeline and API tests**

```python
def test_generate_partner_package_routes_to_manual_review(monkeypatch, db_session):
    post = generate_instagram_item(
        {
            "content_type": "partner_content",
            "pillar": "client_proof",
            "approval_tier": "tier_2",
            "partner_name": "Alliance Fastpitch",
        },
        db_session,
    )
    assert post["draft"].state == DraftState.MANUAL_READY
    assert post["package"].status == PartnerPackageStatus.NEEDS_REVIEW
```

```python
def test_instagram_generate_endpoint_requires_auth():
    response = client.post("/instagram/generate", json={})
    assert response.status_code == 403
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run: `pytest tests/test_instagram_pipeline.py tests/test_instagram_api.py tests/test_review_queue.py -v`
Expected: FAIL because the service and routes do not exist yet

- [ ] **Step 3: Implement the workflow bootstrap, pipeline, and routes**

```python
def ensure_instagram_workflow(db: Session, request_data: dict) -> Workflow:
    slug = f"instagram-{request_data['content_type']}-{request_data['approval_tier']}"
    ...
```

```python
@router.post("/generate", dependencies=[Depends(verify_api_key)])
def generate_instagram(req: InstagramGenerateRequest, db: Session = Depends(get_db)):
    result = generate_instagram_item(req.model_dump(), db)
    return serialize_instagram_result(result)
```

- [ ] **Step 4: Run the focused Instagram API/pipeline tests**

Run: `pytest tests/test_instagram_pipeline.py tests/test_instagram_api.py tests/test_review_queue.py -v`
Expected: PASS with owned-channel auto-publish behavior and partner-package manual review behavior

- [ ] **Step 5: Commit**

```bash
git add app/api/instagram_schemas.py app/api/instagram_routes.py app/services/instagram_pipeline.py app/main.py app/services/review_queue.py app/publishers/__init__.py tests/test_instagram_pipeline.py tests/test_instagram_api.py tests/test_review_queue.py
git commit -m "feat: add instagram pipeline and api"
```

### Task 5: Verify the Phase 4 lane end to end

**Files:**
- Review: `app/agents/instagram_writer.py`
- Review: `app/agents/instagram_compliance.py`
- Review: `app/services/instagram_pipeline.py`
- Review: `app/api/instagram_routes.py`
- Review: `tests/test_instagram_*.py`

- [ ] **Step 1: Run the focused Instagram suite**

Run: `pytest tests/test_instagram_models.py tests/test_instagram_writer.py tests/test_instagram_compliance.py tests/test_instagram_renderer.py tests/test_instagram_publisher.py tests/test_instagram_pipeline.py tests/test_instagram_api.py -v`
Expected: PASS

- [ ] **Step 2: Run the full repository test suite**

Run: `pytest tests -v`
Expected: PASS, or only pre-existing unrelated failures in the dirty Phase 3 tree

- [ ] **Step 3: Inspect the diff**

Run: `git diff --stat`
Expected: Instagram/config/model/pipeline/test files only, plus the minimum required shared-file touches

- [ ] **Step 4: Commit final verification-only fixes if needed**

```bash
git add app tests alembic .env.example
git commit -m "test: finish instagram phase 4 verification"
```

- [ ] **Step 5: Summarize remaining runtime gaps**

```text
- Meta Graph publish path still requires real credentials and a Business account.
- Canva HTTP rendering still requires a real API key and approved templates.
- Alembic migration must be applied to a real Postgres instance before live smoke testing.
```
