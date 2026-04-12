import base64
import hashlib
import json
import logging
import os
import time
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings


logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)
CONTROL_ROOM_SESSION_COOKIE = "control_room_session"
CONTROL_ROOM_LOGIN_PATH = "/control-room/login"

_jwks_client: PyJWKClient | None = None

# In-memory session store (maps session_id -> tokens)
# In production with multiple workers, use Redis. For single-worker uvicorn this is fine.
_sessions: dict[str, dict] = {}


def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=403, detail="Not authenticated")
    if credentials.credentials != get_settings().api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials


def control_room_auth_enabled() -> bool:
    return bool(get_settings().control_room_require_auth)


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        settings = get_settings()
        region = settings.cognito_user_pool_id.split("_")[0]
        jwks_url = (
            f"https://cognito-idp.{region}.amazonaws.com"
            f"/{settings.cognito_user_pool_id}/.well-known/jwks.json"
        )
        _jwks_client = PyJWKClient(jwks_url)
    return _jwks_client


def get_cognito_login_url(state: str = "") -> str:
    settings = get_settings()
    params = {
        "client_id": settings.cognito_client_id,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": settings.cognito_redirect_uri,
    }
    if state:
        params["state"] = state
    return f"https://{settings.cognito_domain}/login?{urlencode(params)}"


def get_cognito_logout_url() -> str:
    settings = get_settings()
    base_url = settings.cognito_redirect_uri.rsplit("/auth/callback", 1)[0]
    params = {
        "client_id": settings.cognito_client_id,
        "logout_uri": base_url,
        "redirect_uri": base_url,
        "response_type": "code",
    }
    return f"https://{settings.cognito_domain}/logout?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    settings = get_settings()
    token_url = f"https://{settings.cognito_domain}/oauth2/token"
    credentials = f"{settings.cognito_client_id}:{settings.cognito_client_secret}"
    basic_auth = base64.b64encode(credentials.encode()).decode()

    response = httpx.post(
        token_url,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {basic_auth}",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.cognito_redirect_uri,
        },
        timeout=10,
    )
    if response.status_code != 200:
        logger.error("Token exchange failed: %s", response.text)
        raise HTTPException(status_code=401, detail="Authentication failed")
    return response.json()


def validate_cognito_token(id_token: str) -> dict | None:
    settings = get_settings()
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(id_token)
        region = settings.cognito_user_pool_id.split("_")[0]
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
            issuer=f"https://cognito-idp.{region}.amazonaws.com/{settings.cognito_user_pool_id}",
        )
        return claims
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as exc:
        logger.debug("Token validation failed: %s", exc)
        return None


def create_session(tokens: dict) -> str:
    """Store tokens server-side, return a short session ID for the cookie."""
    session_id = hashlib.sha256(os.urandom(32)).hexdigest()[:32]
    _sessions[session_id] = {
        "id_token": tokens["id_token"],
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "created_at": time.time(),
    }
    return session_id


def get_current_user(request: Request) -> dict | None:
    session_id = request.cookies.get(CONTROL_ROOM_SESSION_COOKIE)
    if not session_id or session_id not in _sessions:
        return None

    session = _sessions[session_id]
    claims = validate_cognito_token(session.get("id_token", ""))
    if claims:
        return {"email": claims.get("email", ""), "sub": claims.get("sub", "")}

    # Token expired — try refresh
    refresh_token = session.get("refresh_token")
    if not refresh_token:
        _sessions.pop(session_id, None)
        return None

    new_tokens = _refresh_tokens(refresh_token)
    if not new_tokens:
        _sessions.pop(session_id, None)
        return None

    # Update stored tokens
    session["id_token"] = new_tokens["id_token"]
    session["access_token"] = new_tokens["access_token"]

    claims = validate_cognito_token(new_tokens["id_token"])
    if claims:
        return {"email": claims.get("email", ""), "sub": claims.get("sub", "")}

    _sessions.pop(session_id, None)
    return None


def _refresh_tokens(refresh_token: str) -> dict | None:
    settings = get_settings()
    token_url = f"https://{settings.cognito_domain}/oauth2/token"
    credentials = f"{settings.cognito_client_id}:{settings.cognito_client_secret}"
    basic_auth = base64.b64encode(credentials.encode()).decode()

    response = httpx.post(
        token_url,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {basic_auth}",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=10,
    )
    if response.status_code != 200:
        return None
    return response.json()
