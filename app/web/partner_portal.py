import uuid
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.services.partner_delivery_service import PartnerDeliveryService
from app.services.partner_intake_service import PartnerIntakeService
from app.web.routes import templates


portal_router = APIRouter(tags=["partner-portal"])

PARTNER_PORTAL_COOKIE = "partner_portal_session"


def _portal_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        get_settings().control_room_session_secret,
        salt="partner-portal-session",
    )


def _build_portal_session(partner_slug: str) -> str:
    return _portal_serializer().dumps({"partner_slug": partner_slug})


def _read_portal_session(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        return _portal_serializer().loads(token, max_age=60 * 60 * 12)
    except BadSignature:
        return None


def authenticate_partner_portal_user(db: Session, username: str, password: str) -> dict | None:
    return PartnerIntakeService(db).authenticate_portal_user(username, password)


def submit_partner_portal_event(db: Session, partner_slug: str, payload: dict) -> dict:
    return PartnerIntakeService(db).ingest_portal(partner_slug, payload)


def list_partner_portal_packages(db: Session, partner_slug: str) -> list[dict]:
    return PartnerDeliveryService(db).list_bundles(partner_slug=partner_slug, limit=100)


def _require_partner_session(request: Request) -> dict:
    session = _read_portal_session(request.cookies.get(PARTNER_PORTAL_COOKIE))
    if session is None:
        raise HTTPException(status_code=401, detail="Partner portal login required")
    return session


@portal_router.get("/partner-portal/login")
def partner_portal_login(request: Request):
    return templates.TemplateResponse(
        request,
        "partner_portal_login.html",
        {"page": "partner-portal-login"},
    )


@portal_router.post("/partner-portal/login")
async def partner_portal_login_submit(request: Request, db: Session = Depends(get_db)):
    form_data = parse_qs((await request.body()).decode("utf-8"))
    username = form_data.get("username", [""])[0]
    password = form_data.get("password", [""])[0]
    partner = authenticate_partner_portal_user(db, username, password)
    if partner is None:
        raise HTTPException(status_code=401, detail="Invalid partner portal credentials")
    response = RedirectResponse("/partner-portal/submit", status_code=303)
    response.set_cookie(PARTNER_PORTAL_COOKIE, _build_portal_session(partner["slug"]), httponly=True, samesite="lax")
    return response


@portal_router.get("/partner-portal/submit")
def partner_portal_submit_page(request: Request):
    session = _read_portal_session(request.cookies.get(PARTNER_PORTAL_COOKIE))
    if session is None:
        return RedirectResponse("/partner-portal/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "partner_portal_submit.html",
        {"page": "partner-portal-submit", "partner_slug": session["partner_slug"]},
    )


@portal_router.post("/partner-portal/submit", response_class=HTMLResponse)
async def partner_portal_submit(
    request: Request,
    db: Session = Depends(get_db),
):
    session = _require_partner_session(request)
    form_data = parse_qs((await request.body()).decode("utf-8"))
    payload = {key: values[0] for key, values in form_data.items()}
    partner_slug = payload.pop("partner_slug", session["partner_slug"])
    result = submit_partner_portal_event(db, partner_slug, payload)
    db.commit()
    return templates.TemplateResponse(
        request,
        "partials/partner_event_result.html",
        {"result": result},
    )


@portal_router.get("/partner-portal/packages")
def partner_portal_packages(request: Request, db: Session = Depends(get_db)):
    session = _read_portal_session(request.cookies.get(PARTNER_PORTAL_COOKIE))
    if session is None:
        return RedirectResponse("/partner-portal/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "partner_portal_packages.html",
        {
            "page": "partner-portal-packages",
            "partner_slug": session["partner_slug"],
            "bundles": list_partner_portal_packages(db, session["partner_slug"]),
        },
    )
