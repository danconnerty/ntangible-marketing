# Single-Tenant Connected Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add in-app connection and destination management so the single NTangible dashboard can publish through selected connected accounts/pages instead of relying only on `.env`.

**Architecture:** Introduce persistent connection and destination records, expose them in `/control-room/settings`, and thread the selected destination into the existing publisher factories and publish flows. Preserve `.env` publishers as a fallback so the rollout is incremental.

**Tech Stack:** FastAPI, SQLAlchemy, Jinja2/HTMX, Alembic, pytest

---

## File Structure

- Create: `app/models/publishing_connection.py`
  Purpose: canonical app connection and publishing destination records.
- Create: `app/services/publishing_connection_service.py`
  Purpose: CRUD, summary loading, active destination switching, publish-target resolution.
- Modify: `app/models/__init__.py`
  Purpose: register new models.
- Create: `alembic/versions/20260409_add_publishing_connection_tables.py`
  Purpose: add connection and destination tables.
- Modify: `app/web/routes.py`
  Purpose: extend settings summary and add connection/destination actions.
- Modify: `app/web/templates/settings.html`
  Purpose: render connection cards and destination management forms.
- Create: `app/web/templates/partials/connection_result.html`
  Purpose: HTMX response fragment for connection actions.
- Modify: `app/publishers/linkedin_factory.py`
- Modify: `app/publishers/instagram_factory.py`
- Modify: `app/publishers/newsletter_factory.py`
- Modify: `app/publishers/blog_factory.py`
- Modify: `app/publishers/__init__.py`
  Purpose: accept runtime connection overrides instead of `.env` only.
- Modify: `app/publishers/linkedin_http.py`
- Modify: `app/publishers/instagram_http.py`
- Modify: `app/publishers/mailchimp_http.py`
- Modify: `app/publishers/blog_http.py`
- Modify: `app/publishers/tweepy_pub.py`
- Modify: `app/publishers/twikit_pub.py`
  Purpose: accept explicit runtime credentials/config when provided.
- Modify: `app/services/review_queue.py`
- Modify: `app/services/linkedin_pipeline.py`
- Modify: `app/services/x_pipeline.py`
- Modify: `app/services/instagram_pipeline.py`
- Modify: `app/services/blog_service.py`
  Purpose: resolve the active destination before publishing.
- Create: `tests/test_publishing_connection_service.py`
- Create: `tests/test_publishing_connection_models.py`
- Modify: `tests/test_review_queue.py`
- Modify: `tests/test_publisher_factory.py`
- Modify: `tests/test_web_settings_view.py`

---

### Task 1: Add Canonical Connection Models

**Files:**
- Create: `app/models/publishing_connection.py`
- Modify: `app/models/__init__.py`
- Create: `alembic/versions/20260409_add_publishing_connection_tables.py`
- Test: `tests/test_publishing_connection_models.py`

- [ ] **Step 1: Write the failing model test**
- [ ] **Step 2: Run `pytest tests/test_publishing_connection_models.py -q` and verify it fails**
- [ ] **Step 3: Add `AppConnection` and `PublishingDestination` models plus the Alembic revision**
- [ ] **Step 4: Run `pytest tests/test_publishing_connection_models.py -q` and verify it passes**

---

### Task 2: Add Connection Service

**Files:**
- Create: `app/services/publishing_connection_service.py`
- Test: `tests/test_publishing_connection_service.py`

- [ ] **Step 1: Write failing tests for create/update connection, add/remove destination, and active destination selection**
- [ ] **Step 2: Run `pytest tests/test_publishing_connection_service.py -q` and verify it fails**
- [ ] **Step 3: Implement minimal service methods for summary loading and destination resolution**
- [ ] **Step 4: Run `pytest tests/test_publishing_connection_service.py -q` and verify it passes**

---

### Task 3: Extend Settings UI

**Files:**
- Modify: `app/web/routes.py`
- Modify: `app/web/templates/settings.html`
- Create: `app/web/templates/partials/connection_result.html`
- Modify: `tests/test_web_settings_view.py`

- [ ] **Step 1: Write failing settings-view tests for connection cards and destination management affordances**
- [ ] **Step 2: Run `pytest tests/test_web_settings_view.py -q` and verify it fails**
- [ ] **Step 3: Add settings summary loading plus HTMX actions for save connection, add destination, activate destination, and delete destination**
- [ ] **Step 4: Run `pytest tests/test_web_settings_view.py -q` and verify it passes**

---

### Task 4: Add Runtime Publisher Overrides

**Files:**
- Modify: `app/publishers/linkedin_factory.py`
- Modify: `app/publishers/instagram_factory.py`
- Modify: `app/publishers/newsletter_factory.py`
- Modify: `app/publishers/blog_factory.py`
- Modify: `app/publishers/__init__.py`
- Modify: `app/publishers/linkedin_http.py`
- Modify: `app/publishers/instagram_http.py`
- Modify: `app/publishers/mailchimp_http.py`
- Modify: `app/publishers/blog_http.py`
- Modify: `app/publishers/tweepy_pub.py`
- Modify: `app/publishers/twikit_pub.py`
- Modify: `tests/test_publisher_factory.py`

- [ ] **Step 1: Write failing tests proving publishers can be built from runtime config overrides**
- [ ] **Step 2: Run `pytest tests/test_publisher_factory.py -q` and verify it fails**
- [ ] **Step 3: Implement runtime-config-aware factories and HTTP publisher constructors**
- [ ] **Step 4: Run `pytest tests/test_publisher_factory.py -q` and verify it passes**

---

### Task 5: Thread Active Destinations Into Publish Paths

**Files:**
- Modify: `app/services/review_queue.py`
- Modify: `app/services/linkedin_pipeline.py`
- Modify: `app/services/x_pipeline.py`
- Modify: `app/services/instagram_pipeline.py`
- Modify: `app/services/blog_service.py`
- Modify: `tests/test_review_queue.py`

- [ ] **Step 1: Write failing tests proving publish actions use the active destination when present**
- [ ] **Step 2: Run targeted pytest cases and verify they fail**
- [ ] **Step 3: Resolve the active destination via `PublishingConnectionService` before falling back to `.env`**
- [ ] **Step 4: Run the targeted publish-path tests and verify they pass**

---

### Task 6: Verify Incremental Rollout

**Files:**
- Modify: any touched files as needed

- [ ] **Step 1: Run targeted test suite for models, service, settings UI, publisher factories, and review queue**
- [ ] **Step 2: Confirm legacy `.env` fallback still works when no connection records exist**
- [ ] **Step 3: Summarize remaining gaps tied to real provider credentials or OAuth app setup**
