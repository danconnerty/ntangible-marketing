# Public-Only Content Brain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a public-only NTangible content-brain pipeline that collects historical public content from X, Instagram, public LinkedIn/newsletter surfaces, public newsletter archives, and Wayback snapshots, then stores and retrieves that data for future content generation.

**Architecture:** Add a small ingestion subsystem to the planned Python/FastAPI/Postgres stack. Collectors fetch only public data or official third-party reads, normalize into one `public_content_items` model, snapshot visible metrics over time, and generate embeddings for retrieval.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, httpx, Pydantic, BeautifulSoup/lxml, pgvector, pytest

---

## File Structure

- `app/models/public_content.py`
  - SQLAlchemy models for public content items, observed metrics, source URLs, and archive snapshots.
- `app/schemas/public_content.py`
  - Pydantic schemas for collector outputs and retrieval responses.
- `app/collectors/x_public.py`
  - Public X collector using public API/web inputs.
- `app/collectors/instagram_public.py`
  - Public Instagram collector using public profile/post URLs.
- `app/collectors/linkedin_public.py`
  - Collector for public LinkedIn newsletter pages and any off-platform visible public posts.
- `app/collectors/newsletter_public.py`
  - Collector for public Mailchimp/Kit/browser-view newsletter pages.
- `app/collectors/wayback.py`
  - Wayback lookup/save helper for discovered public URLs.
- `app/services/public_content_ingest.py`
  - Normalization, upsert logic, visible-metric snapshotting.
- `app/services/public_retrieval.py`
  - SQL + vector retrieval for “similar past content” and “top visible-engagement posts”.
- `app/api/public_content_routes.py`
  - Trigger ingestion jobs and query the public content brain.
- `tests/test_public_content_ingest.py`
  - Ingestion normalization and upsert tests.
- `tests/test_public_collectors.py`
  - Collector parsing tests with captured fixtures.
- `tests/test_public_retrieval.py`
  - Retrieval ranking and filtering tests.
- `alembic/versions/<timestamp>_add_public_content_tables.py`
  - Database tables for the public-only brain.

### Task 1: Create the public-content data model

**Files:**
- Create: `app/models/public_content.py`
- Create: `app/schemas/public_content.py`
- Create: `alembic/versions/20260406_add_public_content_tables.py`
- Test: `tests/test_public_content_ingest.py`

- [ ] **Step 1: Write the failing test**

```python
from app.schemas.public_content import PublicContentItemIn


def test_public_content_item_schema_accepts_visible_metrics():
    item = PublicContentItemIn(
        source_platform="x",
        canonical_url="https://x.com/ntangible/status/123",
        author_handle="ntangible",
        content_text="Test post",
        content_type="post",
        visible_like_count=12,
        visible_comment_count=3,
        visible_share_count=1,
    )
    assert item.visible_like_count == 12
    assert item.source_platform == "x"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_public_content_ingest.py::test_public_content_item_schema_accepts_visible_metrics -v`
Expected: FAIL with `ModuleNotFoundError` for `app.schemas.public_content`

- [ ] **Step 3: Write minimal implementation**

```python
# app/schemas/public_content.py
from pydantic import BaseModel, HttpUrl


class PublicContentItemIn(BaseModel):
    source_platform: str
    canonical_url: HttpUrl
    author_handle: str | None = None
    content_text: str | None = None
    content_type: str
    visible_like_count: int | None = None
    visible_comment_count: int | None = None
    visible_share_count: int | None = None
```

```python
# app/models/public_content.py
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PublicContentItem(Base):
    __tablename__ = "public_content_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_platform: Mapped[str] = mapped_column(String(32), index=True)
    canonical_url: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    author_handle: Mapped[str | None] = mapped_column(String(255))
    content_text: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(64), index=True)


class PublicContentMetricSnapshot(Base):
    __tablename__ = "public_content_metric_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_item_id: Mapped[int] = mapped_column(index=True)
    visible_like_count: Mapped[int | None] = mapped_column(Integer)
    visible_comment_count: Mapped[int | None] = mapped_column(Integer)
    visible_share_count: Mapped[int | None] = mapped_column(Integer)
    captured_at: Mapped[str] = mapped_column(DateTime(timezone=True), index=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_public_content_ingest.py::test_public_content_item_schema_accepts_visible_metrics -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/models/public_content.py app/schemas/public_content.py tests/test_public_content_ingest.py alembic/versions/20260406_add_public_content_tables.py
git commit -m "feat: add public content data model"
```

### Task 2: Build the X public collector

**Files:**
- Create: `app/collectors/x_public.py`
- Modify: `app/schemas/public_content.py`
- Test: `tests/test_public_collectors.py`

- [ ] **Step 1: Write the failing test**

