# Content Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the third blueprint bucket by integrating `blog`, `science`, `video`, `ugc`, `repurposing`, and `sports` into the canonical control-room app with one discoverable expansion surface.

**Architecture:** Reuse the existing services and templates instead of rebuilding them. Mount the missing API/web routers in the main app, add thin control-room GET pages where modules only expose APIs, and add one `Expansion` hub page to make the family discoverable without bloating the top nav.

**Tech Stack:** FastAPI, SQLAlchemy, Jinja2/HTMX, pytest

---

## File Structure

- Modify: `app/main.py`
  Mount the expansion API routers and existing web routers.
- Modify: `app/web/routes.py`
  Add expansion hub route plus thin GET pages for `blog`, `science`, and `repurposing`.
- Modify: `app/web/templates/base.html`
  Add `Expansion` to the top navigation.
- Create: `app/web/templates/expansion.html`
  Hub page linking to all expansion modules.
- Modify: `app/api/blog_routes.py`
  Add `web_router` with `GET /control-room/blog`.
- Modify: `app/api/science_routes.py`
  Add `web_router` with `GET /control-room/science`.
- Modify: `app/api/repurposing_routes.py`
  Add `web_router` with `GET /control-room/repurposing`.
- Test: `tests/test_control_room_api.py`
  Extend canonical route assertions for expansion APIs/pages.
- Create: `tests/test_web_expansion_view.py`
  Verify expansion hub rendering.
- Create: `tests/test_web_blog_route_integration.py`
  Verify main-app blog page renders.
- Create: `tests/test_web_science_route_integration.py`
  Verify main-app science page renders.
- Create: `tests/test_web_repurposing_route_integration.py`
  Verify main-app repurposing page renders.

---

### Task 1: Add Expansion Hub And Main-App Surface

**Files:**
- Modify: `app/web/routes.py`
- Modify: `app/web/templates/base.html`
- Create: `app/web/templates/expansion.html`
- Test: `tests/test_web_expansion_view.py`

- [ ] **Step 1: Write the failing hub test**

```python
def test_expansion_hub_renders_module_cards(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_expansion_modules",
        lambda db: [
            {"slug": "blog", "title": "Blog", "count_label": "2 articles", "href": "/control-room/blog"},
            {"slug": "science", "title": "Science", "count_label": "3 records", "href": "/control-room/science"},
        ],
    )

    response = client.get("/control-room/expansion")

    assert response.status_code == 200
    assert "Content Expansion" in response.text
    assert "Blog" in response.text
    assert "Science" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_expansion_view.py -q`
Expected: FAIL because the route/template/helper do not exist yet.

- [ ] **Step 3: Implement the minimal hub**

```python
def load_expansion_modules(db: Session) -> list[dict[str, str]]:
    return [
        {"slug": "blog", "title": "Blog", "href": "/control-room/blog", "count_label": "..."},
        {"slug": "science", "title": "Science", "href": "/control-room/science", "count_label": "..."},
        {"slug": "video", "title": "Video", "href": "/control-room/video", "count_label": "..."},
        {"slug": "ugc", "title": "UGC", "href": "/control-room/ugc", "count_label": "..."},
        {"slug": "repurposing", "title": "Repurposing", "href": "/control-room/repurposing", "count_label": "..."},
        {"slug": "sports", "title": "Sports", "href": "/control-room/sports", "count_label": "..."},
    ]


@web_router.get("/expansion")
def expansion_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "expansion.html",
        {"page": "expansion", "review_count": load_review_count(db), "modules": load_expansion_modules(db)},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_expansion_view.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/web/routes.py app/web/templates/base.html app/web/templates/expansion.html \
  tests/test_web_expansion_view.py
git commit -m "feat: add control-room expansion hub"
```

---

### Task 2: Mount Expansion Routers In The Main App

**Files:**
- Modify: `app/main.py`
- Modify: `tests/test_control_room_api.py`

- [ ] **Step 1: Write the failing route-registration assertions**

```python
def test_control_room_api_routes_are_namespaced():
    paths = {route.path for route in app.routes}

    assert "/api/control-room/blog" in paths
    assert "/api/control-room/science" in paths
    assert "/api/control-room/repurposing" in paths
    assert "/api/control-room/video" in paths
    assert "/api/control-room/ugc" in paths
    assert "/api/control-room/sports" in paths
    assert "/control-room/expansion" in paths
    assert "/control-room/video" in paths
    assert "/control-room/ugc" in paths
    assert "/control-room/sports" in paths
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_control_room_api.py::test_control_room_api_routes_are_namespaced -q`
Expected: FAIL because the expansion routers are not all mounted in `app.main`.

- [ ] **Step 3: Mount the missing routers**

```python
from app.api.blog_routes import router as blog_router, web_router as blog_web_router
from app.api.science_routes import router as science_router, web_router as science_web_router
from app.api.repurposing_routes import router as repurposing_router, web_router as repurposing_web_router
from app.api.video_routes import router as video_router, web_router as video_web_router
from app.api.ugc_routes import router as ugc_router, web_router as ugc_web_router
from app.api.sports_routes import router as sports_router, web_router as sports_web_router

app.include_router(blog_router)
app.include_router(science_router)
app.include_router(repurposing_router)
app.include_router(video_router)
app.include_router(ugc_router)
app.include_router(sports_router)
app.include_router(blog_web_router)
app.include_router(science_web_router)
app.include_router(repurposing_web_router)
app.include_router(video_web_router)
app.include_router(ugc_web_router)
app.include_router(sports_web_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_control_room_api.py::test_control_room_api_routes_are_namespaced -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_control_room_api.py
git commit -m "feat: mount expansion routers in main app"
```

