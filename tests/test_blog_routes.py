import uuid
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.blog_routes as blog_routes
from app.database import get_db


def _client():
    app = FastAPI()
    app.include_router(blog_routes.router)
    return TestClient(app, raise_server_exceptions=False), app


def test_blog_routes_are_registered():
    paths = {route.path for route in blog_routes.router.routes}
    assert "/api/control-room/blog" in paths
    assert "/api/control-room/blog/drafts" in paths
    assert "/api/control-room/blog/drafts/{article_id}/publish" in paths


def test_generate_blog_route_returns_draft(monkeypatch):
    client, app = _client()

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self):
            return {"articles": [], "counts": {"total": 0}}

        def generate_draft(self, **kwargs):
            assert kwargs["topic"] == "Pressure performance assessment"
            return {
                "id": str(uuid.uuid4()),
                "slug": "pressure-performance-assessment",
                "title": "Pressure Performance Assessment for Coaches",
                "status": "review_ready",
                "word_count": 900,
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(blog_routes, "BlogService", FakeService)

    response = client.post(
        "/api/control-room/blog/drafts",
        headers={"Authorization": "Bearer test-secret-key"},
        json={
            "topic": "Pressure performance assessment",
            "audience": "college coaches",
            "target_keywords": ["pressure performance assessment"],
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "review_ready"
    assert payload["word_count"] == 900


def test_publish_blog_route_returns_publication_result(monkeypatch):
    client, app = _client()
    article_id = uuid.uuid4()

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def publish_article(self, incoming_article_id, *, actor="editor", scheduled_at=None):
            assert incoming_article_id == article_id
            assert actor == "editor"
            return {
                "id": str(article_id),
                "title": "Pressure Performance Assessment for Coaches",
                "status": "published",
                "canonical_url": "https://example.com/blog/pressure-performance-assessment",
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(blog_routes, "BlogService", FakeService)

    response = client.post(
        f"/api/control-room/blog/drafts/{article_id}/publish",
        headers={"Authorization": "Bearer test-secret-key"},
        json={"actor": "editor"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "published"


def test_publish_blog_route_returns_htmx_fragment(monkeypatch):
    client, app = _client()
    article_id = uuid.uuid4()

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def publish_article(self, incoming_article_id, *, actor="editor", scheduled_at=None):
            assert incoming_article_id == article_id
            return {
                "id": str(article_id),
                "title": "Pressure Performance Assessment for Coaches",
                "status": "published",
                "canonical_url": "https://example.com/blog/pressure-performance-assessment",
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(blog_routes, "BlogService", FakeService)

    response = client.post(
        f"/api/control-room/blog/drafts/{article_id}/publish",
        headers={"Authorization": "Bearer test-secret-key", "HX-Request": "true"},
        data={"actor": "editor"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Pressure Performance Assessment for Coaches" in response.text
    assert "https://example.com/blog/pressure-performance-assessment" in response.text


def test_generate_blog_route_accepts_form_post(monkeypatch):
    client, app = _client()

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self):
            return {"articles": [], "counts": {"total": 0}}

        def generate_draft(self, **kwargs):
            assert kwargs["target_keywords"] == ["pressure performance assessment", "mental performance testing"]
            return {
                "id": str(uuid.uuid4()),
                "slug": "pressure-performance-assessment",
                "title": "Pressure Performance Assessment for Coaches",
                "status": "review_ready",
                "word_count": 900,
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(blog_routes, "BlogService", FakeService)

    response = client.post(
        "/api/control-room/blog/drafts",
        headers={"Authorization": "Bearer test-secret-key"},
        data={
            "topic": "Pressure performance assessment",
            "audience": "college coaches",
            "target_keywords": "pressure performance assessment, mental performance testing",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "review_ready"
    assert payload["word_count"] == 900


def test_generate_blog_route_returns_htmx_fragment(monkeypatch):
    client, app = _client()

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self):
            return {"articles": [], "counts": {"total": 0}}

        def generate_draft(self, **kwargs):
            return {
                "id": str(uuid.uuid4()),
                "slug": "pressure-performance-assessment",
                "title": "Pressure Performance Assessment for Coaches",
                "status": "review_ready",
                "word_count": 900,
                "target_keywords": ["pressure performance assessment", "mental performance testing"],
                "canonical_url": None,
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(blog_routes, "BlogService", FakeService)

    response = client.post(
        "/api/control-room/blog/drafts",
        headers={"Authorization": "Bearer test-secret-key", "HX-Request": "true"},
        data={
            "topic": "Pressure performance assessment",
            "audience": "college coaches",
            "target_keywords": "pressure performance assessment, mental performance testing",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Pressure Performance Assessment for Coaches" in response.text
    assert "review_ready" in response.text
    assert "900 words" in response.text
