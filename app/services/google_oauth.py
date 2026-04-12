"""Google OAuth2 service for Gmail and Calendar connections."""
from __future__ import annotations
import logging
from urllib.parse import urlencode

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def get_redirect_uri(request_base_url: str) -> str:
    """Build the OAuth callback URI from the request's base URL."""
    base = str(request_base_url).rstrip("/")
    return f"{base}control-room/brain/settings/oauth/callback"


def build_auth_url(*, redirect_uri: str, channel: str) -> str:
    """Build the Google OAuth consent URL."""
    settings = get_settings()
    scopes = GMAIL_SCOPES if channel == "gmail" else CALENDAR_SCOPES
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "state": channel,  # We pass the channel type in state so the callback knows which connection to create
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code(*, code: str, redirect_uri: str) -> dict:
    """Exchange authorization code for tokens."""
    settings = get_settings()
    response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    response.raise_for_status()
    return response.json()


def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expired access token."""
    settings = get_settings()
    response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    response.raise_for_status()
    return response.json()


def get_user_email(access_token: str) -> str:
    """Get the authenticated user's email address."""
    response = httpx.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    return response.json().get("email", "unknown")


def get_valid_access_token(credential_json: dict) -> str:
    """Get a valid access token, refreshing if needed."""
    from datetime import datetime, timezone
    access_token = credential_json.get("access_token", "")
    expiry = credential_json.get("token_expiry", "")
    refresh_token = credential_json.get("refresh_token", "")

    if expiry:
        try:
            expiry_dt = datetime.fromisoformat(expiry)
            if expiry_dt > datetime.now(timezone.utc):
                return access_token
        except (ValueError, TypeError):
            pass

    if not refresh_token:
        raise ValueError("No refresh token available")

    tokens = refresh_access_token(refresh_token)
    # Note: caller should update credential_json in DB with new tokens
    return tokens["access_token"]