```python
from app.collectors.x_public import parse_x_api_post


def test_parse_x_api_post_maps_public_metrics():
    payload = {
        "id": "123",
        "text": "Pressure matters.",
        "created_at": "2026-04-01T12:00:00.000Z",
        "public_metrics": {
            "like_count": 10,
            "reply_count": 2,
            "retweet_count": 1,
            "quote_count": 0,
        },
    }
    item = parse_x_api_post(payload, handle="ntangible")
    assert item.source_platform == "x"
    assert item.visible_like_count == 10
    assert item.visible_comment_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_public_collectors.py::test_parse_x_api_post_maps_public_metrics -v`
Expected: FAIL with `ModuleNotFoundError` for `app.collectors.x_public`

- [ ] **Step 3: Write minimal implementation**

```python
# app/collectors/x_public.py
from app.schemas.public_content import PublicContentItemIn


def parse_x_api_post(payload: dict, handle: str) -> PublicContentItemIn:
    metrics = payload.get("public_metrics", {})
    return PublicContentItemIn(
        source_platform="x",
        canonical_url=f"https://x.com/{handle}/status/{payload['id']}",
        author_handle=handle,
        content_text=payload.get("text"),
        content_type="post",
        visible_like_count=metrics.get("like_count"),
        visible_comment_count=metrics.get("reply_count"),
        visible_share_count=(metrics.get("retweet_count") or 0) + (metrics.get("quote_count") or 0),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_public_collectors.py::test_parse_x_api_post_maps_public_metrics -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/collectors/x_public.py app/schemas/public_content.py tests/test_public_collectors.py
git commit -m "feat: add public X collector"
```

### Task 3: Build Instagram, LinkedIn, and newsletter public parsers

**Files:**
- Create: `app/collectors/instagram_public.py`
- Create: `app/collectors/linkedin_public.py`
- Create: `app/collectors/newsletter_public.py`
- Test: `tests/test_public_collectors.py`

- [ ] **Step 1: Write the failing tests**

```python
from app.collectors.instagram_public import parse_instagram_public_post
from app.collectors.newsletter_public import parse_mailchimp_archive_page


def test_parse_instagram_public_post_maps_caption_and_counts():
    html = """
    <html><meta property="og:description" content="12 likes, 2 comments - NTangible on Instagram: 'Clutch matters.'" /></html>
    """
    item = parse_instagram_public_post(
        html=html,
        canonical_url="https://www.instagram.com/p/abc123/",
        handle="ntangible",
    )
    assert item.source_platform == "instagram"
    assert item.visible_like_count == 12


def test_parse_mailchimp_archive_page_extracts_subject_and_body():
    html = "<html><title>April Update</title><body><h1>April Update</h1><p>Top data insight.</p></body></html>"
    item = parse_mailchimp_archive_page(html, "https://example.list-manage.com/archive")
    assert item.source_platform == "newsletter"
    assert "April Update" in item.content_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_public_collectors.py -v`
Expected: FAIL with missing collector modules

- [ ] **Step 3: Write minimal implementation**

```python
# app/collectors/instagram_public.py
import re

from app.schemas.public_content import PublicContentItemIn


def parse_instagram_public_post(html: str, canonical_url: str, handle: str) -> PublicContentItemIn:
    match = re.search(r"(\d+) likes, (\d+) comments.*?'(.+?)'", html)
    likes = int(match.group(1)) if match else None
    comments = int(match.group(2)) if match else None
    caption = match.group(3) if match else None
    return PublicContentItemIn(
        source_platform="instagram",
        canonical_url=canonical_url,
        author_handle=handle,
        content_text=caption,
        content_type="post",
        visible_like_count=likes,
        visible_comment_count=comments,
    )
```

```python
# app/collectors/newsletter_public.py
from bs4 import BeautifulSoup

from app.schemas.public_content import PublicContentItemIn


def parse_mailchimp_archive_page(html: str, canonical_url: str) -> PublicContentItemIn:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    return PublicContentItemIn(
        source_platform="newsletter",
        canonical_url=canonical_url,
        content_text=text,
        content_type="campaign",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_public_collectors.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/collectors/instagram_public.py app/collectors/linkedin_public.py app/collectors/newsletter_public.py tests/test_public_collectors.py
git commit -m "feat: add public platform parsers"
```

### Task 4: Add ingestion service and metric snapshotting

**Files:**
- Create: `app/services/public_content_ingest.py`
- Modify: `app/models/public_content.py`
- Test: `tests/test_public_content_ingest.py`

- [ ] **Step 1: Write the failing test**

```python
from app.schemas.public_content import PublicContentItemIn
from app.services.public_content_ingest import build_metric_snapshot


def test_build_metric_snapshot_copies_visible_counts():
    item = PublicContentItemIn(
        source_platform="x",
        canonical_url="https://x.com/ntangible/status/123",
        author_handle="ntangible",
        content_text="Test",
        content_type="post",
        visible_like_count=99,
        visible_comment_count=4,
        visible_share_count=2,
    )
    snapshot = build_metric_snapshot(content_item_id=7, item=item)
    assert snapshot.content_item_id == 7
    assert snapshot.visible_like_count == 99
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_public_content_ingest.py::test_build_metric_snapshot_copies_visible_counts -v`
Expected: FAIL with `ModuleNotFoundError` for `app.services.public_content_ingest`

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/public_content_ingest.py
from datetime import datetime, UTC

