# Phase 1: Content Writer + X Auto-Posting — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python API that generates on-brand tweets via Claude, validates them through a deterministic compliance gate with factual claim verification, and publishes to X on manual approval.

**Architecture:** Modular monolith — FastAPI app with separate modules for content generation, compliance checking, publishing, and config. All state in Postgres. No background jobs; all actions are user-triggered via authenticated API calls.

**Tech Stack:** Python 3.12+, FastAPI, Anthropic SDK, SQLAlchemy + Alembic, Tweepy, Twikit (dev), PostgreSQL, PyYAML, pytest

---

### Task 1: Project Scaffolding & Dependencies

**Files:**
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `app/config.py`
- Create: `app/database.py`
- Create: `tests/__init__.py`
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Initialize git repo**

```bash
cd /Users/elliot18/Desktop/Home/Projects/ntangible_marketing
git init
```

- [ ] **Step 2: Create pyproject.toml**

```toml
[project]
name = "ntangible-marketing"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "anthropic>=0.40.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.13.0",
    "tweepy>=4.14.0",
    "twikit>=2.0.0",
    "pyyaml>=6.0",
    "psycopg2-binary>=2.9.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"
```

- [ ] **Step 3: Create .env.example**

```
DATABASE_URL=postgresql://user:pass@localhost:5432/ntangible_marketing
API_KEY=change-me-to-a-random-secret
ANTHROPIC_API_KEY=sk-ant-...
X_PUBLISHER=mock
# For tweepy (production):
# X_API_KEY=
# X_API_SECRET=
# X_ACCESS_TOKEN=
# X_ACCESS_TOKEN_SECRET=
# For twikit (dev only):
# X_TWIKIT_USERNAME=
# X_TWIKIT_PASSWORD=
# X_TWIKIT_EMAIL=
```

- [ ] **Step 4: Create .gitignore**

```
__pycache__/
*.pyc
.env
*.egg-info/
dist/
.venv/
```

- [ ] **Step 5: Create app/config.py**

```python
from pathlib import Path
from functools import lru_cache

import yaml
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    api_key: str
    anthropic_api_key: str
    x_publisher: str = "mock"
    # Tweepy (production)
    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""
    # Twikit (dev)
    x_twikit_username: str = ""
    x_twikit_password: str = ""
    x_twikit_email: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


CONFIG_DIR = Path(__file__).parent / "config_data"


def load_yaml(filename: str) -> dict:
    with open(CONFIG_DIR / filename) as f:
        return yaml.safe_load(f)


@lru_cache
def get_brand_voice() -> dict:
    return load_yaml("brand_voice.yaml")


@lru_cache
def get_content_pillars() -> dict:
    return load_yaml("content_pillars.yaml")


@lru_cache
def get_approved_claims() -> dict:
    return load_yaml("approved_claims.yaml")


@lru_cache
def get_platform_config(platform: str = "x") -> dict:
    return load_yaml(f"platforms/{platform}.yaml")
```

- [ ] **Step 6: Create app/database.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import get_settings


engine = create_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 7: Create app/main.py**

```python
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import get_settings

app = FastAPI(title="NTangible Marketing Engine", version="0.1.0")
security = HTTPBearer()


def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    if credentials.credentials != get_settings().api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials
```

- [ ] **Step 8: Create app/__init__.py and tests/__init__.py**

Both files are empty.

- [ ] **Step 9: Install dependencies and verify**

```bash
cd /Users/elliot18/Desktop/Home/Projects/ntangible_marketing
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -c "from app.main import app; print(app.title)"
```

Expected: `NTangible Marketing Engine`

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml .env.example .gitignore app/__init__.py app/main.py app/config.py app/database.py tests/__init__.py
git commit -m "scaffold: project structure, config, database, FastAPI app with auth"
```

---

### Task 2: YAML Config Files

**Files:**
- Create: `app/config_data/brand_voice.yaml`
- Create: `app/config_data/content_pillars.yaml`
- Create: `app/config_data/approved_claims.yaml`
- Create: `app/config_data/platforms/x.yaml`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the config loading test**

```python
# tests/test_config.py
from app.config import load_yaml, CONFIG_DIR


def test_brand_voice_loads():
    data = load_yaml("brand_voice.yaml")
    assert "voice" in data
    assert "banned_phrases" in data
    assert "trademarks" in data
    assert "restricted_clients" in data
    assert "verified_clients" in data
    assert len(data["banned_phrases"]) > 0


def test_content_pillars_loads():
    data = load_yaml("content_pillars.yaml")
    assert "pillars" in data
    expected_pillars = {"blind_spot", "cost_of_guessing", "client_proof", "thought_leadership", "product"}
    assert set(data["pillars"].keys()) == expected_pillars
    for name, pillar in data["pillars"].items():
        assert "description" in pillar
        assert "example_angles" in pillar


def test_approved_claims_loads():
    data = load_yaml("approved_claims.yaml")
    assert "claims" in data
    for key, claim in data["claims"].items():
        assert "text" in claim
        assert "check_value_groups" in claim
        assert "source" in claim
        assert "verified_date" in claim
        for group in claim["check_value_groups"]:
            assert isinstance(group, list)
            assert len(group) > 0


