from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def _make_app():
    from fastapi import FastAPI
    from app.api.context_routes import router
    app = FastAPI()
    app.include_router(router)
    return app


def test_context_endpoint_returns_results():
    from app.database import get_db
    app = _make_app()

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = []

    def override_get_db():
        return mock_db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    response = client.get("/api/mcp/context", params={"q": "Alliance Sports"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert "entities" in data
    assert "knowledge" in data
    assert "query" in data
    assert data["query"] == "Alliance Sports"


def test_context_endpoint_requires_query():
    app = _make_app()
    client = TestClient(app)
    response = client.get("/api/mcp/context")
    assert response.status_code == 422
