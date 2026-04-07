from fastapi.testclient import TestClient

from app.main import app


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_no_auth_returns_403():
    with _client() as client:
        response = client.get("/system/status")
        assert response.status_code == 403


def test_wrong_auth_returns_401():
    with _client() as client:
        response = client.get(
            "/system/status",
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert response.status_code == 401


def test_correct_auth_passes():
    with _client() as client:
        response = client.get(
            "/system/status",
            headers={"Authorization": "Bearer test-secret-key"},
        )
        assert response.status_code != 401
        assert response.status_code != 403