def test_platform_x_loads():
    data = load_yaml("platforms/x.yaml")
    assert "x" in data
    assert data["x"]["single_tweet_max_chars"] == 280
    assert data["x"]["max_hashtags"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v
```

Expected: FAIL — yaml files don't exist yet.

- [ ] **Step 3: Create app/config_data/brand_voice.yaml**

```yaml
voice:
  personality: "Punchy. Contrarian. Sports bar meets data lab."
  do:
    - "Sound like a smart person who works in sports, not a brand account"
    - "Use short, direct sentences"
    - "Lead with data-backed claims"
    - "Be opinionated — take a position"
  dont:
    - "No passive voice"
    - "No exclamation points (except rare genuine excitement)"
    - "No fluffy motivational language"
    - "No corporate buzzwords"
    - "Never sound like a press release"

banned_phrases:
  - "unlock insights"
  - "leverage data"
  - "empower your team"
  - "game-changing"
  - "cutting-edge"

trademarks:
  "Clutch Factor™": ["Clutch Factor", "clutch factor", "ClutchFactor"]
  "NTangible Score": ["ntangible score", "Ntangible score"]
  "The Pressure Test": ["the pressure test", "pressure test"]

restricted_clients:
  hard_block: ["Florida A&M", "FAMU", "Swarthmore", "Sporting KC"]
  generic_only: ["MLS"]

verified_clients:
  - "Michigan State"
  - "Hofstra"
  - "Boston College"
  - "Alliance Fastpitch"
  - "Future Stars Series"
  - "RFK Racing"
  - "High Level Throwing"

score_publishing:
  min_threshold: 750
  allow_aggregate_full_range: true
```

- [ ] **Step 4: Create app/config_data/content_pillars.yaml**

```yaml
pillars:
  blind_spot:
    description: "You're evaluating half the picture"
    example_angles:
      - "You measure arm strength, speed, GPA. What about pressure?"
      - "Film tells you what happened. Not what happens when it counts."

  cost_of_guessing:
    description: "The financial cost of not measuring mental performance"
    note: "All dollar amounts and percentages must come from approved_claims.yaml"
    example_angles:
      - "You're guessing on half the recruiting decision"
      - "What does it cost when the transfer doesn't work out?"

  client_proof:
    description: "Real programs using NTangible, real results"
    note: "Only reference verified_clients. Specific outcomes must be in approved_claims.yaml"
    example_angles:
      - "D1 programs are measuring what matters"
      - "The data speaks for itself"

  thought_leadership:
    description: "NTangible's position in the mental performance conversation"
    example_angles:
      - "Personality profiles don't predict performance under pressure"
      - "Coach Alignment Index — the feature nobody else has"

  product:
    description: "What NTangible does and how it works"
    note: "Specific numbers must come from approved_claims.yaml"
    example_angles:
      - "Not a survey. A validated cognitive assessment."
      - "We measure what happens when it counts."
```

- [ ] **Step 5: Create app/config_data/approved_claims.yaml**

```yaml
claims:
  cf_all_american:
    text: "73% of athletes scoring above 800 CF were named All-American"
    check_value_groups:
      - ["73%"]
      - ["800"]
    source: "NTangible internal dataset"
    verified_date: "2026-03-01"

  failed_transfer_cost:
    text: "The average failed D1 transfer costs $150K"
    check_value_groups:
      - ["$150K", "$150,000", "150K"]
    source: "Industry research"
    verified_date: "2026-01-15"

  draft_bust_cost:
    text: "Average 1st round draft bust: -$3.5M"
    check_value_groups:
      - ["$3.5M", "$3.5 million", "3.5M"]
    source: "Industry research"
    verified_date: "2026-01-15"

  youth_churn_cost:
    text: "Youth churn: -$50K lifetime value"
    check_value_groups:
      - ["$50K", "$50,000", "50K"]
    source: "NTangible internal estimate"
    verified_date: "2026-02-01"

  assessment_count:
    text: "6,000+ assessments. 1M+ data points. 7 sports."
    check_value_groups:
      - ["6,000", "6000"]
      - ["1M", "1,000,000"]
      - ["7 sports"]
    source: "NTangible platform metrics"
    verified_date: "2026-03-15"

  alliance_athlete_count:
    text: "30,000+ athletes assessed through Alliance Fastpitch"
    check_value_groups:
      - ["30,000", "30000", "30K"]
    source: "Alliance Fastpitch partnership"
    verified_date: "2026-03-01"
```

- [ ] **Step 6: Create app/config_data/platforms/x.yaml**

```yaml
x:
  single_tweet_max_chars: 280
  max_hashtags: 2
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add app/config_data/ tests/test_config.py
git commit -m "feat: add YAML config files for brand voice, pillars, claims, platform rules"
```

---

### Task 3: Database Models & Migrations

**Files:**
- Create: `app/models/__init__.py`
- Create: `app/models/content.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the model test**

```python
# tests/test_models.py
import uuid
from datetime import datetime, timezone

from app.models.content import ContentQueue, GenerationLog, ContentType, Pillar, Intent, Status


def test_content_queue_fields():
    item = ContentQueue(
        id=uuid.uuid4(),
        content="Test tweet",
        content_type=ContentType.HOT_TAKE,
        pillar=Pillar.BLIND_SPOT,
        intent=Intent.BRAND,
        hashtags=["#test"],
        status=Status.DRAFT,
        variant_group=uuid.uuid4(),
        request_payload={"content_type": "hot_take", "pillar": "blind_spot"},
        compliance_result={"passed": True},
    )
    assert item.content == "Test tweet"
    assert item.status == Status.DRAFT
    assert item.content_type == ContentType.HOT_TAKE


def test_content_type_enum():
    assert ContentType.HOT_TAKE.value == "hot_take"
    assert ContentType.DATA_DROP.value == "data_drop"
    assert ContentType.TREND_JACK.value == "trend_jack"


def test_status_enum():
    assert Status.DRAFT.value == "draft"
    assert Status.PUBLISHING.value == "publishing"
    assert Status.PUBLISHED.value == "published"
    assert Status.PUBLISHING_UNKNOWN.value == "publishing_unknown"
    assert Status.FAILED.value == "failed"
    assert Status.REJECTED.value == "rejected"


def test_generation_log_fields():
    log = GenerationLog(
        id=uuid.uuid4(),
        content_queue_id=None,
        prompt_snapshot="test prompt",
        response={"content": "test"},
        model="claude-sonnet-4-6",
        tokens_in=100,
        tokens_out=50,
        cost_estimate=0.001,
        duration_ms=500,
    )
    assert log.model == "claude-sonnet-4-6"
    assert log.content_queue_id is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create app/models/__init__.py**

```python
from app.models.content import ContentQueue, GenerationLog, ContentType, Pillar, Intent, Status

__all__ = ["ContentQueue", "GenerationLog", "ContentType", "Pillar", "Intent", "Status"]
```

- [ ] **Step 4: Create app/models/content.py**

```python
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Enum, DateTime, Integer, Numeric, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ContentType(str, enum.Enum):
    HOT_TAKE = "hot_take"
    DATA_DROP = "data_drop"
    TREND_JACK = "trend_jack"


class Pillar(str, enum.Enum):
    BLIND_SPOT = "blind_spot"
    COST_OF_GUESSING = "cost_of_guessing"
    CLIENT_PROOF = "client_proof"
    THOUGHT_LEADERSHIP = "thought_leadership"
    PRODUCT = "product"


class Intent(str, enum.Enum):
    BRAND = "brand"
    PARTNER = "partner"
    REVENUE = "revenue"


class Status(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    PUBLISHING_UNKNOWN = "publishing_unknown"
    FAILED = "failed"
    REJECTED = "rejected"


class ContentQueue(Base):
    __tablename__ = "content_queue"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType, name="content_type_enum"), nullable=False)
    pillar: Mapped[Pillar] = mapped_column(Enum(Pillar, name="pillar_enum"), nullable=False)
    intent: Mapped[Intent] = mapped_column(Enum(Intent, name="intent_enum"), nullable=False)
    hashtags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    status: Mapped[Status] = mapped_column(Enum(Status, name="status_enum"), nullable=False, default=Status.DRAFT)
    variant_group: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    post_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    tweet_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compliance_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    regeneration_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GenerationLog(Base):
    __tablename__ = "generation_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_queue_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    prompt_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_estimate: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 6: Initialize Alembic**

```bash
cd /Users/elliot18/Desktop/Home/Projects/ntangible_marketing
alembic init alembic
```

- [ ] **Step 7: Edit alembic/env.py**

Replace the contents of `alembic/env.py` with:

```python
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from app.database import Base
from app.models.content import ContentQueue, GenerationLog
from app.config import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 8: Create initial migration**

```bash
alembic revision --autogenerate -m "initial: content_queue and generation_log tables"
```

- [ ] **Step 9: Commit**

```bash
git add app/models/ alembic/ alembic.ini tests/test_models.py
git commit -m "feat: database models for content_queue and generation_log"
```

---

### Task 4: Numeric Token Classifier

**Files:**
- Create: `app/agents/numeric_tokenizer.py`
- Create: `tests/test_numeric_tokenizer.py`

This is the tokenizer used by the compliance gate to classify numeric tokens in tweet text.

- [ ] **Step 1: Write the tokenizer tests**

```python
# tests/test_numeric_tokenizer.py
from app.agents.numeric_tokenizer import extract_claim_numerics


def test_dollar_amounts():
    tokens = extract_claim_numerics("Costs $150K to fail")
    assert "$150K" in tokens


def test_dollar_with_decimal():
    tokens = extract_claim_numerics("Draft bust: $3.5M wasted")
    assert "$3.5M" in tokens


def test_percentage():
    tokens = extract_claim_numerics("73% of athletes above 800 CF")
    assert "73%" in tokens
    assert "800" in tokens


def test_large_number_with_commas():
    tokens = extract_claim_numerics("Over 30,000 athletes tested")
    assert "30,000" in tokens


def test_number_with_plus():
    tokens = extract_claim_numerics("6,000+ assessments completed")
    assert "6,000+" in tokens


def test_bare_suffix():
    tokens = extract_claim_numerics("Reached 1M data points")
    assert "1M" in tokens


def test_ignores_ordinals():
    tokens = extract_claim_numerics("1st round pick failed again")
    assert len(tokens) == 0


def test_ignores_d1_d2_labels():
    tokens = extract_claim_numerics("D1 coaches are watching D2 players")
    assert len(tokens) == 0


def test_ignores_hashtag_numbers():
    tokens = extract_claim_numerics("We are #1 in pressure testing")
    assert len(tokens) == 0


def test_ignores_bare_single_digits():
    tokens = extract_claim_numerics("This is a great day")
    assert len(tokens) == 0


