"""Fetch Gmail messages and enqueue for processing."""
from __future__ import annotations
import logging

import httpx

from app.models.ingestion import IngestionQueueItem, IngestionSourceType

logger = logging.getLogger(__name__)

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"


def fetch_message(access_token: str, message_id: str) -> dict:
    """Fetch a single Gmail message by ID."""
    response = httpx.get(
        f"{GMAIL_API_BASE}/users/me/messages/{message_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"format": "full"},
    )
    response.raise_for_status()
    return response.json()


def fetch_history(access_token: str, history_id: str) -> list[dict]:
    """Fetch message history since a history ID. Returns list of message metadata."""
    response = httpx.get(
        f"{GMAIL_API_BASE}/users/me/history",
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "startHistoryId": history_id,
            "historyTypes": "messageAdded",
        },
    )
    response.raise_for_status()
    data = response.json()

    messages = []
    for record in data.get("history", []):
        for msg_added in record.get("messagesAdded", []):
            messages.append(msg_added["message"])
    return messages


def parse_message_payload(message: dict) -> dict:
    """Extract useful fields from a Gmail API message response."""
    headers = {}
    for header in message.get("payload", {}).get("headers", []):
        headers[header["name"]] = header["value"]

    # Extract body text
    body = ""
    payload = message.get("payload", {})
    if payload.get("body", {}).get("data"):
        import base64
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    elif payload.get("parts"):
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                import base64
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                break

    return {
        "message_id": message.get("id", ""),
        "thread_id": message.get("threadId", ""),
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "subject": headers.get("Subject", ""),
        "date": headers.get("Date", ""),
        "body": body[:10000],  # Truncate very long emails
        "snippet": message.get("snippet", ""),
        "headers": {
            "List-Unsubscribe": headers.get("List-Unsubscribe", ""),
        },
        "label_ids": message.get("labelIds", []),
    }


def fetch_and_enqueue_gmail_messages(db, access_token: str, history_id: str) -> list[str]:
    """Fetch new messages since history_id and enqueue them for processing."""
    enqueued = []

    try:
        messages = fetch_history(access_token, history_id)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning("Gmail history ID %s not found (too old?), skipping", history_id)
            return []
        raise

    for msg_meta in messages:
        msg_id = msg_meta.get("id", "")
        if not msg_id:
            continue

        try:
            full_message = fetch_message(access_token, msg_id)
            parsed = parse_message_payload(full_message)

            item = IngestionQueueItem(
                source_type=IngestionSourceType.GMAIL.value,
                source_id=f"gmail-msg-{msg_id}",
                raw_payload=parsed,
            )
            db.add(item)
            enqueued.append(msg_id)
            logger.info("Enqueued Gmail message %s: %s", msg_id, parsed.get("subject", ""))
        except Exception:
            logger.exception("Failed to fetch/enqueue Gmail message %s", msg_id)

    if enqueued:
        db.flush()

    return enqueued
