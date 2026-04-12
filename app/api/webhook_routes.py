"""Webhook endpoints for Gmail and Google Calendar push notifications."""
from __future__ import annotations
import base64
import json
import logging
from fastapi import APIRouter, Request, Response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])


def fetch_and_enqueue_gmail(push_data: dict) -> dict:
    """Fetch the email via Gmail API and write to ingestion_queue."""
    from app.database import SessionLocal
    from app.models.publishing_connection import AppConnection, ConnectionChannel, ConnectionStatus
    from app.services.google_oauth import get_valid_access_token
    from app.services.gmail_intake import fetch_and_enqueue_gmail_messages

    history_id = push_data.get("historyId", "unknown")

    db = SessionLocal()
    try:
        conn = db.query(AppConnection).filter(
            AppConnection.channel == ConnectionChannel.GMAIL,
            AppConnection.status == ConnectionStatus.CONNECTED,
        ).first()

        if not conn:
            logger.warning("Gmail webhook received but no connected Gmail account")
            return {"queued": False, "reason": "not_connected"}

        access_token = get_valid_access_token(conn.credential_json)
        enqueued = fetch_and_enqueue_gmail_messages(db, access_token, str(history_id))
        db.commit()
        logger.info("Gmail webhook: enqueued %d messages from history_id=%s", len(enqueued), history_id)
        return {"queued": True, "count": len(enqueued)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def fetch_and_enqueue_calendar(channel_id: str, resource_state: str) -> dict:
    """Fetch changed calendar events and write to ingestion_queue."""
    from app.database import SessionLocal
    from app.models.publishing_connection import AppConnection, ConnectionChannel, ConnectionStatus
    from app.services.google_oauth import get_valid_access_token
    from app.services.calendar_intake import fetch_and_enqueue_calendar_events

    db = SessionLocal()
    try:
        conn = db.query(AppConnection).filter(
            AppConnection.channel == ConnectionChannel.CALENDAR,
            AppConnection.status == ConnectionStatus.CONNECTED,
        ).first()

        if not conn:
            logger.warning("Calendar webhook received but no connected Calendar account")
            return {"queued": False, "reason": "not_connected"}

        access_token = get_valid_access_token(conn.credential_json)
        sync_token = conn.config_json.get("sync_token")
        self_email = conn.connection_label or ""

        enqueued, new_sync_token = fetch_and_enqueue_calendar_events(
            db, access_token, sync_token, self_email=self_email,
        )

        # Update sync token
        if new_sync_token:
            config = dict(conn.config_json)
            config["sync_token"] = new_sync_token
            conn.config_json = config

        db.commit()
        logger.info("Calendar webhook: enqueued %d events", len(enqueued))
        return {"queued": True, "count": len(enqueued)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/webhooks/gmail")
async def gmail_webhook(request: Request) -> Response:
    try:
        body = await request.json()
        message = body.get("message", {})
        data_b64 = message.get("data", "")
        push_data = json.loads(base64.b64decode(data_b64).decode("utf-8"))
        fetch_and_enqueue_gmail(push_data)
    except Exception:
        logger.exception("Gmail webhook processing failed")
    return Response(status_code=200)


@router.post("/webhooks/calendar")
async def calendar_webhook(request: Request) -> Response:
    try:
        channel_id = request.headers.get("X-Goog-Channel-ID", "")
        resource_state = request.headers.get("X-Goog-Resource-State", "")
        if resource_state == "sync":
            return Response(status_code=200)
        fetch_and_enqueue_calendar(channel_id, resource_state)
    except Exception:
        logger.exception("Calendar webhook processing failed")
    return Response(status_code=200)