def test_mixed_content():
    text = "The 1st round bust costs $3.5M. D1 coaches see 73% success with 800+ CF scores."
    tokens = extract_claim_numerics(text)
    assert "$3.5M" in tokens
    assert "73%" in tokens
    assert "800+" in tokens
    assert "1st" not in tokens
    assert "D1" not in tokens


def test_seven_sports():
    tokens = extract_claim_numerics("Validated across 7 sports")
    assert "7 sports" in tokens


def test_bare_small_number_without_unit_ignored():
    tokens = extract_claim_numerics("We saw 3 things happen")
    assert len(tokens) == 0


def test_number_k_without_dollar():
    tokens = extract_claim_numerics("150K lifetime value lost")
    assert "150K" in tokens


def test_empty_string():
    tokens = extract_claim_numerics("")
    assert tokens == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_numeric_tokenizer.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create app/agents/__init__.py**

Empty file.

- [ ] **Step 4: Create app/agents/numeric_tokenizer.py**

```python
import re


# Patterns that are NOT claim numerics (checked first)
_ORDINAL_RE = re.compile(r"\b\d+(st|nd|rd|th)\b", re.IGNORECASE)
_LABEL_RE = re.compile(r"\b[A-Z]\d+\b")  # D1, D2, D3, G5, P5 etc.
_HASHTAG_NUM_RE = re.compile(r"#\d+")
_TIME_DATE_RE = re.compile(
    r"\b\d{1,2}:\d{2}\b|\b\d{1,2}/\d{1,2}(/\d{2,4})?\b|\b\d{4}-\d{2}-\d{2}\b"
)

# Patterns that ARE claim numerics (checked after exclusions are removed)
_CLAIM_PATTERNS = [
    # $X with optional decimal and suffix: $150K, $3.5M, $150,000
    re.compile(r"\$[\d,]+(?:\.\d+)?[KMBkmb]?"),
    # Percentage: 73%
    re.compile(r"\d[\d,]*(?:\.\d+)?%"),
    # Number with K/M/B suffix (no $): 150K, 1M, 30K
    re.compile(r"\b\d[\d,]*(?:\.\d+)?[KMBkmb]\b"),
    # Large number with commas and optional +: 30,000+, 6,000+, 150,000
    re.compile(r"\b\d{1,3}(?:,\d{3})+\+?\b"),
    # Number followed by " sports" (special case for "7 sports")
    re.compile(r"\b\d+ sports\b"),
    # Number with + suffix (800+, 6000+)
    re.compile(r"\b\d{3,}\+"),
    # Bare 3+ digit numbers not already matched (800, 6000)
    re.compile(r"\b\d{3,}\b"),
]


def extract_claim_numerics(text: str) -> list[str]:
    """Extract all claim-like numeric tokens from tweet text.

    Returns tokens that represent quantities, costs, or statistical figures.
    Ignores ordinals (1st, 2nd), labels (D1, D2), hashtag numbers (#1),
    dates/times, and bare single/double digit numbers without units.
    """
    if not text:
        return []

    # Build a set of character ranges to exclude (ordinals, labels, etc.)
    exclude_spans: list[tuple[int, int]] = []
    for pattern in [_ORDINAL_RE, _LABEL_RE, _HASHTAG_NUM_RE, _TIME_DATE_RE]:
        for match in pattern.finditer(text):
            exclude_spans.append((match.start(), match.end()))

    def is_excluded(start: int, end: int) -> bool:
        for ex_start, ex_end in exclude_spans:
            if start >= ex_start and end <= ex_end:
                return True
        return False

    # Find all claim numeric tokens
    found: list[str] = []
    seen_spans: set[tuple[int, int]] = set()

    for pattern in _CLAIM_PATTERNS:
        for match in pattern.finditer(text):
            span = (match.start(), match.end())
            if span in seen_spans:
                continue
            if is_excluded(match.start(), match.end()):
                continue
            # Check if this span overlaps with an already-found longer match
            overlaps = False
            for s_start, s_end in seen_spans:
                if match.start() >= s_start and match.end() <= s_end:
                    overlaps = True
                    break
            if overlaps:
                continue
            seen_spans.add(span)
            found.append(match.group())

    return found
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_numeric_tokenizer.py -v
```

Expected: All tests PASS. If any fail, adjust the patterns.

- [ ] **Step 6: Commit**

```bash
git add app/agents/__init__.py app/agents/numeric_tokenizer.py tests/test_numeric_tokenizer.py
git commit -m "feat: numeric token classifier for claim verification"
```

---

### Task 5: Brand Compliance Gate

**Files:**
- Create: `app/agents/compliance.py`
- Create: `tests/test_compliance.py`

- [ ] **Step 1: Write the compliance tests**

```python
# tests/test_compliance.py
from app.agents.compliance import run_compliance_checks, ComplianceResult


def _make_draft(content: str, claim_keys_used: list[str] | None = None):
    return {
        "content": content,
        "claim_keys_used": claim_keys_used or [],
        "hashtags": [],
    }


# --- Banned phrases ---

def test_banned_phrase_rejected():
    draft = _make_draft("This is a game-changing product")
    result = run_compliance_checks(draft, requested_claims=[])
    assert not result.passed
    assert "banned_phrases" in result.failed_check


def test_banned_phrase_case_insensitive():
    draft = _make_draft("We LEVERAGE DATA to win")
    result = run_compliance_checks(draft, requested_claims=[])
    assert not result.passed
    assert "banned_phrases" in result.failed_check


# --- Trademarks ---

def test_trademark_auto_corrected():
    draft = _make_draft("The Clutch Factor score matters")
    result = run_compliance_checks(draft, requested_claims=[])
    assert result.passed
    assert "Clutch Factor™" in result.corrected_content


def test_trademark_already_correct():
    draft = _make_draft("The Clutch Factor™ score matters")
    result = run_compliance_checks(draft, requested_claims=[])
    assert result.passed
    assert result.corrected_content == "The Clutch Factor™ score matters"


# --- Restricted clients ---

def test_restricted_client_rejected():
    draft = _make_draft("Florida A&M is using our platform")
    result = run_compliance_checks(draft, requested_claims=[])
    assert not result.passed
    assert "restricted_clients" in result.failed_check


def test_restricted_client_famu_rejected():
    draft = _make_draft("FAMU signed up today")
    result = run_compliance_checks(draft, requested_claims=[])
    assert not result.passed


def test_verified_client_allowed():
    draft = _make_draft("Michigan State is measuring what matters")
    result = run_compliance_checks(draft, requested_claims=[])
    assert result.passed


# --- Factual claims (key level) ---

def test_claim_key_not_in_request_rejected():
    draft = _make_draft("73% success rate", claim_keys_used=["cf_all_american"])
    result = run_compliance_checks(draft, requested_claims=[])
    assert not result.passed
    assert "claim_keys" in result.failed_check


def test_claim_key_valid():
    draft = _make_draft("73% of athletes above 800 CF", claim_keys_used=["cf_all_american"])
    result = run_compliance_checks(draft, requested_claims=["cf_all_american"])
    assert result.passed


# --- Factual claims (text level) ---

def test_claim_wrong_number_rejected():
    draft = _make_draft("85% of athletes above 800 CF", claim_keys_used=["cf_all_american"])
    result = run_compliance_checks(draft, requested_claims=["cf_all_american"])
    assert not result.passed
    assert "claim_text" in result.failed_check


# --- Undeclared numerics ---

def test_undeclared_numeric_rejected():
    draft = _make_draft("90% of coaches agree this works", claim_keys_used=[])
    result = run_compliance_checks(draft, requested_claims=[])
    assert not result.passed
    assert "undeclared_numerics" in result.failed_check


def test_ordinal_not_flagged():
    draft = _make_draft("The 1st thing D1 coaches notice")
    result = run_compliance_checks(draft, requested_claims=[])
    assert result.passed


# --- Tone ---

def test_exclamation_rejected():
    draft = _make_draft("This is amazing! Wow!")
    result = run_compliance_checks(draft, requested_claims=[])
    assert not result.passed
    assert "tone" in result.failed_check


# --- Character limit ---

def test_over_280_rejected():
    draft = _make_draft("x" * 281)
    result = run_compliance_checks(draft, requested_claims=[])
    assert not result.passed
    assert "char_limit" in result.failed_check


def test_exactly_280_passes():
    draft = _make_draft("x" * 280)
    result = run_compliance_checks(draft, requested_claims=[])
    assert result.passed


# --- Hashtag limit ---

def test_excess_hashtags_trimmed():
    draft = _make_draft("Good tweet")
    draft["hashtags"] = ["#one", "#two", "#three"]
    result = run_compliance_checks(draft, requested_claims=[])
    assert result.passed
    assert len(result.corrected_hashtags) == 2


# --- Clean pass ---

def test_clean_tweet_passes():
    draft = _make_draft("Personality profiles tell you who someone is in the locker room. Not who they are in the bottom of the 9th.")
    result = run_compliance_checks(draft, requested_claims=[])
    assert result.passed
    assert result.failed_check is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_compliance.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create app/agents/compliance.py**

```python
import re
from dataclasses import dataclass, field

