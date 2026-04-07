from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings


app = FastAPI(title="NTangible Marketing Engine", version="0.1.0")
security = HTTPBearer()


def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    if credentials.credentials != get_settings().api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials
