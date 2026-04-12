"""Rules-based noise filter. Runs before the LLM classifier to skip obvious junk."""
from __future__ import annotations
from dataclasses import dataclass

BOUNCE_SENDERS = {"mailer-daemon", "postmaster"}
NOREPLY_PATTERNS = {"noreply@", "no-reply@", "donotreply@", "do-not-reply@"}


@dataclass
class FilterReason:
    reason: str
    detail: str


def should_filter(source_type: str, raw_payload: dict) -> FilterReason | None:
    if source_type == "gmail":
        return _filter_email(raw_payload)
    if source_type == "calendar":
        return _filter_calendar(raw_payload)
    return None


def _filter_email(payload: dict) -> FilterReason | None:
    headers = payload.get("headers", {})
    if headers.get("List-Unsubscribe"):
        return FilterReason("newsletter_unsubscribe", "Has List-Unsubscribe header")
    sender = (payload.get("from") or "").lower()
    sender_local = sender.split("@")[0] if "@" in sender else sender
    if sender_local in BOUNCE_SENDERS:
        return FilterReason("bounce", f"Bounce sender: {sender}")
    for pattern in NOREPLY_PATTERNS:
        if pattern in sender:
            return FilterReason("noreply_sender", f"No-reply sender: {sender}")
    return None


def _filter_calendar(payload: dict) -> FilterReason | None:
    status = payload.get("status", "").lower()
    if status == "cancelled":
        return FilterReason("cancelled_event", "Event was cancelled")
    self_email = payload.get("self_email", "").lower()
    if self_email:
        attendees = payload.get("attendees", [])
        for attendee in attendees:
            if attendee.get("email", "").lower() == self_email:
                if attendee.get("responseStatus") == "declined":
                    return FilterReason("declined_event", "User declined this event")
    return None