from app.config import get_brand_voice, get_approved_claims
from app.agents.numeric_tokenizer import extract_claim_numerics


@dataclass
class ComplianceResult:
    passed: bool
    failed_check: str | None = None
    failure_reason: str | None = None
    corrected_content: str | None = None
    corrected_hashtags: list[str] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)


def run_compliance_checks(
    draft: dict,
    requested_claims: list[str],
) -> ComplianceResult:
    brand = get_brand_voice()
    claims_config = get_approved_claims()
    content = draft["content"]
    claim_keys_used = draft.get("claim_keys_used", [])
    hashtags = list(draft.get("hashtags", []))
    checks_run = []

    # 1. Banned phrases
    checks_run.append("banned_phrases")
    content_lower = content.lower()
    for phrase in brand["banned_phrases"]:
        if phrase.lower() in content_lower:
            return ComplianceResult(
                passed=False,
                failed_check="banned_phrases",
                failure_reason=f"Contains banned phrase: '{phrase}'",
                checks_run=checks_run,
            )

    # 2. Trademark enforcement (auto-correct, no rejection)
    checks_run.append("trademarks")
    corrected = content
    for correct_form, variants in brand["trademarks"].items():
        for variant in variants:
            pattern = re.compile(re.escape(variant), re.IGNORECASE)
            corrected = pattern.sub(correct_form, corrected)

    # 3. Restricted clients
    checks_run.append("restricted_clients")
    restricted = brand["restricted_clients"]
    for name in restricted["hard_block"]:
        if name.lower() in corrected.lower():
            return ComplianceResult(
                passed=False,
                failed_check="restricted_clients",
                failure_reason=f"References restricted client: '{name}'",
                checks_run=checks_run,
            )

    # 4. Factual claims — key level
    checks_run.append("claim_keys")
    for key in claim_keys_used:
        if key not in requested_claims:
            return ComplianceResult(
                passed=False,
                failed_check="claim_keys",
                failure_reason=f"Claim key '{key}' was not in the requested claims",
                checks_run=checks_run,
            )
        if key not in claims_config["claims"]:
            return ComplianceResult(
                passed=False,
                failed_check="claim_keys",
                failure_reason=f"Claim key '{key}' does not exist in approved_claims.yaml",
                checks_run=checks_run,
            )

    # 5. Factual claims — text level
    checks_run.append("claim_text")
    for key in claim_keys_used:
        claim = claims_config["claims"][key]
        for value_group in claim["check_value_groups"]:
            if not any(variant in corrected for variant in value_group):
                return ComplianceResult(
                    passed=False,
                    failed_check="claim_text",
                    failure_reason=f"Claim '{key}' declared but required value {value_group} not found in text",
                    checks_run=checks_run,
                )

    # 6. Undeclared numerics
    checks_run.append("undeclared_numerics")
    numeric_tokens = extract_claim_numerics(corrected)
    # Build set of all covered values from declared claims
    covered_values: set[str] = set()
    for key in claim_keys_used:
        claim = claims_config["claims"][key]
        for value_group in claim["check_value_groups"]:
            covered_values.update(value_group)

    for token in numeric_tokens:
        if not any(token in cv or cv in token for cv in covered_values):
            return ComplianceResult(
                passed=False,
                failed_check="undeclared_numerics",
                failure_reason=f"Undeclared numeric '{token}' in text — not covered by any approved claim",
                checks_run=checks_run,
            )

    # 7. Tone check
    checks_run.append("tone")
    exclamation_count = corrected.count("!")
    if exclamation_count > 0:
        return ComplianceResult(
            passed=False,
            failed_check="tone",
            failure_reason=f"Contains {exclamation_count} exclamation point(s)",
            checks_run=checks_run,
        )
    # Simple passive voice heuristic: "was/were/been/being + past participle pattern"
    passive_patterns = [
        r"\b(?:was|were|been|being)\s+\w+ed\b",
        r"\b(?:is|are)\s+being\s+\w+ed\b",
    ]
    for pattern in passive_patterns:
        if re.search(pattern, corrected, re.IGNORECASE):
            return ComplianceResult(
                passed=False,
                failed_check="tone",
                failure_reason="Contains passive voice construction",
                checks_run=checks_run,
            )

    # 8. Character limit
    checks_run.append("char_limit")
    if len(corrected) > 280:
        return ComplianceResult(
            passed=False,
            failed_check="char_limit",
            failure_reason=f"Tweet is {len(corrected)} chars (max 280)",
            checks_run=checks_run,
        )

    # 9. Hashtag limit (auto-trim)
    checks_run.append("hashtags")
    corrected_hashtags = hashtags[:2]

    return ComplianceResult(
        passed=True,
        corrected_content=corrected,
        corrected_hashtags=corrected_hashtags,
        checks_run=checks_run,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_compliance.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/agents/compliance.py tests/test_compliance.py
git commit -m "feat: brand compliance gate with factual claim verification"
```

---

### Task 6: Publisher Interface & Mock Publisher

**Files:**
- Create: `app/publishers/__init__.py`
- Create: `app/publishers/base.py`
- Create: `app/publishers/mock.py`
- Create: `tests/test_publisher.py`

- [ ] **Step 1: Write the publisher tests**

```python
# tests/test_publisher.py
from app.publishers.base import PostResult
from app.publishers.mock import MockPublisher


def test_mock_post_tweet_succeeds():
    pub = MockPublisher()
    result = pub.post_tweet("Hello world")
    assert result.success is True
    assert result.tweet_id is not None
    assert "mock" in result.tweet_url
    assert result.posted_at is not None


def test_mock_post_tweet_with_media():
    pub = MockPublisher()
    result = pub.post_tweet("With image", media="image.png")
    assert result.success is True


def test_mock_delete_tweet():
    pub = MockPublisher()
    result = pub.post_tweet("To delete")
    assert pub.delete_tweet(result.tweet_id) is True


def test_mock_tracks_posts():
    pub = MockPublisher()
    pub.post_tweet("First")
    pub.post_tweet("Second")
    assert len(pub.posted) == 2
    assert pub.posted[0]["text"] == "First"
    assert pub.posted[1]["text"] == "Second"


def test_post_result_fields():
    result = PostResult(
        success=True,
        tweet_id="123",
        tweet_url="https://x.com/test/status/123",
        posted_at="2026-04-06T12:00:00Z",
    )
    assert result.success is True
    assert result.tweet_id == "123"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_publisher.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create app/publishers/__init__.py**

Empty file.

- [ ] **Step 4: Create app/publishers/base.py**

```python
from dataclasses import dataclass


@dataclass
class PostResult:
    success: bool
    tweet_id: str | None = None
    tweet_url: str | None = None
    posted_at: str | None = None
    error: str | None = None


class BasePublisher:
    def post_tweet(self, text: str, media: str | None = None) -> PostResult:
        raise NotImplementedError

    def delete_tweet(self, tweet_id: str) -> bool:
        raise NotImplementedError
```

- [ ] **Step 5: Create app/publishers/mock.py**

```python
import uuid
from datetime import datetime, timezone

from app.publishers.base import BasePublisher, PostResult


class MockPublisher(BasePublisher):
    def __init__(self):
        self.posted: list[dict] = []
        self.deleted: list[str] = []

    def post_tweet(self, text: str, media: str | None = None) -> PostResult:
        tweet_id = str(uuid.uuid4())[:12]
        posted_at = datetime.now(timezone.utc).isoformat()
        self.posted.append({"text": text, "media": media, "tweet_id": tweet_id})
        return PostResult(
            success=True,
            tweet_id=tweet_id,
            tweet_url=f"https://x.com/mock/status/{tweet_id}",
            posted_at=posted_at,
        )

    def delete_tweet(self, tweet_id: str) -> bool:
        self.deleted.append(tweet_id)
        return True
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_publisher.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add app/publishers/ tests/test_publisher.py
git commit -m "feat: publisher interface and mock publisher"
```

---

### Task 7: Tweepy Publisher (Production)

**Files:**
- Create: `app/publishers/tweepy_pub.py`

- [ ] **Step 1: Create app/publishers/tweepy_pub.py**

```python
import time
import logging
from datetime import datetime, timezone

import tweepy

from app.publishers.base import BasePublisher, PostResult
from app.config import get_settings

logger = logging.getLogger(__name__)


class TweepyPublisher(BasePublisher):
    def __init__(self):
        settings = get_settings()
        self.client = tweepy.Client(
            consumer_key=settings.x_api_key,
            consumer_secret=settings.x_api_secret,
            access_token=settings.x_access_token,
            access_token_secret=settings.x_access_token_secret,
        )

    def post_tweet(self, text: str, media: str | None = None) -> PostResult:
        max_retries = 3
        backoff_seconds = [30, 60, 120]

        for attempt in range(max_retries + 1):
            try:
                response = self.client.create_tweet(text=text)
                tweet_id = str(response.data["id"])
                return PostResult(
                    success=True,
                    tweet_id=tweet_id,
                    tweet_url=f"https://x.com/i/status/{tweet_id}",
                    posted_at=datetime.now(timezone.utc).isoformat(),
                )
            except tweepy.TooManyRequests:
                if attempt < max_retries:
                    wait = backoff_seconds[attempt]
                    logger.warning(f"Rate limited, retrying in {wait}s (attempt {attempt + 1})")
                    time.sleep(wait)
                    continue
                return PostResult(success=False, error="Rate limited after max retries")
            except tweepy.Unauthorized:
                return PostResult(success=False, error="Authentication failed (401)")
            except tweepy.Forbidden:
                return PostResult(success=False, error="Forbidden (403)")
            except tweepy.BadRequest as e:
                return PostResult(success=False, error=f"Bad request: {e}")
            except Exception as e:
                # Ambiguous — could have succeeded on X
                logger.error(f"Ambiguous publish result: {e}")
                return PostResult(success=False, error=f"unknown: {e}")

        return PostResult(success=False, error="Exhausted retries")

    def delete_tweet(self, tweet_id: str) -> bool:
        try:
            self.client.delete_tweet(tweet_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete tweet {tweet_id}: {e}")
            return False
```

- [ ] **Step 2: Commit**

```bash
git add app/publishers/tweepy_pub.py
git commit -m "feat: tweepy publisher for official X API v2"
```

---

### Task 8: Publisher Factory

**Files:**
- Modify: `app/publishers/__init__.py`
- Create: `tests/test_publisher_factory.py`

- [ ] **Step 1: Write the factory test**

```python
# tests/test_publisher_factory.py
import os

from app.publishers import get_publisher
from app.publishers.mock import MockPublisher


def test_get_mock_publisher(monkeypatch):
    monkeypatch.setenv("X_PUBLISHER", "mock")
    pub = get_publisher()
    assert isinstance(pub, MockPublisher)


def test_get_publisher_default_is_mock(monkeypatch):
    monkeypatch.setenv("X_PUBLISHER", "mock")
    pub = get_publisher()
    assert isinstance(pub, MockPublisher)


def test_get_publisher_invalid_raises(monkeypatch):
    import pytest
    monkeypatch.setenv("X_PUBLISHER", "invalid")
    with pytest.raises(ValueError, match="Unknown publisher"):
        get_publisher()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_publisher_factory.py -v
```

Expected: FAIL — `get_publisher` not defined.

- [ ] **Step 3: Implement app/publishers/__init__.py**

```python
from app.publishers.base import BasePublisher
from app.config import get_settings


def get_publisher() -> BasePublisher:
    publisher_type = get_settings().x_publisher.lower()

    if publisher_type == "mock":
        from app.publishers.mock import MockPublisher
        return MockPublisher()
    elif publisher_type == "tweepy":
        from app.publishers.tweepy_pub import TweepyPublisher
        return TweepyPublisher()
    elif publisher_type == "twikit":
        from app.publishers.twikit_pub import TwikitPublisher
        return TwikitPublisher()
    else:
        raise ValueError(f"Unknown publisher: {publisher_type}. Use mock, tweepy, or twikit.")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_publisher_factory.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/publishers/__init__.py tests/test_publisher_factory.py
git commit -m "feat: publisher factory with env-based selection"
```

---

### Task 9: Content Writer Agent

**Files:**
- Create: `app/agents/content_writer.py`
- Create: `tests/test_content_writer.py`

- [ ] **Step 1: Write the content writer tests**

```python
# tests/test_content_writer.py
from app.agents.content_writer import build_prompt, parse_generation_response


def test_build_prompt_includes_brand_voice():
    prompt = build_prompt(
        content_type="hot_take",
        pillar="blind_spot",
        claims=[],
        context=None,
    )
    assert "sports bar meets data lab" in prompt["system"].lower() or "punchy" in prompt["system"].lower()


def test_build_prompt_includes_pillar():
    prompt = build_prompt(
        content_type="hot_take",
        pillar="blind_spot",
        claims=[],
        context=None,
    )
    assert "evaluating half the picture" in prompt["system"].lower() or "blind_spot" in prompt["user"].lower()


def test_build_prompt_includes_banned_phrases():
    prompt = build_prompt(
        content_type="hot_take",
        pillar="blind_spot",
        claims=[],
        context=None,
    )
    system = prompt["system"].lower()
    assert "game-changing" in system or "banned" in system


def test_build_prompt_includes_claims():
    prompt = build_prompt(
        content_type="data_drop",
        pillar="cost_of_guessing",
        claims=["failed_transfer_cost"],
        context=None,
    )
    combined = prompt["system"] + prompt["user"]
    assert "$150K" in combined or "150K" in combined


def test_build_prompt_includes_context():
    prompt = build_prompt(
        content_type="trend_jack",
        pillar="blind_spot",
        claims=[],
        context="Transfer portal just opened",
    )
    assert "Transfer portal just opened" in prompt["user"]


def test_build_prompt_char_limit():
    prompt = build_prompt(
        content_type="hot_take",
        pillar="blind_spot",
        claims=[],
        context=None,
    )
    assert "280" in prompt["system"]


def test_parse_valid_response():
    raw = {
        "content": "Test tweet",
        "content_type": "hot_take",
        "pillar": "blind_spot",
        "claim_keys_used": [],
        "hashtags": ["#Test"],
        "media_needed": False,
        "intent": "brand",
    }
    parsed = parse_generation_response(raw)
    assert parsed["content"] == "Test tweet"
    assert parsed["intent"] == "brand"


def test_parse_response_missing_field_raises():
    import pytest
    raw = {"content": "Test tweet"}
    with pytest.raises(ValueError):
        parse_generation_response(raw)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_content_writer.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create app/agents/content_writer.py**

```python
import json
import time
import logging
from typing import Any

import anthropic

from app.config import (
    get_settings,
    get_brand_voice,
    get_content_pillars,
    get_approved_claims,
    get_platform_config,
)

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {"content", "content_type", "pillar", "claim_keys_used", "hashtags", "media_needed", "intent"}


def build_prompt(
    content_type: str,
    pillar: str,
    claims: list[str],
    context: str | None,
) -> dict[str, str]:
    brand = get_brand_voice()
    pillars = get_content_pillars()
    claims_config = get_approved_claims()
    platform = get_platform_config("x")

    pillar_data = pillars["pillars"][pillar]

    # Build approved claims section
    claims_text = ""
    if claims:
        claims_lines = []
        for key in claims:
            if key in claims_config["claims"]:
                claim = claims_config["claims"][key]
                claims_lines.append(f"- {key}: {claim['text']} (Source: {claim['source']})")
        claims_text = "\n".join(claims_lines)

    system_prompt = f"""You are a social media content writer for NTangible, a sports tech company that measures athlete mental performance under pressure using Clutch Factor™.

BRAND VOICE:
{brand['voice']['personality']}

DO:
{chr(10).join('- ' + rule for rule in brand['voice']['do'])}

DON'T:
{chr(10).join('- ' + rule for rule in brand['voice']['dont'])}

BANNED PHRASES (never use these):
{chr(10).join('- "' + phrase + '"' for phrase in brand['banned_phrases'])}

TRADEMARK RULES:
- Always write "Clutch Factor™" with the ™ symbol
- Always capitalize "NTangible Score" and "The Pressure Test" correctly

PLATFORM CONSTRAINTS (X/Twitter):
- Maximum {platform['x']['single_tweet_max_chars']} characters
- Maximum {platform['x']['max_hashtags']} hashtags
- Single tweet only (no threads)

FACTUAL CLAIMS RULE:
Do not invent statistics, percentages, dollar amounts, client names, or outcomes. Use ONLY the approved claims provided below. If no claims are provided, do not include any numeric assertions.

{f"APPROVED CLAIMS YOU MAY USE:{chr(10)}{claims_text}" if claims_text else "NO APPROVED CLAIMS PROVIDED — do not include any numeric facts."}

VERIFIED CLIENTS (only these may be named):
{chr(10).join('- ' + c for c in brand['verified_clients'])}

OUTPUT FORMAT:
Return exactly 3 JSON objects separated by newlines. Each must have these fields:
- content: the tweet text (string)
- content_type: "{content_type}"
- pillar: "{pillar}"
- claim_keys_used: list of approved claim keys actually referenced in the tweet (may be empty)
- hashtags: list of 0-{platform['x']['max_hashtags']} hashtags
- media_needed: boolean
- intent: "brand" | "partner" | "revenue"
"""

    user_prompt = f"""Generate 3 variations of a {content_type} tweet for the "{pillar}" content pillar.

Pillar description: {pillar_data['description']}
Example angles: {', '.join(pillar_data['example_angles'])}

{f"Context: {context}" if context else ""}

Return exactly 3 JSON objects, one per line. Each must be valid JSON."""

    return {"system": system_prompt, "user": user_prompt}


def parse_generation_response(raw: dict) -> dict:
    missing = REQUIRED_FIELDS - set(raw.keys())
    if missing:
        raise ValueError(f"Missing fields in generation response: {missing}")
    return raw


def generate_tweets(
    content_type: str,
    pillar: str,
    claims: list[str],
    context: str | None,
) -> tuple[list[dict], dict]:
    """Generate tweet variations via Claude API.

    Returns (variations, log_data) where log_data contains prompt, response, token counts.
    """
    settings = get_settings()
    prompt = build_prompt(content_type, pillar, claims, context)

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    start = time.time()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=prompt["system"],
        messages=[{"role": "user", "content": prompt["user"]}],
    )
    duration_ms = int((time.time() - start) * 1000)

    raw_text = response.content[0].text

    # Parse the response — expect 3 JSON objects, one per line
    variations = []
    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
            validated = parse_generation_response(parsed)
            variations.append(validated)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Skipping malformed variation: {e}")
            continue

    log_data = {
        "prompt_snapshot": prompt["system"] + "\n---\n" + prompt["user"],
        "response": {"raw_text": raw_text, "parsed_count": len(variations)},
        "model": "claude-sonnet-4-6",
        "tokens_in": response.usage.input_tokens,
        "tokens_out": response.usage.output_tokens,
        "cost_estimate": (response.usage.input_tokens * 0.003 + response.usage.output_tokens * 0.015) / 1000,
        "duration_ms": duration_ms,
    }

    return variations, log_data
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_content_writer.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/agents/content_writer.py tests/test_content_writer.py
git commit -m "feat: content writer agent with Claude prompt assembly"
```

---

### Task 10: API Routes

**Files:**
- Create: `app/api/__init__.py`
- Create: `app/api/routes.py`
- Create: `app/api/schemas.py`
- Modify: `app/main.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Create app/api/schemas.py**

