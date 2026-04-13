import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text as sa_text

from app.auth import (
    CONTROL_ROOM_LOGIN_PATH,
    control_room_auth_enabled,
    get_cognito_login_url,
    get_current_user,
)
from app.config import get_settings
from app.database import SessionLocal


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    db = SessionLocal()
    try:
        recovered = db.execute(
            sa_text(
                """
                UPDATE content_queue
                SET status = 'publishing_unknown',
                    failure_reason = 'Server crashed during publish — manually verify on X',
                    updated_at = now()
                WHERE status = 'publishing'
                RETURNING id
                """
            )
        ).fetchall()
        if recovered:
            logger.warning(
                "Recovered %s items from 'publishing' to 'publishing_unknown' on startup",
                len(recovered),
            )
        db.commit()
    except Exception as exc:  # pragma: no cover - startup should not kill local auth-only tests
        logger.warning("Startup recovery skipped: %s", exc)
        db.rollback()
    finally:
        db.close()
    yield


app = FastAPI(title="NTangible Marketing Engine", version="0.1.0", lifespan=lifespan)


@app.get("/")
async def root():
    return RedirectResponse("/control-room/brain/", status_code=303)


@app.middleware("http")
async def control_room_auth_middleware(request: Request, call_next):
    path = request.url.path
    if control_room_auth_enabled() and path.startswith("/control-room"):
        public_paths = {
            CONTROL_ROOM_LOGIN_PATH,
            f"{CONTROL_ROOM_LOGIN_PATH}/",
            "/control-room/auth/callback",
            "/control-room/logout",
        }
        if path not in public_paths:
            user = get_current_user(request)
            if user is None:
                return RedirectResponse(get_cognito_login_url(), status_code=303)
            request.state.user = user
    response = await call_next(request)
    if path.startswith(("/content", "/content-brain", "/linkedin", "/instagram", "/system")):
        response.headers["X-NTangible-Legacy-Endpoint"] = "true"
        response.headers["X-NTangible-Canonical-Path"] = "/control-room"
    return response

# Static files and web UI
from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# API routes
from app.api.routes import router
from app.api.instagram_routes import router as instagram_router
from app.api.linkedin_routes import router as linkedin_router
from app.api.control_room_routes import router as control_room_router
from app.api.history_routes import router as history_router
from app.api.trigger_routes import router as trigger_router
from app.api.workflow_routes import router as workflow_router
from app.api.analytics_routes import router as analytics_router
from app.api.campaign_routes import router as campaign_router
from app.api.competitor_routes import router as competitor_router
from app.api.lead_routes import router as lead_router
from app.api.partner_routes import router as partner_router
from app.api.revenue_routes import router as revenue_router
from app.api.science_routes import router as science_router, web_router as science_web_router
from app.api.blog_routes import router as blog_router, web_router as blog_web_router
from app.api.video_routes import router as video_router, web_router as video_web_router
from app.api.ugc_routes import router as ugc_router, web_router as ugc_web_router
from app.api.sports_routes import router as sports_router, web_router as sports_web_router
from app.api.repurposing_routes import router as repurposing_router, web_router as repurposing_web_router
from app.api.mcp_routes import router as mcp_router
from app.api.webhook_routes import router as webhook_router
from app.api.context_routes import router as context_router

app.include_router(router)
app.include_router(instagram_router)
app.include_router(linkedin_router)
app.include_router(control_room_router)
app.include_router(history_router)
app.include_router(trigger_router)
app.include_router(workflow_router)
app.include_router(analytics_router)
app.include_router(campaign_router)
app.include_router(competitor_router)
app.include_router(lead_router)
app.include_router(partner_router)
app.include_router(revenue_router)
app.include_router(science_router)
app.include_router(blog_router)
app.include_router(video_router)
app.include_router(ugc_router)
app.include_router(sports_router)
app.include_router(repurposing_router)
app.include_router(mcp_router)
app.include_router(webhook_router)
app.include_router(context_router)

# Web UI routes are optional in API-only environments.
try:
    from app.web.routes import web_router, public_router
    from app.web.partner_portal import portal_router
    from app.web.brain_settings import brain_settings_router
    from app.web.routes_studio import studio_router
except ImportError as exc:  # pragma: no cover - optional dependency in local test envs
    logger.warning("Web router skipped: %s", exc)
else:
    app.include_router(web_router)
    app.include_router(public_router)
    app.include_router(portal_router)
    app.include_router(science_web_router)
    app.include_router(blog_web_router)
    app.include_router(video_web_router)
    app.include_router(ugc_web_router)
    app.include_router(sports_web_router)
    app.include_router(repurposing_web_router)
    app.include_router(brain_settings_router)
    app.include_router(studio_router)
