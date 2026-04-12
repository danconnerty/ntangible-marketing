from fastapi.testclient import TestClient

import app.api.blog_routes as blog_routes
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_blog_web_view_renders_articles(monkeypatch):
    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self):
            return {
                "articles": [
                    {
                        "id": "article-1",
                        "title": "Pressure Performance Assessment for Coaches",
                        "meta_description": "A practical look at pressure performance assessment.",
                        "status": "review_ready",
                        "word_count": 900,
                        "target_keywords": ["pressure performance assessment"],
                    }
                ],
                "counts": {"total": 1},
            }

    monkeypatch.setattr(blog_routes, "BlogService", FakeService)

    response = client.get("/control-room/blog")

    assert response.status_code == 200
    assert "SEO &amp; Blog" in response.text or "SEO & Blog" in response.text
    assert "Pressure Performance Assessment for Coaches" in response.text
    assert "900 words" in response.text