```python
from pydantic import BaseModel


class GenerateRequest(BaseModel):
    content_type: str  # hot_take | data_drop | trend_jack
    pillar: str  # blind_spot | cost_of_guessing | client_proof | thought_leadership | product
    claims: list[str] = []
    context: str | None = None


class ResolveRequest(BaseModel):
    outcome: str  # published | failed
    tweet_url: str | None = None
    tweet_id: str | None = None
```

- [ ] **Step 2: Create app/api/__init__.py**

Empty file.

- [ ] **Step 3: Create app/api/routes.py**

```python
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.main import verify_api_key
from app.models.content import ContentQueue, GenerationLog, ContentType, Pillar, Intent, Status
from app.agents.content_writer import generate_tweets
from app.agents.compliance import run_compliance_checks
from app.publishers import get_publisher
from app.api.schemas import GenerateRequest, ResolveRequest

router = APIRouter()

CONTENT_TYPE_MAP = {
    "hot_take": ContentType.HOT_TAKE,
    "data_drop": ContentType.DATA_DROP,
    "trend_jack": ContentType.TREND_JACK,
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
TREND_JACK_EXPIRY_MINUTES = 60


@router.post("/content/generate", dependencies=[Depends(verify_api_key)])
def generate_content(req: GenerateRequest, db: Session = Depends(get_db)):
    if req.content_type not in CONTENT_TYPE_MAP:
        raise HTTPException(400, f"Invalid content_type: {req.content_type}")
    if req.pillar not in PILLAR_MAP:
        raise HTTPException(400, f"Invalid pillar: {req.pillar}")

    variations, log_data = generate_tweets(
        content_type=req.content_type,
        pillar=req.pillar,
        claims=req.claims,
        context=req.context,
    )

    if not variations:
        raise HTTPException(500, "No valid variations generated")

    variant_group = uuid.uuid4()
    request_payload = req.model_dump()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=TREND_JACK_EXPIRY_MINUTES) if req.content_type == "trend_jack" else None

    drafts = []
    for var in variations:
        result = run_compliance_checks(
            draft=var,
            requested_claims=req.claims,
        )

        if not result.passed:
            # Try regeneration up to 3 times total (handled by caller in future; for now, skip failed)
            continue

        item = ContentQueue(
            id=uuid.uuid4(),
            content=result.corrected_content or var["content"],
            content_type=CONTENT_TYPE_MAP[req.content_type],
            pillar=PILLAR_MAP[req.pillar],
            intent=INTENT_MAP.get(var.get("intent", "brand"), Intent.BRAND),
            hashtags=result.corrected_hashtags,
            status=Status.DRAFT,
            variant_group=variant_group,
            request_payload=request_payload,
            expires_at=expires_at,
            compliance_result={
                "passed": result.passed,
                "checks_run": result.checks_run,
            },
        )
        db.add(item)
        drafts.append(item)

    # Log the generation
    gen_log = GenerationLog(
        id=uuid.uuid4(),
        content_queue_id=drafts[0].id if drafts else None,
        prompt_snapshot=log_data["prompt_snapshot"],
        response=log_data["response"],
        model=log_data["model"],
        tokens_in=log_data["tokens_in"],
        tokens_out=log_data["tokens_out"],
        cost_estimate=log_data["cost_estimate"],
        duration_ms=log_data["duration_ms"],
    )
    db.add(gen_log)
    db.commit()

    return {
        "variant_group": str(variant_group),
        "drafts": [
            {
                "id": str(d.id),
                "content": d.content,
                "hashtags": d.hashtags,
                "intent": d.intent.value,
                "compliance": d.compliance_result,
            }
            for d in drafts
        ],
        "total_generated": len(variations),
        "total_passed": len(drafts),
    }


@router.get("/content/drafts", dependencies=[Depends(verify_api_key)])
def list_drafts(db: Session = Depends(get_db)):
    drafts = db.query(ContentQueue).filter(ContentQueue.status == Status.DRAFT).order_by(ContentQueue.created_at.desc()).all()
    return [
        {
            "id": str(d.id),
            "content": d.content,
            "content_type": d.content_type.value,
            "pillar": d.pillar.value,
            "intent": d.intent.value,
            "hashtags": d.hashtags,
            "variant_group": str(d.variant_group),
            "expires_at": d.expires_at.isoformat() if d.expires_at else None,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in drafts
    ]


@router.get("/content/{content_id}", dependencies=[Depends(verify_api_key)])
def get_content(content_id: str, db: Session = Depends(get_db)):
    item = db.query(ContentQueue).filter(ContentQueue.id == content_id).first()
    if not item:
        raise HTTPException(404, "Content not found")
    return {
        "id": str(item.id),
        "content": item.content,
        "content_type": item.content_type.value,
        "pillar": item.pillar.value,
        "intent": item.intent.value,
        "hashtags": item.hashtags,
        "status": item.status.value,
        "variant_group": str(item.variant_group),
        "post_url": item.post_url,
        "tweet_id": item.tweet_id,
        "compliance_result": item.compliance_result,
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.post("/content/{content_id}/publish", dependencies=[Depends(verify_api_key)])
def publish_content(content_id: str, db: Session = Depends(get_db)):
    # Check expiry for trend_jack
    item = db.query(ContentQueue).filter(ContentQueue.id == content_id).first()
    if not item:
        raise HTTPException(404, "Content not found")
    if item.expires_at and datetime.now(timezone.utc) > item.expires_at:
        raise HTTPException(410, "Draft has expired (trend_jack freshness)")

    # Atomic group claim: set selected to publishing, siblings to rejected
    result = db.execute(
        text("""
            UPDATE content_queue
            SET status = CASE
                    WHEN id = :target_id THEN 'publishing'
                    ELSE 'rejected'
                END,
                updated_at = now()
            WHERE variant_group = (SELECT variant_group FROM content_queue WHERE id = :target_id)
              AND status = 'draft'
            RETURNING id, status
        """),
        {"target_id": content_id},
    )
    rows = result.fetchall()
    db.commit()

    # Check the target was claimed
    target_claimed = any(str(row[0]) == content_id and row[1] == "publishing" for row in rows)
    if not target_claimed:
        raise HTTPException(409, "Draft already claimed, rejected, or not in draft status")

    # Refresh the item after update
    db.refresh(item)

    # Publish to X
    publisher = get_publisher()
    post_result = publisher.post_tweet(item.content)

    if post_result.success:
        item.status = Status.PUBLISHED
        item.tweet_id = post_result.tweet_id
        item.post_url = post_result.tweet_url
        item.published_at = datetime.now(timezone.utc)
    elif post_result.error and post_result.error.startswith("unknown:"):
        item.status = Status.PUBLISHING_UNKNOWN
        item.failure_reason = post_result.error
    else:
        item.status = Status.FAILED
        item.failure_reason = post_result.error

    db.commit()
    db.refresh(item)

    return {
        "id": str(item.id),
        "status": item.status.value,
        "post_url": item.post_url,
        "tweet_id": item.tweet_id,
        "failure_reason": item.failure_reason,
    }


@router.delete("/content/{content_id}", dependencies=[Depends(verify_api_key)])
def delete_content(content_id: str, db: Session = Depends(get_db)):
    item = db.query(ContentQueue).filter(ContentQueue.id == content_id).first()
    if not item:
        raise HTTPException(404, "Content not found")
    if item.status not in (Status.DRAFT, Status.FAILED):
        raise HTTPException(409, f"Cannot delete content in '{item.status.value}' status")
    db.delete(item)
    db.commit()
    return {"deleted": True}


@router.post("/content/{content_id}/regenerate", dependencies=[Depends(verify_api_key)])
def regenerate_content(content_id: str, db: Session = Depends(get_db)):
    item = db.query(ContentQueue).filter(ContentQueue.id == content_id).first()
    if not item:
        raise HTTPException(404, "Content not found")
    if item.status not in (Status.DRAFT, Status.FAILED):
        raise HTTPException(409, f"Cannot regenerate from '{item.status.value}' status")

    # Delete all siblings in the variant group
    db.query(ContentQueue).filter(ContentQueue.variant_group == item.variant_group).delete()
    db.commit()

    # Re-generate using stored request payload
    payload = item.request_payload
    req = GenerateRequest(**payload)
    return generate_content(req, db)


@router.post("/content/{content_id}/resolve", dependencies=[Depends(verify_api_key)])
def resolve_content(content_id: str, req: ResolveRequest, db: Session = Depends(get_db)):
    item = db.query(ContentQueue).filter(ContentQueue.id == content_id).first()
    if not item:
        raise HTTPException(404, "Content not found")
    if item.status != Status.PUBLISHING_UNKNOWN:
        raise HTTPException(409, f"Can only resolve 'publishing_unknown' status, got '{item.status.value}'")

    if req.outcome == "published":
        item.status = Status.PUBLISHED
        item.published_at = datetime.now(timezone.utc)
        if req.tweet_url:
            item.post_url = req.tweet_url
        if req.tweet_id:
            item.tweet_id = req.tweet_id
    elif req.outcome == "failed":
        item.status = Status.FAILED
        item.failure_reason = "Manually resolved as failed"
    else:
        raise HTTPException(400, "outcome must be 'published' or 'failed'")

    db.commit()
    return {"id": str(item.id), "status": item.status.value}


@router.get("/content/published", dependencies=[Depends(verify_api_key)])
def list_published(db: Session = Depends(get_db)):
    items = db.query(ContentQueue).filter(ContentQueue.status == Status.PUBLISHED).order_by(ContentQueue.published_at.desc()).all()
    return [
        {
            "id": str(i.id),
            "content": i.content,
            "post_url": i.post_url,
            "tweet_id": i.tweet_id,
            "published_at": i.published_at.isoformat() if i.published_at else None,
        }
        for i in items
    ]


@router.get("/system/status", dependencies=[Depends(verify_api_key)])
def system_status(db: Session = Depends(get_db)):
    total = db.query(ContentQueue).count()
    drafts = db.query(ContentQueue).filter(ContentQueue.status == Status.DRAFT).count()
    published = db.query(ContentQueue).filter(ContentQueue.status == Status.PUBLISHED).count()
    failed = db.query(ContentQueue).filter(ContentQueue.status == Status.FAILED).count()
    unknown = db.query(ContentQueue).filter(ContentQueue.status == Status.PUBLISHING_UNKNOWN).count()
    return {
        "status": "active",
        "counts": {
            "total": total,
            "drafts": drafts,
            "published": published,
            "failed": failed,
            "publishing_unknown": unknown,
        },
    }
```