---

### Task 3: Add Blog, Science, And Repurposing Web Pages

**Files:**
- Modify: `app/api/blog_routes.py`
- Modify: `app/api/science_routes.py`
- Modify: `app/api/repurposing_routes.py`
- Test: `tests/test_web_blog_route_integration.py`
- Test: `tests/test_web_science_route_integration.py`
- Test: `tests/test_web_repurposing_route_integration.py`

- [ ] **Step 1: Write the failing web-route tests**

```python
def test_blog_web_view_renders_articles(monkeypatch):
    monkeypatch.setattr(blog_routes, "BlogService", FakeService)
    response = client.get("/control-room/blog")
    assert response.status_code == 200
    assert "SEO & Blog" in response.text


def test_science_web_view_renders_records(monkeypatch):
    monkeypatch.setattr(science_routes, "ScienceCredibilityService", FakeService)
    response = client.get("/control-room/science")
    assert response.status_code == 200
    assert "Science Credibility" in response.text


def test_repurposing_web_view_renders_dashboard(monkeypatch):
    monkeypatch.setattr(repurposing_routes, "RepurposingService", FakeService)
    response = client.get("/control-room/repurposing")
    assert response.status_code == 200
    assert "Repurposing Engine" in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_web_blog_route_integration.py tests/test_web_science_route_integration.py tests/test_web_repurposing_route_integration.py -q`
Expected: FAIL because the web routers/GET pages do not exist yet.

- [ ] **Step 3: Add thin control-room GET routes**

```python
web_router = APIRouter(prefix="/control-room", tags=["blog-web"])


@web_router.get("/blog")
def blog_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "blog.html",
        {"page": "expansion", **BlogService(db).list_dashboard()},
    )
```

Apply the same pattern to science and repurposing using their service dashboard methods.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_web_blog_route_integration.py tests/test_web_science_route_integration.py tests/test_web_repurposing_route_integration.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/blog_routes.py app/api/science_routes.py app/api/repurposing_routes.py \
  tests/test_web_blog_route_integration.py tests/test_web_science_route_integration.py \
  tests/test_web_repurposing_route_integration.py
git commit -m "feat: add expansion module web pages"
```

---

### Task 4: Verify Existing Expansion Web Lanes Through The Main App

**Files:**
- Modify: `tests/test_control_room_api.py`
- Modify: `tests/test_web_video_view.py`
- Modify: `tests/test_web_ugc_view.py`
- Modify: `tests/test_web_sports_view.py`

- [ ] **Step 1: Add main-app coverage for already-built lanes**

```python
def test_control_room_api_routes_are_namespaced():
    paths = {route.path for route in app.routes}
    assert "/control-room/video" in paths
    assert "/control-room/ugc" in paths
    assert "/control-room/sports" in paths
```

Add or extend route/view tests so they verify the pages still render once mounted via `app.main`.

- [ ] **Step 2: Run tests to verify any missing mounts fail**

Run: `pytest tests/test_control_room_api.py tests/test_web_video_view.py tests/test_web_ugc_view.py tests/test_web_sports_view.py -q`
Expected: FAIL if any route is still not reachable through the canonical app.

- [ ] **Step 3: Fix any remaining page context issues**

```python
return templates.TemplateResponse(
    request,
    "video.html",
    {"page": "expansion", "review_count": 0, **dashboard},
)
```

Keep the page context consistent with the control-room base template for all expansion views.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_control_room_api.py tests/test_web_video_view.py tests/test_web_ugc_view.py tests/test_web_sports_view.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_control_room_api.py tests/test_web_video_view.py tests/test_web_ugc_view.py \
  tests/test_web_sports_view.py
git commit -m "test: cover expansion lanes in canonical control room"
```

---

### Task 5: Full Regression Verification

**Files:**
- Modify as needed based on verification output

- [ ] **Step 1: Run the content-expansion regression slice**

Run:

```bash
pytest tests/test_blog_routes.py tests/test_science_service.py tests/test_video_routes.py \
  tests/test_web_video_view.py tests/test_ugc_service.py tests/test_web_ugc_view.py \
  tests/test_repurposing_service.py tests/test_repurposing_routes.py tests/test_sports_routes.py \
  tests/test_web_expansion_view.py tests/test_web_blog_route_integration.py \
  tests/test_web_science_route_integration.py tests/test_web_repurposing_route_integration.py \
  tests/test_control_room_api.py -q
```

Expected: PASS

- [ ] **Step 2: Run full verification**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add app/main.py app/api/blog_routes.py app/api/science_routes.py app/api/repurposing_routes.py \
  app/web/routes.py app/web/templates/base.html app/web/templates/expansion.html \
  tests/test_control_room_api.py tests/test_web_expansion_view.py \
  tests/test_web_blog_route_integration.py tests/test_web_science_route_integration.py \
  tests/test_web_repurposing_route_integration.py
git commit -m "feat: integrate content expansion into canonical control room"
```