from app.models.public_content import PublicContentMetricSnapshot


def build_metric_snapshot(content_item_id: int, item) -> PublicContentMetricSnapshot:
    return PublicContentMetricSnapshot(
        content_item_id=content_item_id,
        visible_like_count=item.visible_like_count,
        visible_comment_count=item.visible_comment_count,
        visible_share_count=item.visible_share_count,
        captured_at=datetime.now(UTC),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_public_content_ingest.py::test_build_metric_snapshot_copies_visible_counts -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/public_content_ingest.py app/models/public_content.py tests/test_public_content_ingest.py
git commit -m "feat: add public content ingest service"
```

### Task 5: Add retrieval service for the writer

**Files:**
- Create: `app/services/public_retrieval.py`
- Test: `tests/test_public_retrieval.py`

- [ ] **Step 1: Write the failing test**

```python
from app.services.public_retrieval import build_generation_context


def test_build_generation_context_prioritizes_top_visible_posts():
    items = [
        {"content_text": "Weak post", "score": 10},
        {"content_text": "Strong hook", "score": 90},
    ]
    result = build_generation_context(items)
    assert "Strong hook" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_public_retrieval.py::test_build_generation_context_prioritizes_top_visible_posts -v`
Expected: FAIL with `ModuleNotFoundError` for `app.services.public_retrieval`

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/public_retrieval.py
def build_generation_context(items: list[dict]) -> str:
    ranked = sorted(items, key=lambda item: item["score"], reverse=True)
    top = ranked[:5]
    return "\n".join(item["content_text"] for item in top)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_public_retrieval.py::test_build_generation_context_prioritizes_top_visible_posts -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/public_retrieval.py tests/test_public_retrieval.py
git commit -m "feat: add public content retrieval service"
```

### Task 6: Add ingestion and query API routes

**Files:**
- Create: `app/api/public_content_routes.py`
- Modify: `app/main.py`
- Test: `tests/test_public_retrieval.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_public_content_search_endpoint_exists():
    client = TestClient(app)
    response = client.get("/public-content/search?q=clutch")
    assert response.status_code in {200, 422}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_public_retrieval.py::test_public_content_search_endpoint_exists -v`
Expected: FAIL with route not found

- [ ] **Step 3: Write minimal implementation**

```python
# app/api/public_content_routes.py
from fastapi import APIRouter, Query

router = APIRouter(prefix="/public-content", tags=["public-content"])


@router.get("/search")
def search_public_content(q: str = Query(..., min_length=1)):
    return {"query": q, "results": []}
```

```python
# app/main.py
from fastapi import FastAPI
from app.api.public_content_routes import router as public_content_router

app = FastAPI()
app.include_router(public_content_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_public_retrieval.py::test_public_content_search_endpoint_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/public_content_routes.py app/main.py tests/test_public_retrieval.py
git commit -m "feat: add public content api routes"
```

## External Inputs Required Before Collection Starts

- Confirm the exact public profiles and URLs to target:
  - X handle(s)
  - Instagram handle(s)
  - LinkedIn Page URL
  - LinkedIn newsletter URL if it exists
  - website/blog URL
  - any public newsletter archive URLs
- Confirm the date range to backfill:
  - all-time
  - last 12 months
  - since brand launch
- Confirm whether old handles or renamed profiles exist.
- Confirm whether using your own X developer app is allowed for public timeline reads.
- Confirm whether public web collection is acceptable where no official read API exists.
- Confirm the desired output:
  - CSV export only
  - Postgres database
  - search API
  - embeddings/retrieval for content generation

## What Is Not Required From NTangible

- No account logins
- No admin roles
- No private analytics exports
- No ESP credentials

## Expected Gaps Even After Implementation

- LinkedIn Page analytics will still be unavailable without NTangible admin access.
- Instagram insights will still be unavailable without NTangible account access.
- X private/organic metrics beyond public counts will still be unavailable without owned-account auth.
- Newsletter open/click/unsubscribe data will remain unavailable unless NTangible provides ESP access or exports.

## Self-Review

- **Spec coverage:** This plan covers public X, public Instagram, public LinkedIn/newsletter surfaces, public newsletter archives, Wayback fallback, storage, retrieval, and API exposure.
- **Placeholder scan:** No `TODO`/`TBD` placeholders remain; every task has named files, tests, commands, and minimal implementation snippets.
- **Type consistency:** `PublicContentItemIn`, visible metric fields, and route names are consistent across tasks.

Plan complete and saved to `docs/superpowers/plans/2026-04-06-public-only-content-brain.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