- [ ] **Step 4: Register routes in app/main.py**

Add these lines at the end of `app/main.py`:

```python
from app.api.routes import router

app.include_router(router)
```

- [ ] **Step 5: Write API auth tests**

```python
# tests/test_api.py
import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/test")
os.environ.setdefault("API_KEY", "test-secret-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("X_PUBLISHER", "mock")

from app.main import app

client = TestClient(app)


def test_no_auth_returns_403():
    response = client.get("/system/status")
    assert response.status_code == 403


def test_wrong_auth_returns_401():
    response = client.get(
        "/system/status",
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert response.status_code == 401


def test_correct_auth_passes():
    response = client.get(
        "/system/status",
        headers={"Authorization": "Bearer test-secret-key"},
    )
    # May fail on DB connection but auth itself passes (not 401/403)
    assert response.status_code != 401
    assert response.status_code != 403
```

- [ ] **Step 6: Run auth tests**

```bash
pytest tests/test_api.py -v
```

Expected: All 3 auth tests PASS.

- [ ] **Step 7: Commit**

```bash
git add app/api/ app/main.py tests/test_api.py
git commit -m "feat: API routes with auth, publish safety, state transitions"
```

---

### Task 11: Startup Recovery for Crashed Publishes

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Add startup event to recover crashed publishes**

