from fastapi.testclient import TestClient

import app.web.routes as web_routes
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_expansion_hub_renders_module_cards(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_expansion_modules",
        lambda db: [
            {
                "slug": "blog",
                "title": "Blog",
                "description": "Long-form search content.",
                "count_label": "2 articles",
                "href": "/control-room/blog",
            },
            {
                "slug": "science",
                "title": "Science",
                "description": "Evidence-led credibility content.",
                "count_label": "3 records",
                "href": "/control-room/science",
            },
        ],
        raising=False,
    )

    response = client.get("/control-room/expansion")

    assert response.status_code == 200
    assert "Content Expansion" in response.text
    assert "Blog" in response.text
    assert "Science" in response.text
    assert "2 articles" in response.text
    assert "/control-room/blog" in response.text
