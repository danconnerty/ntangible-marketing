import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text as sa_text

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
security = HTTPBearer(auto_error=False)


def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=403, detail="Not authenticated")
    if credentials.credentials != get_settings().api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials


from app.api.routes import router

app.include_router(router)