Add to `app/main.py` before the router include:

```python
from contextlib import asynccontextmanager
from sqlalchemy import text as sa_text
from app.database import SessionLocal


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # On startup: recover any items stuck in 'publishing' (crashed mid-publish)
    db = SessionLocal()
    try:
        result = db.execute(
            sa_text("""
                UPDATE content_queue
                SET status = 'publishing_unknown',
                    failure_reason = 'Server crashed during publish — manually verify on X',
                    updated_at = now()
                WHERE status = 'publishing'
                RETURNING id
            """)
        )
        recovered = result.fetchall()
        if recovered:
            import logging
            logging.getLogger(__name__).warning(
                f"Recovered {len(recovered)} items from 'publishing' to 'publishing_unknown' on startup"
            )
        db.commit()
    finally:
        db.close()
    yield
```

Then change the `app = FastAPI(...)` line to:

```python
app = FastAPI(title="NTangible Marketing Engine", version="0.1.0", lifespan=lifespan)
```

- [ ] **Step 2: Commit**

```bash
git add app/main.py
git commit -m "feat: startup recovery for crashed publishes to publishing_unknown"
```

---

### Task 12: End-to-End Smoke Test

**Files:**
- Create: `tests/test_e2e_smoke.py`

This test verifies the full flow with the mock publisher and no real database (using SQLite in-memory).

