"""Brain Settings page — manage intake connections and view processing activity."""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.ingestion import IngestionQueueItem
from app.models.publishing_connection import AppConnection, ConnectionChannel, ConnectionStatus
from app.services.google_oauth import build_auth_url, exchange_code, get_redirect_uri, get_user_email

logger = logging.getLogger(__name__)

try:
    from fastapi.templating import Jinja2Templates
except ImportError:
    Jinja2Templates = None

templates = (
    Jinja2Templates(directory="app/web/templates")
    if Jinja2Templates is not None
    else None
)

brain_settings_router = APIRouter(prefix="/control-room/brain", tags=["brain-settings"])


@brain_settings_router.get("/settings", response_class=HTMLResponse)
def brain_settings_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    has_google_creds = bool(settings.google_client_id and settings.google_client_secret)

    connections = {}
    for channel in [ConnectionChannel.GMAIL, ConnectionChannel.CALENDAR, ConnectionChannel.TELEGRAM]:
        conn = db.query(AppConnection).filter(AppConnection.channel == channel).first()
        connections[channel.value] = {
            "status": conn.status.value if conn else "disconnected",
            "label": conn.connection_label if conn else None,
        }

    now = datetime.now(timezone.utc)
    total_today = (
        db.query(IngestionQueueItem)
        .filter(IngestionQueueItem.created_at >= now.replace(hour=0, minute=0, second=0))
        .count()
    )
    pending = db.query(IngestionQueueItem).filter(IngestionQueueItem.status == "pending").count()
    errors = (
        db.query(IngestionQueueItem)
        .filter(IngestionQueueItem.status == "failed")
        .filter(IngestionQueueItem.created_at >= now.replace(hour=0, minute=0, second=0))
        .count()
    )

    recent = (
        db.query(IngestionQueueItem)
        .filter(IngestionQueueItem.status.in_(["completed", "filtered"]))
        .order_by(IngestionQueueItem.processed_at.desc())
        .limit(20)
        .all()
    )

    context = {
        "request": request,
        "page": "brain_settings",
        "has_google_creds": has_google_creds,
        "connections": connections,
        "queue_stats": {"total_today": total_today, "pending": pending, "errors": errors},
        "recent_activity": recent,
    }
    return templates.TemplateResponse(request, "brain/settings.html", context)


@brain_settings_router.get("/settings/connect/{channel}")
def connect_channel(channel: str, request: Request):
    """Redirect to Google OAuth consent screen."""
    if channel not in ("gmail", "calendar"):
        return RedirectResponse("/control-room/brain/settings", status_code=303)

    redirect_uri = get_redirect_uri(str(request.base_url))
    auth_url = build_auth_url(redirect_uri=redirect_uri, channel=channel)
    return RedirectResponse(auth_url)


@brain_settings_router.get("/settings/oauth/callback")
def oauth_callback(request: Request, code: str = "", state: str = "", error: str = "", db: Session = Depends(get_db)):
    """Handle Google OAuth callback."""
    if error:
        logger.warning("OAuth error: %s", error)
        return RedirectResponse("/control-room/brain/settings", status_code=303)

    channel = state  # "gmail" or "calendar"
    if channel not in ("gmail", "calendar"):
        logger.warning("Invalid OAuth state: %s", state)
        return RedirectResponse("/control-room/brain/settings", status_code=303)

    redirect_uri = get_redirect_uri(str(request.base_url))

    try:
        tokens = exchange_code(code=code, redirect_uri=redirect_uri)
    except Exception:
        logger.exception("OAuth token exchange failed")
        return RedirectResponse("/control-room/brain/settings", status_code=303)

    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    expires_in = tokens.get("expires_in", 3600)

    # Get user email
    try:
        email = get_user_email(access_token)
    except Exception:
        email = "unknown"

    # Calculate token expiry
    from datetime import timedelta
    token_expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

    # Upsert the connection
    channel_enum = ConnectionChannel.GMAIL if channel == "gmail" else ConnectionChannel.CALENDAR
    conn = db.query(AppConnection).filter(AppConnection.channel == channel_enum).first()

    if conn is None:
        conn = AppConnection(
            channel=channel_enum,
            provider_key="google",
            auth_mode="oauth2",
            status=ConnectionStatus.CONNECTED,
            connection_label=email,
            credential_json={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expiry": token_expiry,
            },
            config_json={"scopes": tokens.get("scope", "").split()},
        )
        db.add(conn)
    else:
        conn.status = ConnectionStatus.CONNECTED
        conn.connection_label = email
        conn.credential_json = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expiry": token_expiry,
        }
        conn.config_json = {**conn.config_json, "scopes": tokens.get("scope", "").split()}
        conn.last_validated_at = datetime.now(timezone.utc)

    db.commit()
    logger.info("Connected %s for %s", channel, email)

    return RedirectResponse("/control-room/brain/settings", status_code=303)


@brain_settings_router.post("/settings/disconnect/{channel}")
def disconnect_channel(channel: str, db: Session = Depends(get_db)):
    """Disconnect a channel."""
    channel_map = {"gmail": ConnectionChannel.GMAIL, "calendar": ConnectionChannel.CALENDAR, "telegram": ConnectionChannel.TELEGRAM}
    channel_enum = channel_map.get(channel)
    if not channel_enum:
        return RedirectResponse("/control-room/brain/settings", status_code=303)

    conn = db.query(AppConnection).filter(AppConnection.channel == channel_enum).first()
    if conn:
        conn.status = ConnectionStatus.DISCONNECTED
        conn.credential_json = {}
        conn.connection_label = None
        db.commit()
        logger.info("Disconnected %s", channel)

    return RedirectResponse("/control-room/brain/settings", status_code=303)
