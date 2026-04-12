# Phase 3: LinkedIn Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a LinkedIn-only pipeline that generates on-brand LinkedIn posts, applies deterministic brand/factual compliance, auto-publishes Tier 1 items, and holds Tier 2/Tier 3 items for manual approve/reject/publish APIs, without adding dashboard or scheduler work.

**Architecture:** Add a parallel LinkedIn path beside the existing X pipeline instead of refactoring the X code first. The LinkedIn path gets its own prompt builder, compliance runner, models, publisher adapters, and API routes, but it reuses shared brand voice, claim config, auth, and database setup so the future queue/dashboard can call the same endpoints later.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Anthropic SDK, httpx, pytest

---

## File Structure

- Modify: `app/config.py`
  Add LinkedIn settings/env support.
- Modify: `.env.example`
  Document LinkedIn publisher configuration.
- Create: `app/config_data/platforms/linkedin.yaml`
  LinkedIn-specific character, hashtag, and approval defaults.
- Create: `alembic/versions/20260406_add_linkedin_tables.py`
  Migration for LinkedIn tables.
- Create: `app/models/linkedin.py`
  SQLAlchemy enums and tables for LinkedIn posts and generation logs.
- Modify: `app/models/__init__.py`
  Export the new LinkedIn models.
- Create: `app/agents/linkedin_writer.py`
  LinkedIn prompt assembly, response parsing, and Claude call wrapper.
- Create: `app/agents/linkedin_compliance.py`
  Deterministic LinkedIn compliance checks using the same claim verification rules as X.
- Create: `app/publishers/linkedin_base.py`
  LinkedIn publish result contract.
- Create: `app/publishers/linkedin_mock.py`
  Dev/test mock LinkedIn publisher.
- Create: `app/publishers/linkedin_http.py`
  Official LinkedIn `rest/posts` adapter using bearer token + org URN.
- Create: `app/publishers/linkedin_factory.py`
  Chooses mock or HTTP publisher from config.
- Create: `app/services/linkedin_pipeline.py`
  Generation, approval-tier routing, and publish orchestration.
- Create: `app/services/__init__.py`
  Service package marker.
- Create: `app/api/linkedin_schemas.py`
  Request/response Pydantic schemas for LinkedIn endpoints.
- Create: `app/api/linkedin_routes.py`
  Authenticated LinkedIn generate/review/publish endpoints.
- Modify: `app/main.py`
  Include the LinkedIn router.
- Modify: `tests/conftest.py`
  Seed LinkedIn env vars for tests.
- Create: `tests/test_linkedin_models.py`
  Enum/model structure tests.
- Create: `tests/test_linkedin_writer.py`
  Prompt + response parsing tests.
- Create: `tests/test_linkedin_compliance.py`
  LinkedIn compliance tests.
- Create: `tests/test_linkedin_publisher.py`
  Mock publisher + factory tests.
- Create: `tests/test_linkedin_api.py`
  Endpoint contract tests with dependency overrides and monkeypatching.

### Task 1: Add LinkedIn Configuration And Persistence

**Files:**
- Modify: `.env.example`
- Modify: `app/config.py`
- Create: `app/config_data/platforms/linkedin.yaml`
- Create: `alembic/versions/20260406_add_linkedin_tables.py`
- Create: `app/models/linkedin.py`
- Modify: `app/models/__init__.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_linkedin_models.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_linkedin_models.py
import uuid

from app.models.content import Intent, Pillar
from app.models.linkedin import (
    LinkedInApprovalTier,
    LinkedInContentType,
    LinkedInGenerationLog,
    LinkedInPost,
    LinkedInStatus,
)


def test_linkedin_post_defaults():
    item = LinkedInPost(
        id=uuid.uuid4(),
        content="Pressure data beats vibes.",
        content_type=LinkedInContentType.THOUGHT_LEADERSHIP,
        pillar=Pillar.THOUGHT_LEADERSHIP,
        intent=Intent.BRAND,
        hashtags=["#MentalPerformance"],
        approval_tier=LinkedInApprovalTier.TIER_1,
        status=LinkedInStatus.DRAFT,
        request_payload={"content_type": "thought_leadership", "pillar": "thought_leadership"},
        compliance_result={"passed": True},
    )
    assert item.content_type == LinkedInContentType.THOUGHT_LEADERSHIP
    assert item.approval_tier == LinkedInApprovalTier.TIER_1
    assert item.status == LinkedInStatus.DRAFT


def test_linkedin_status_values():
    assert LinkedInStatus.NEEDS_REVIEW.value == "needs_review"
    assert LinkedInStatus.APPROVED.value == "approved"
    assert LinkedInStatus.PUBLISHED.value == "published"


def test_linkedin_generation_log_fields():
    log = LinkedInGenerationLog(
        id=uuid.uuid4(),
        linkedin_post_id=None,
        prompt_snapshot="prompt",
        response={"raw_text": "post"},
        model="claude-sonnet-4-6",
        tokens_in=100,
        tokens_out=50,
        cost_estimate=0.001,
        duration_ms=500,
    )
    assert log.model == "claude-sonnet-4-6"
    assert log.linkedin_post_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_linkedin_models.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.linkedin'`