- [ ] **Step 1: Write the smoke test**

```python
# tests/test_e2e_smoke.py
"""
End-to-end smoke test for the generate → comply → publish flow.
Uses MockPublisher and skips Claude API (tests prompt assembly + compliance only).
"""
from app.agents.content_writer import build_prompt
from app.agents.compliance import run_compliance_checks
from app.publishers.mock import MockPublisher


def test_generate_comply_publish_flow():
    # 1. Build a prompt (doesn't call Claude)
    prompt = build_prompt(
        content_type="hot_take",
        pillar="blind_spot",
        claims=[],
        context=None,
    )
    assert "system" in prompt
    assert "user" in prompt

    # 2. Simulate a Claude response
    mock_variation = {
        "content": "You measure arm strength, speed, GPA. What about pressure?",
        "content_type": "hot_take",
        "pillar": "blind_spot",
        "claim_keys_used": [],
        "hashtags": ["#MentalPerformance"],
        "media_needed": False,
        "intent": "brand",
    }

    # 3. Run compliance
    result = run_compliance_checks(mock_variation, requested_claims=[])
    assert result.passed, f"Compliance failed: {result.failure_reason}"

    # 4. Publish via mock
    publisher = MockPublisher()
    post_result = publisher.post_tweet(result.corrected_content)
    assert post_result.success
    assert post_result.tweet_url is not None


def test_compliance_rejects_bad_tweet():
    bad_tweet = {
        "content": "This game-changing product will unlock insights!",
        "content_type": "hot_take",
        "pillar": "blind_spot",
        "claim_keys_used": [],
        "hashtags": [],
        "media_needed": False,
        "intent": "brand",
    }
    result = run_compliance_checks(bad_tweet, requested_claims=[])
    assert not result.passed


def test_compliance_rejects_undeclared_number():
    tweet_with_fake_stat = {
        "content": "95% of athletes fail under pressure without training",
        "content_type": "data_drop",
        "pillar": "blind_spot",
        "claim_keys_used": [],
        "hashtags": [],
        "media_needed": False,
        "intent": "brand",
    }
    result = run_compliance_checks(tweet_with_fake_stat, requested_claims=[])
    assert not result.passed
    assert "undeclared_numerics" in result.failed_check


def test_compliance_passes_with_approved_claim():
    tweet_with_claim = {
        "content": "The average failed D1 transfer costs $150K. Know the mental game before you commit.",
        "content_type": "data_drop",
        "pillar": "cost_of_guessing",
        "claim_keys_used": ["failed_transfer_cost"],
        "hashtags": ["#TransferPortal"],
        "media_needed": False,
        "intent": "revenue",
    }
    result = run_compliance_checks(tweet_with_claim, requested_claims=["failed_transfer_cost"])
    assert result.passed, f"Compliance failed: {result.failure_reason}"
```

- [ ] **Step 2: Run the smoke tests**

```bash
pytest tests/test_e2e_smoke.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 3: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e_smoke.py
git commit -m "test: end-to-end smoke test for generate-comply-publish flow"
```

---

### Task 13: Twikit Publisher (Dev Only)

**Files:**
- Create: `app/publishers/twikit_pub.py`

- [ ] **Step 1: Create app/publishers/twikit_pub.py**

```python
import logging
from datetime import datetime, timezone

from twikit import Client

from app.publishers.base import BasePublisher, PostResult
from app.config import get_settings

logger = logging.getLogger(__name__)


class TwikitPublisher(BasePublisher):
    """Dev/test only — uses session cookies, violates X ToS. Not for production."""

    def __init__(self):
        settings = get_settings()
        self.client = Client("en-US")
        self._username = settings.x_twikit_username
        self._password = settings.x_twikit_password
        self._email = settings.x_twikit_email
        self._logged_in = False

    async def _ensure_login(self):
        if not self._logged_in:
            await self.client.login(
                auth_info_1=self._username,
                auth_info_2=self._email,
                password=self._password,
            )
            self._logged_in = True

    def post_tweet(self, text: str, media: str | None = None) -> PostResult:
        import asyncio

        async def _post():
            await self._ensure_login()
            tweet = await self.client.create_tweet(text=text)
            return tweet

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    tweet = pool.submit(asyncio.run, _post()).result()
            else:
                tweet = asyncio.run(_post())

            tweet_id = str(tweet.id)
            return PostResult(
                success=True,
                tweet_id=tweet_id,
                tweet_url=f"https://x.com/i/status/{tweet_id}",
                posted_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            logger.error(f"Twikit publish failed: {e}")
            return PostResult(success=False, error=f"unknown: {e}")

    def delete_tweet(self, tweet_id: str) -> bool:
        import asyncio

        async def _delete():
            await self._ensure_login()
            await self.client.delete_tweet(tweet_id)

        try:
            asyncio.run(_delete())
            return True
        except Exception as e:
            logger.error(f"Twikit delete failed: {e}")
            return False
```

- [ ] **Step 2: Commit**

```bash
git add app/publishers/twikit_pub.py
git commit -m "feat: twikit publisher (dev/test only)"
```

---

### Task 14: Final Verification & .env Setup

- [ ] **Step 1: Run all tests one final time**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 2: Copy .env.example to .env and fill in real values**

```bash
cp .env.example .env
# Edit .env with your actual values:
# - DATABASE_URL (local Postgres or Railway)
# - API_KEY (generate a random secret)
# - ANTHROPIC_API_KEY (your real key)
```

- [ ] **Step 3: Run the database migration**

```bash
alembic upgrade head
```

- [ ] **Step 4: Start the server**

```bash
uvicorn app.main:app --reload
```

- [ ] **Step 5: Test with curl**

```bash
# Health check
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8000/system/status

# Generate drafts
curl -X POST http://localhost:8000/content/generate \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"content_type": "hot_take", "pillar": "blind_spot"}'

# List drafts
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8000/content/drafts

# Publish a draft (replace ID)
curl -X POST http://localhost:8000/content/DRAFT_ID_HERE/publish \
  -H "Authorization: Bearer YOUR_API_KEY"
```

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: Phase 1 complete — content writer + X auto-posting engine"
```
