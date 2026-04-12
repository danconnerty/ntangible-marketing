"""Fetch Google Calendar events and enqueue for processing."""
from __future__ import annotations
import logging

import httpx

from app.models.ingestion import IngestionQueueItem, IngestionSourceType

logger = logging.getLogger(__name__)

CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"


def fetch_changed_events(access_token: str, sync_token: str | None = None) -> tuple[list[dict], str | None]:
    """Fetch changed events from the primary calendar.

    Returns (events, next_sync_token).
    """
    params = {"singleEvents": "true"}
    if sync_token:
        params["syncToken"] = sync_token
    else:
        # Initial sync: get events from last 30 days
        from datetime import datetime, timedelta, timezone
        time_min = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        params["timeMin"] = time_min

    all_events = []
    next_page_token = None
    next_sync_token = None

    while True:
        if next_page_token:
            params["pageToken"] = next_page_token

        response = httpx.get(
            f"{CALENDAR_API_BASE}/calendars/primary/events",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )

        if response.status_code == 410:
            # Sync token expired, need full re-sync
            logger.warning("Calendar sync token expired, performing full sync")
            return fetch_changed_events(access_token, sync_token=None)

        response.raise_for_status()
        data = response.json()

        all_events.extend(data.get("items", []))
        next_page_token = data.get("nextPageToken")
        next_sync_token = data.get("nextSyncToken")

        if not next_page_token:
            break

    return all_events, next_sync_token


def parse_calendar_event(event: dict, self_email: str = "") -> dict:
    """Extract useful fields from a Calendar API event."""
    start = event.get("start", {})
    end = event.get("end", {})

    return {
        "event_id": event.get("id", ""),
        "status": event.get("status", ""),
        "summary": event.get("summary", ""),
        "description": event.get("description", ""),
        "location": event.get("location", ""),
        "start": start.get("dateTime") or start.get("date", ""),
        "end": end.get("dateTime") or end.get("date", ""),
        "attendees": [
            {"email": a.get("email", ""), "responseStatus": a.get("responseStatus", ""), "displayName": a.get("displayName", "")}
            for a in event.get("attendees", [])
        ],
        "organizer": event.get("organizer", {}).get("email", ""),
        "creator": event.get("creator", {}).get("email", ""),
        "self_email": self_email,
    }


def fetch_and_enqueue_calendar_events(db, access_token: str, sync_token: str | None, self_email: str = "") -> tuple[list[str], str | None]:
    """Fetch changed calendar events and enqueue them for processing.

    Returns (enqueued_event_ids, new_sync_token).
    """
    events, new_sync_token = fetch_changed_events(access_token, sync_token)
    enqueued = []

    for event in events:
        event_id = event.get("id", "")
        if not event_id:
            continue

        parsed = parse_calendar_event(event, self_email=self_email)

        try:
            item = IngestionQueueItem(
                source_type=IngestionSourceType.CALENDAR.value,
                source_id=f"cal-event-{event_id}",
                raw_payload=parsed,
            )
            db.add(item)
            enqueued.append(event_id)
            logger.info("Enqueued Calendar event %s: %s", event_id, parsed.get("summary", ""))
        except Exception:
            logger.exception("Failed to enqueue Calendar event %s", event_id)

    if enqueued:
        db.flush()

    return enqueued, new_sync_token