- [ ] **Step 3: Write the minimal implementation**

```env
# .env.example
DATABASE_URL=postgresql://user:pass@localhost:5432/ntangible_marketing
API_KEY=change-me-to-a-random-secret
ANTHROPIC_API_KEY=sk-ant-...
X_PUBLISHER=mock
LINKEDIN_PUBLISHER=mock
# For LinkedIn company page posting:
# LINKEDIN_ACCESS_TOKEN=
# LINKEDIN_ORGANIZATION_URN=urn:li:organization:123456
# LINKEDIN_API_VERSION=202504
```

```python
# app/config.py
class Settings(BaseSettings):
    database_url: str
    api_key: str
    anthropic_api_key: str
    x_publisher: str = "mock"
    linkedin_publisher: str = "mock"
    linkedin_access_token: str = ""
    linkedin_organization_urn: str = ""
    linkedin_api_version: str = "202504"
    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""
    x_twikit_username: str = ""
    x_twikit_password: str = ""
    x_twikit_email: str = ""
```

```yaml
# app/config_data/platforms/linkedin.yaml
linkedin:
  max_chars: 3000
  max_hashtags: 5
  auto_publish_default_tier: tier_1
  content_types:
    thought_leadership:
      target_min_chars: 1200
      target_max_chars: 1500
    data_insight:
      target_min_chars: 600
      target_max_chars: 800
    company_update:
      target_min_chars: 300
      target_max_chars: 900
```

