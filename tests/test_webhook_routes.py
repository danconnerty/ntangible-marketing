from unittest.mock import patch
from fastapi.testclient import TestClient


def _make_app():
    from fastapi import FastAPI
    from app.api.webhook_routes import router
    app = FastAPI()
    app.include_router(router)
    return app


def test_gmail_webhook_enqueues_item():
    app = _make_app()
    client = TestClient(app)
    gmail_push = {
        "message": {
            "data": "eyJlbWFpbEFkZHJlc3MiOiJ0ZXN0QHRlc3QuY29tIiwiaGlzdG9yeUlkIjoiMTIzNDUifQ==",
            "messageId": "msg-001",
        },
        "subscription": "projects/test/subscriptions/gmail-push",
    }
    with patch("app.api.webhook_routes.fetch_and_enqueue_gmail") as mock_fetch:
        mock_fetch.return_value = {"queued": True}
        response = client.post("/webhooks/gmail", json=gmail_push)
    assert response.status_code == 200
    mock_fetch.assert_called_once()


def test_calendar_webhook_enqueues_item():
    app = _make_app()
    client = TestClient(app)
    with patch("app.api.webhook_routes.fetch_and_enqueue_calendar") as mock_fetch:
        mock_fetch.return_value = {"queued": True}
        response = client.post("/webhooks/calendar", headers={"X-Goog-Channel-ID": "channel-123", "X-Goog-Resource-State": "exists"})
    assert response.status_code == 200
    mock_fetch.assert_called_once()


def test_gmail_webhook_returns_200_on_error():
    app = _make_app()
    client = TestClient(app)
    with patch("app.api.webhook_routes.fetch_and_enqueue_gmail", side_effect=Exception("boom")):
        response = client.post("/webhooks/gmail", json={"message": {"data": "dGVzdA==", "messageId": "x"}})
    assert response.status_code == 200