```python
# app/models/linkedin.py
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.content import Intent, Pillar, _enum_values


class LinkedInContentType(str, enum.Enum):
    THOUGHT_LEADERSHIP = "thought_leadership"
    DATA_INSIGHT = "data_insight"
    COMPANY_UPDATE = "company_update"


class LinkedInApprovalTier(str, enum.Enum):
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"


class LinkedInStatus(str, enum.Enum):
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    PUBLISHING_UNKNOWN = "publishing_unknown"
    FAILED = "failed"
    REJECTED = "rejected"


class LinkedInPost(Base):
    __tablename__ = "linkedin_posts"

    content_type_enum = Enum(LinkedInContentType, name="linkedin_content_type_enum", values_callable=_enum_values)
    approval_tier_enum = Enum(LinkedInApprovalTier, name="linkedin_approval_tier_enum", values_callable=_enum_values)
    status_enum = Enum(LinkedInStatus, name="linkedin_status_enum", values_callable=_enum_values)
    pillar_enum = Enum(Pillar, name="pillar_enum", values_callable=_enum_values, create_type=False)
    intent_enum = Enum(Intent, name="intent_enum", values_callable=_enum_values, create_type=False)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[LinkedInContentType] = mapped_column(content_type_enum, nullable=False)
    pillar: Mapped[Pillar] = mapped_column(pillar_enum, nullable=False)
    intent: Mapped[Intent] = mapped_column(intent_enum, nullable=False)
    hashtags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    approval_tier: Mapped[LinkedInApprovalTier] = mapped_column(approval_tier_enum, nullable=False)
    status: Mapped[LinkedInStatus] = mapped_column(status_enum, nullable=False, default=LinkedInStatus.DRAFT)
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    compliance_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_post_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    post_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class LinkedInGenerationLog(Base):
    __tablename__ = "linkedin_generation_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    linkedin_post_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    prompt_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_estimate: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

```python
# alembic/versions/20260406_add_linkedin_tables.py
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260406_add_linkedin_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "linkedin_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Enum("thought_leadership", "data_insight", "company_update", name="linkedin_content_type_enum"), nullable=False),
        sa.Column("pillar", sa.Enum("blind_spot", "cost_of_guessing", "client_proof", "thought_leadership", "product", name="pillar_enum", create_type=False), nullable=False),
        sa.Column("intent", sa.Enum("brand", "partner", "revenue", name="intent_enum", create_type=False), nullable=False),
        sa.Column("hashtags", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("approval_tier", sa.Enum("tier_1", "tier_2", "tier_3", name="linkedin_approval_tier_enum"), nullable=False),
        sa.Column("status", sa.Enum("draft", "needs_review", "approved", "publishing", "published", "publishing_unknown", "failed", "rejected", name="linkedin_status_enum"), nullable=False),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("compliance_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("linkedin_post_id", sa.String(length=128), nullable=True),
        sa.Column("post_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table(
        "linkedin_generation_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("linkedin_post_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("prompt_snapshot", sa.Text(), nullable=False),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_estimate", sa.Numeric(10, 6), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("linkedin_generation_log")
    op.drop_table("linkedin_posts")
    sa.Enum(name="linkedin_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="linkedin_approval_tier_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="linkedin_content_type_enum").drop(op.get_bind(), checkfirst=True)
```

```python
# app/models/__init__.py
from app.models.linkedin import (
    LinkedInApprovalTier,
    LinkedInContentType,
    LinkedInGenerationLog,
    LinkedInPost,
    LinkedInStatus,
)

__all__ += [
    "LinkedInPost",
    "LinkedInGenerationLog",
    "LinkedInContentType",
    "LinkedInApprovalTier",
    "LinkedInStatus",
]
```

```python
# tests/conftest.py
os.environ.setdefault("LINKEDIN_PUBLISHER", "mock")
os.environ.setdefault("LINKEDIN_ACCESS_TOKEN", "test-linkedin-token")
os.environ.setdefault("LINKEDIN_ORGANIZATION_URN", "urn:li:organization:123456")
os.environ.setdefault("LINKEDIN_API_VERSION", "202504")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_linkedin_models.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .env.example app/config.py app/config_data/platforms/linkedin.yaml alembic/versions/20260406_add_linkedin_tables.py app/models/linkedin.py app/models/__init__.py tests/conftest.py tests/test_linkedin_models.py
git commit -m "feat: add LinkedIn config and persistence models"
```

### Task 2: Build The LinkedIn Writer And Compliance Gate

**Files:**
- Create: `app/agents/linkedin_writer.py`
- Create: `app/agents/linkedin_compliance.py`
- Test: `tests/test_linkedin_writer.py`
- Test: `tests/test_linkedin_compliance.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_linkedin_writer.py
import pytest

from app.agents.linkedin_writer import build_linkedin_prompt, parse_linkedin_response


def test_build_linkedin_prompt_uses_linkedin_voice():
    prompt = build_linkedin_prompt(
        content_type="thought_leadership",
        pillar="thought_leadership",
        claims=[],
        context="Transfer portal inefficiency",
    )
    assert "professional but not corporate" in prompt["system"].lower()
    assert "3-5 hashtags" in prompt["system"]


def test_parse_linkedin_response_requires_fields():
    with pytest.raises(ValueError):
        parse_linkedin_response({"content": "Only content"})
```

```python
# tests/test_linkedin_compliance.py
from app.agents.linkedin_compliance import run_linkedin_compliance_checks


def _draft(content: str, hashtags: list[str] | None = None, claim_keys_used: list[str] | None = None):
    return {
        "content": content,
        "hashtags": hashtags or [],
        "claim_keys_used": claim_keys_used or [],
    }


def test_linkedin_rejects_over_3000_chars():
    result = run_linkedin_compliance_checks(_draft("x" * 3001), requested_claims=[])
    assert not result.passed
    assert result.failed_check == "char_limit"


def test_linkedin_trims_hashtags_to_five():
    result = run_linkedin_compliance_checks(
        _draft("Pressure data wins.", hashtags=["#one", "#two", "#three", "#four", "#five", "#six"]),
        requested_claims=[],
    )
    assert result.passed
    assert len(result.corrected_hashtags) == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_linkedin_writer.py tests/test_linkedin_compliance.py -q`
Expected: FAIL with missing LinkedIn agent modules

- [ ] **Step 3: Write the minimal implementation**

```python
# app/agents/linkedin_writer.py
import json
import time
from typing import Any

import anthropic

from app.config import (
    get_approved_claims,
    get_brand_voice,
    get_content_pillars,
    get_platform_config,
    get_settings,
)


LINKEDIN_REQUIRED_FIELDS = {
    "content",
    "content_type",
    "pillar",
    "claim_keys_used",
    "hashtags",
    "media_needed",
    "intent",
}


def build_linkedin_prompt(
    content_type: str,
    pillar: str,
    claims: list[str],
    context: str | None,
) -> dict[str, str]:
    brand = get_brand_voice()
    pillars = get_content_pillars()
    claims_config = get_approved_claims()
    platform = get_platform_config("linkedin")["linkedin"]
    pillar_data = pillars["pillars"][pillar]

    claims_lines = []
    for key in claims:
        claim = claims_config["claims"].get(key)
        if claim:
            claims_lines.append(f"- {key}: {claim['text']} (Source: {claim['source']})")

    claims_block = "\n".join(claims_lines) if claims_lines else "No approved claims provided."
    system_prompt = f"""You are writing a LinkedIn company page post for NTangible.

Voice: Professional but not corporate. Founder-in-the-arena. Short paragraphs. Data-backed claims.
Brand voice: {brand['voice']['personality']}
Do: {chr(10).join('- ' + item for item in brand['voice']['do'])}
Don't: {chr(10).join('- ' + item for item in brand['voice']['dont'])}
Banned phrases: {chr(10).join('- ' + item for item in brand['banned_phrases'])}
Trademark rules: Always write Clutch Factor™ with the ™ symbol.
Platform constraints:
- Max {platform['max_chars']} characters
- 3-5 hashtags max
- No press-release tone
- CTA should stay soft
Approved claims:
{claims_block}

Return exactly one JSON object with:
content, content_type, pillar, claim_keys_used, hashtags, media_needed, intent
"""

    user_prompt = f"""Write one {content_type} LinkedIn post for the {pillar} pillar.
Pillar description: {pillar_data['description']}
Example angles: {', '.join(pillar_data['example_angles'])}
Context: {context or 'None'}
"""
    return {"system": system_prompt, "user": user_prompt}


def parse_linkedin_response(raw: dict[str, Any]) -> dict[str, Any]:
    missing = LINKEDIN_REQUIRED_FIELDS - set(raw)
    if missing:
        raise ValueError(f"Missing fields in LinkedIn response: {sorted(missing)}")
    return raw


def generate_linkedin_post(
    content_type: str,
    pillar: str,
    claims: list[str],
    context: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    settings = get_settings()
    prompt = build_linkedin_prompt(content_type, pillar, claims, context)
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    start = time.time()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1400,
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
    )
    duration_ms = int((time.time() - start) * 1000)
    parsed = parse_linkedin_response(json.loads(response.content[0].text))
    log_data = {
        "prompt_snapshot": prompt["system"] + "\n---\n" + prompt["user"],
        "response": {"raw_text": response.content[0].text},
        "model": "claude-sonnet-4-6",
        "tokens_in": response.usage.input_tokens,
        "tokens_out": response.usage.output_tokens,
        "cost_estimate": (response.usage.input_tokens * 0.003 + response.usage.output_tokens * 0.015) / 1000,
        "duration_ms": duration_ms,
    }
    return parsed, log_data
```

```python
# app/agents/linkedin_compliance.py
from app.agents.compliance import ComplianceResult, _protect_and_correct_trademarks
from app.agents.numeric_tokenizer import extract_claim_numerics
from app.config import get_approved_claims, get_brand_voice, get_platform_config


def run_linkedin_compliance_checks(draft: dict, requested_claims: list[str]) -> ComplianceResult:
    brand = get_brand_voice()
    claims_config = get_approved_claims()
    platform = get_platform_config("linkedin")["linkedin"]
    content = draft["content"]
    claim_keys_used = draft.get("claim_keys_used", [])
    hashtags = list(draft.get("hashtags", []))
    lowered = content.lower()
    checks_run: list[str] = []

    checks_run.append("banned_phrases")
    for phrase in brand["banned_phrases"]:
        if phrase.lower() in lowered:
            return ComplianceResult(False, "banned_phrases", f"Contains banned phrase: '{phrase}'", checks_run=checks_run)

    checks_run.append("trademarks")
    corrected = _protect_and_correct_trademarks(content, brand["trademarks"])

    checks_run.append("restricted_clients")
    for restricted_name in brand["restricted_clients"]["hard_block"]:
        if restricted_name.lower() in corrected.lower():
            return ComplianceResult(False, "restricted_clients", f"References restricted client: '{restricted_name}'", checks_run=checks_run)

    checks_run.append("claim_keys")
    for key in claim_keys_used:
        if key not in requested_claims:
            return ComplianceResult(False, "claim_keys", f"Claim key '{key}' was not requested", checks_run=checks_run)
        if key not in claims_config["claims"]:
            return ComplianceResult(False, "claim_keys", f"Claim key '{key}' is not approved", checks_run=checks_run)

    checks_run.append("claim_text")
    for key in claim_keys_used:
        for value_group in claims_config["claims"][key]["check_value_groups"]:
            if not any(variant in corrected for variant in value_group):
                return ComplianceResult(False, "claim_text", f"Claim '{key}' missing required value group {value_group}", checks_run=checks_run)

    checks_run.append("undeclared_numerics")
    covered_values = {
        variant
        for key in claim_keys_used
        for value_group in claims_config["claims"][key]["check_value_groups"]
        for variant in value_group
    }
    for token in extract_claim_numerics(corrected):
        normalized = token.lower()
        if not any(
            normalized == covered.lower()
            or normalized in covered.lower()
            or covered.lower() in normalized
            for covered in covered_values
        ):
            return ComplianceResult(False, "undeclared_numerics", f"Undeclared numeric '{token}' in text", checks_run=checks_run)

    checks_run.append("tone")
    if "!" in corrected:
        return ComplianceResult(False, "tone", "Contains exclamation point(s)", checks_run=checks_run)

    checks_run.append("char_limit")
    if len(corrected) > platform["max_chars"]:
        return ComplianceResult(False, "char_limit", f"LinkedIn post is {len(corrected)} chars (max {platform['max_chars']})", checks_run=checks_run)

    checks_run.append("hashtags")
    corrected_hashtags = hashtags[: platform["max_hashtags"]]
    return ComplianceResult(
        passed=True,
        corrected_content=corrected,
        corrected_hashtags=corrected_hashtags,
        checks_run=checks_run,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_linkedin_writer.py tests/test_linkedin_compliance.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/agents/linkedin_writer.py app/agents/linkedin_compliance.py tests/test_linkedin_writer.py tests/test_linkedin_compliance.py
git commit -m "feat: add LinkedIn generation and compliance pipeline"
```

### Task 3: Add LinkedIn Publisher Adapters

**Files:**
- Create: `app/publishers/linkedin_base.py`
- Create: `app/publishers/linkedin_mock.py`
- Create: `app/publishers/linkedin_http.py`
- Create: `app/publishers/linkedin_factory.py`
- Test: `tests/test_linkedin_publisher.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_linkedin_publisher.py
from app.publishers.linkedin_factory import get_linkedin_publisher
from app.publishers.linkedin_mock import MockLinkedInPublisher


def test_linkedin_factory_defaults_to_mock(monkeypatch):
    monkeypatch.setenv("LINKEDIN_PUBLISHER", "mock")
    publisher = get_linkedin_publisher()
    assert isinstance(publisher, MockLinkedInPublisher)


def test_mock_linkedin_publisher_tracks_posts():
    publisher = MockLinkedInPublisher()
    result = publisher.publish_post("Pressure data beats vibes.")
    assert result.success is True
    assert result.post_id is not None
    assert publisher.posted[0]["text"] == "Pressure data beats vibes."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_linkedin_publisher.py -q`
Expected: FAIL with missing LinkedIn publisher modules

- [ ] **Step 3: Write the minimal implementation**

```python
# app/publishers/linkedin_base.py
from dataclasses import dataclass


@dataclass
class LinkedInPublishResult:
    success: bool
    post_id: str | None = None
    post_url: str | None = None
    posted_at: str | None = None
    error: str | None = None


class BaseLinkedInPublisher:
    def publish_post(self, text: str) -> LinkedInPublishResult:
        raise NotImplementedError
```

```python
# app/publishers/linkedin_mock.py
import uuid
from datetime import datetime, timezone

from app.publishers.linkedin_base import BaseLinkedInPublisher, LinkedInPublishResult


class MockLinkedInPublisher(BaseLinkedInPublisher):
    def __init__(self):
        self.posted: list[dict] = []

    def publish_post(self, text: str) -> LinkedInPublishResult:
        post_id = f"urn:li:share:{uuid.uuid4().int % 10**12}"
        posted_at = datetime.now(timezone.utc).isoformat()
        self.posted.append({"text": text, "post_id": post_id})
        return LinkedInPublishResult(
            success=True,
            post_id=post_id,
            post_url=f"https://www.linkedin.com/feed/update/{post_id}",
            posted_at=posted_at,
        )
```

```python
# app/publishers/linkedin_http.py
from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.publishers.linkedin_base import BaseLinkedInPublisher, LinkedInPublishResult


class HttpLinkedInPublisher(BaseLinkedInPublisher):
    def __init__(self):
        self.settings = get_settings()
        self.client = httpx.Client(
            base_url="https://api.linkedin.com",
            headers={
                "Authorization": f"Bearer {self.settings.linkedin_access_token}",
                "Linkedin-Version": self.settings.linkedin_api_version,
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            },
            timeout=20.0,
        )

    def publish_post(self, text: str) -> LinkedInPublishResult:
        payload = {
            "author": self.settings.linkedin_organization_urn,
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        response = self.client.post("/rest/posts", json=payload)
        if response.is_success:
            post_id = response.headers.get("x-restli-id", "")
            return LinkedInPublishResult(
                success=True,
                post_id=post_id,
                post_url=f"https://www.linkedin.com/feed/update/{post_id}",
                posted_at=datetime.now(timezone.utc).isoformat(),
            )
        return LinkedInPublishResult(success=False, error=f"{response.status_code}: {response.text}")
```

```python
# app/publishers/linkedin_factory.py
from app.config import get_settings
from app.publishers.linkedin_base import BaseLinkedInPublisher
from app.publishers.linkedin_http import HttpLinkedInPublisher
from app.publishers.linkedin_mock import MockLinkedInPublisher


def get_linkedin_publisher() -> BaseLinkedInPublisher:
    publisher_type = get_settings().linkedin_publisher.lower()
    if publisher_type == "mock":
        return MockLinkedInPublisher()
    if publisher_type == "http":
        return HttpLinkedInPublisher()
    raise ValueError(f"Unknown LinkedIn publisher: {publisher_type}. Use mock or http.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_linkedin_publisher.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/publishers/linkedin_base.py app/publishers/linkedin_mock.py app/publishers/linkedin_http.py app/publishers/linkedin_factory.py tests/test_linkedin_publisher.py
git commit -m "feat: add LinkedIn publisher adapters"
```

### Task 4: Build The LinkedIn Pipeline Service

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/linkedin_pipeline.py`
- Test: `tests/test_linkedin_pipeline.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_linkedin_pipeline.py
from app.models.linkedin import LinkedInApprovalTier, LinkedInStatus
from app.services.linkedin_pipeline import determine_initial_status


def test_tier_1_defaults_to_draft_for_immediate_publish_path():
    assert determine_initial_status(LinkedInApprovalTier.TIER_1) == LinkedInStatus.DRAFT


def test_tier_2_goes_to_review():
    assert determine_initial_status(LinkedInApprovalTier.TIER_2) == LinkedInStatus.NEEDS_REVIEW
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_linkedin_pipeline.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.linkedin_pipeline'`

- [ ] **Step 3: Write the minimal implementation**

```python
# app/services/__init__.py
```

```python
# app/services/linkedin_pipeline.py
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.linkedin_compliance import run_linkedin_compliance_checks
from app.agents.linkedin_writer import generate_linkedin_post
from app.models.content import Intent, Pillar
from app.models.linkedin import (
    LinkedInApprovalTier,
    LinkedInContentType,
    LinkedInGenerationLog,
    LinkedInPost,
    LinkedInStatus,
)
from app.publishers.linkedin_factory import get_linkedin_publisher


CONTENT_TYPE_MAP = {
    "thought_leadership": LinkedInContentType.THOUGHT_LEADERSHIP,
    "data_insight": LinkedInContentType.DATA_INSIGHT,
    "company_update": LinkedInContentType.COMPANY_UPDATE,
}

PILLAR_MAP = {
    "blind_spot": Pillar.BLIND_SPOT,
    "cost_of_guessing": Pillar.COST_OF_GUESSING,
    "client_proof": Pillar.CLIENT_PROOF,
    "thought_leadership": Pillar.THOUGHT_LEADERSHIP,
    "product": Pillar.PRODUCT,
}

INTENT_MAP = {
    "brand": Intent.BRAND,
    "partner": Intent.PARTNER,
    "revenue": Intent.REVENUE,
}

APPROVAL_TIER_MAP = {
    "tier_1": LinkedInApprovalTier.TIER_1,
    "tier_2": LinkedInApprovalTier.TIER_2,
    "tier_3": LinkedInApprovalTier.TIER_3,
}


def determine_initial_status(approval_tier: LinkedInApprovalTier) -> LinkedInStatus:
    if approval_tier == LinkedInApprovalTier.TIER_1:
        return LinkedInStatus.DRAFT
    return LinkedInStatus.NEEDS_REVIEW


def generate_linkedin_item(request_data: dict, db: Session) -> LinkedInPost:
    approval_tier = APPROVAL_TIER_MAP[request_data["approval_tier"]]
    generated, log_data = generate_linkedin_post(
        content_type=request_data["content_type"],
        pillar=request_data["pillar"],
        claims=request_data.get("claims", []),
        context=request_data.get("context"),
    )
    compliance = run_linkedin_compliance_checks(generated, requested_claims=request_data.get("claims", []))
    if not compliance.passed:
        raise ValueError(compliance.failure_reason)

    post = LinkedInPost(
        id=uuid.uuid4(),
        content=compliance.corrected_content or generated["content"],
        content_type=CONTENT_TYPE_MAP[request_data["content_type"]],
        pillar=PILLAR_MAP[request_data["pillar"]],
        intent=INTENT_MAP.get(generated.get("intent", "brand"), Intent.BRAND),
        hashtags=compliance.corrected_hashtags,
        approval_tier=approval_tier,
        status=determine_initial_status(approval_tier),
        request_payload=request_data,
        compliance_result={"passed": True, "checks_run": compliance.checks_run},
    )
    db.add(post)
    db.add(
        LinkedInGenerationLog(
            id=uuid.uuid4(),
            linkedin_post_id=post.id,
            prompt_snapshot=log_data["prompt_snapshot"],
            response=log_data["response"],
            model=log_data["model"],
            tokens_in=log_data["tokens_in"],
            tokens_out=log_data["tokens_out"],
            cost_estimate=log_data["cost_estimate"],
            duration_ms=log_data["duration_ms"],
        )
    )
    db.commit()
    db.refresh(post)

    if approval_tier == LinkedInApprovalTier.TIER_1:
        return publish_linkedin_item(post.id, db)
    return post


def approve_linkedin_item(post: LinkedInPost, db: Session) -> LinkedInPost:
    post.status = LinkedInStatus.APPROVED
    db.commit()
    db.refresh(post)
    return post


def reject_linkedin_item(post: LinkedInPost, notes: str | None, db: Session) -> LinkedInPost:
    post.status = LinkedInStatus.REJECTED
    post.review_notes = notes
    db.commit()
    db.refresh(post)
    return post


def publish_linkedin_item(post_id, db: Session) -> LinkedInPost:
    post = db.query(LinkedInPost).filter(LinkedInPost.id == post_id).first()
    if post is None:
        raise ValueError("LinkedIn post not found")
    if post.status not in {LinkedInStatus.DRAFT, LinkedInStatus.APPROVED}:
        raise ValueError(f"Cannot publish post in status '{post.status.value}'")

    post.status = LinkedInStatus.PUBLISHING
    db.commit()
    db.refresh(post)

    result = get_linkedin_publisher().publish_post(post.content)
    if result.success:
        post.status = LinkedInStatus.PUBLISHED
        post.linkedin_post_id = result.post_id
        post.post_url = result.post_url
        post.published_at = datetime.now(timezone.utc)
    elif result.error and "timeout" in result.error.lower():
        post.status = LinkedInStatus.PUBLISHING_UNKNOWN
        post.failure_reason = result.error
    else:
        post.status = LinkedInStatus.FAILED
        post.failure_reason = result.error

    db.commit()
    db.refresh(post)
    return post
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_linkedin_pipeline.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/linkedin_pipeline.py tests/test_linkedin_pipeline.py
git commit -m "feat: add LinkedIn pipeline service"
```

### Task 5: Expose The LinkedIn API And Wire It Into FastAPI

**Files:**
- Create: `app/api/linkedin_schemas.py`
- Create: `app/api/linkedin_routes.py`
- Modify: `app/main.py`
- Test: `tests/test_linkedin_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_linkedin_api.py
import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.api.linkedin_routes as linkedin_routes
from app.database import get_db
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_linkedin_generate_requires_auth():
    response = client.post("/linkedin/generate", json={})
    assert response.status_code == 403


def test_linkedin_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/linkedin/generate" in paths
    assert "/linkedin/review" in paths


def test_linkedin_generate_returns_pipeline_result(monkeypatch):
    fake_post = SimpleNamespace(
        id=uuid.uuid4(),
        status=SimpleNamespace(value="needs_review"),
        approval_tier=SimpleNamespace(value="tier_2"),
        content="Pressure data beats vibes.",
        hashtags=["#MentalPerformance"],
        post_url=None,
    )

    def fake_get_db():
        yield object()

    def fake_generate(payload, db):
        assert payload["approval_tier"] == "tier_2"
        return fake_post

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(linkedin_routes, "generate_linkedin_item", fake_generate)
    response = client.post(
        "/linkedin/generate",
        headers={"Authorization": "Bearer test-secret-key"},
        json={
            "content_type": "thought_leadership",
            "pillar": "thought_leadership",
            "approval_tier": "tier_2",
            "claims": [],
            "context": "Pressure data beats vibes.",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "needs_review"
    assert payload["approval_tier"] == "tier_2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_linkedin_api.py -q`
Expected: FAIL because the LinkedIn routes are not registered

- [ ] **Step 3: Write the minimal implementation**

```python
# app/api/linkedin_schemas.py
from pydantic import BaseModel, Field


class LinkedInGenerateRequest(BaseModel):
    content_type: str
    pillar: str
    approval_tier: str = "tier_1"
    claims: list[str] = Field(default_factory=list)
    context: str | None = None


class LinkedInReviewRequest(BaseModel):
    notes: str | None = None
```

```python
# app/api/linkedin_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.linkedin_schemas import LinkedInGenerateRequest, LinkedInReviewRequest
from app.database import get_db
from app.main import verify_api_key
from app.models.linkedin import LinkedInPost, LinkedInStatus
from app.services.linkedin_pipeline import (
    approve_linkedin_item,
    generate_linkedin_item,
    publish_linkedin_item,
    reject_linkedin_item,
)


router = APIRouter(prefix="/linkedin", tags=["linkedin"])


@router.post("/generate", dependencies=[Depends(verify_api_key)])
def generate_linkedin(req: LinkedInGenerateRequest, db: Session = Depends(get_db)):
    post = generate_linkedin_item(req.model_dump(), db)
    return {
        "id": str(post.id),
        "status": post.status.value,
        "approval_tier": post.approval_tier.value,
        "content": post.content,
        "hashtags": post.hashtags,
        "post_url": post.post_url,
    }


@router.get("/review", dependencies=[Depends(verify_api_key)])
def list_review_queue(db: Session = Depends(get_db)):
    posts = (
        db.query(LinkedInPost)
        .filter(LinkedInPost.status.in_([LinkedInStatus.NEEDS_REVIEW, LinkedInStatus.APPROVED]))
        .order_by(LinkedInPost.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(post.id),
            "status": post.status.value,
            "approval_tier": post.approval_tier.value,
            "content": post.content,
        }
        for post in posts
    ]


@router.get("/published", dependencies=[Depends(verify_api_key)])
def list_linkedin_published(db: Session = Depends(get_db)):
    posts = db.query(LinkedInPost).filter(LinkedInPost.status == LinkedInStatus.PUBLISHED).all()
    return [
        {
            "id": str(post.id),
            "content": post.content,
            "post_url": post.post_url,
            "linkedin_post_id": post.linkedin_post_id,
        }
        for post in posts
    ]


@router.get("/{post_id}", dependencies=[Depends(verify_api_key)])
def get_linkedin_post(post_id: str, db: Session = Depends(get_db)):
    post = db.query(LinkedInPost).filter(LinkedInPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="LinkedIn post not found")
    return {
        "id": str(post.id),
        "status": post.status.value,
        "approval_tier": post.approval_tier.value,
        "content": post.content,
        "post_url": post.post_url,
        "failure_reason": post.failure_reason,
    }


@router.post("/{post_id}/approve", dependencies=[Depends(verify_api_key)])
def approve_linkedin(post_id: str, db: Session = Depends(get_db)):
    post = db.query(LinkedInPost).filter(LinkedInPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="LinkedIn post not found")
    if post.status != LinkedInStatus.NEEDS_REVIEW:
        raise HTTPException(status_code=409, detail=f"Cannot approve from '{post.status.value}'")
    post = approve_linkedin_item(post, db)
    return {"id": str(post.id), "status": post.status.value}


@router.post("/{post_id}/reject", dependencies=[Depends(verify_api_key)])
def reject_linkedin(post_id: str, req: LinkedInReviewRequest, db: Session = Depends(get_db)):
    post = db.query(LinkedInPost).filter(LinkedInPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="LinkedIn post not found")
    if post.status not in {LinkedInStatus.NEEDS_REVIEW, LinkedInStatus.APPROVED}:
        raise HTTPException(status_code=409, detail=f"Cannot reject from '{post.status.value}'")
    post = reject_linkedin_item(post, req.notes, db)
    return {"id": str(post.id), "status": post.status.value}


@router.post("/{post_id}/publish", dependencies=[Depends(verify_api_key)])
def publish_linkedin(post_id: str, db: Session = Depends(get_db)):
    try:
        post = publish_linkedin_item(post_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "id": str(post.id),
        "status": post.status.value,
        "post_url": post.post_url,
        "linkedin_post_id": post.linkedin_post_id,
    }
```

```python
# app/main.py
from app.api.linkedin_routes import router as linkedin_router

app = FastAPI(title="NTangible Marketing Engine", version="0.1.0")
app.include_router(linkedin_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_linkedin_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/linkedin_schemas.py app/api/linkedin_routes.py app/main.py tests/test_linkedin_api.py
git commit -m "feat: add LinkedIn pipeline API routes"
```

### Task 6: Verify The Phase 3 Slice End To End

**Files:**
- Test: `tests/test_linkedin_models.py`
- Test: `tests/test_linkedin_writer.py`
- Test: `tests/test_linkedin_compliance.py`
- Test: `tests/test_linkedin_publisher.py`
- Test: `tests/test_linkedin_pipeline.py`
- Test: `tests/test_linkedin_api.py`

- [ ] **Step 1: Run the focused LinkedIn test suite**

Run: `pytest tests/test_linkedin_models.py tests/test_linkedin_writer.py tests/test_linkedin_compliance.py tests/test_linkedin_publisher.py tests/test_linkedin_pipeline.py tests/test_linkedin_api.py -q`
Expected: PASS

- [ ] **Step 2: Run the full test suite**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 3: Verify FastAPI route registration**

Run: `python -c "from app.main import app; print(sorted(route.path for route in app.routes if route.path.startswith('/linkedin')))" `
Expected:

```python
['/linkedin/{post_id}', '/linkedin/{post_id}/approve', '/linkedin/{post_id}/publish', '/linkedin/{post_id}/reject', '/linkedin/generate', '/linkedin/published', '/linkedin/review']
```

- [ ] **Step 4: Manual smoke test with mock publisher**

Run:

```bash
uvicorn app.main:app --reload
```

Then:

```bash
curl -X POST http://127.0.0.1:8000/linkedin/generate \
  -H "Authorization: Bearer change-me-to-a-random-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "content_type": "thought_leadership",
    "pillar": "thought_leadership",
    "approval_tier": "tier_2",
    "claims": [],
    "context": "Why coaches miss pressure performance when they only use film and physical testing"
  }'
```

Expected: `200 OK` with a LinkedIn post in `needs_review` status.

- [ ] **Step 5: Commit**

```bash
git add tests/test_linkedin_models.py tests/test_linkedin_writer.py tests/test_linkedin_compliance.py tests/test_linkedin_publisher.py tests/test_linkedin_pipeline.py tests/test_linkedin_api.py
git commit -m "test: verify LinkedIn phase 3 pipeline"
```
