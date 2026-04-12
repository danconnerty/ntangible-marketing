import asyncio
import concurrent.futures
import logging
from datetime import datetime, timezone

try:  # pragma: no cover - exercised indirectly in environments without twikit
    from twikit import Client
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    Client = None

from app.config import get_settings
from app.publishers.base import BasePublisher, PostResult


logger = logging.getLogger(__name__)


class TwikitPublisher(BasePublisher):
    """Dev/test only; Twikit uses session cookies and is not production-safe."""

    def __init__(self, *, runtime_config: dict | None = None):
        if Client is None:
            raise RuntimeError("twikit is not installed. Use mock publisher or install twikit.")
        settings = get_settings()
        runtime_config = runtime_config or {}
        self.client = Client("en-US")
        self._username = runtime_config.get("username") or settings.x_twikit_username
        self._password = runtime_config.get("password") or settings.x_twikit_password
        self._email = runtime_config.get("email") or settings.x_twikit_email
        self._logged_in = False

    async def _ensure_login(self) -> None:
        if not self._logged_in:
            await self.client.login(
                auth_info_1=self._username,
                auth_info_2=self._email,
                password=self._password,
            )
            self._logged_in = True

    def publish(self, text: str, media: str | None = None, metadata: dict | None = None) -> PostResult:
        async def _post():
            await self._ensure_login()
            return await self.client.create_tweet(text=text)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    tweet = pool.submit(asyncio.run, _post()).result()
            else:
                tweet = asyncio.run(_post())

            tweet_id = str(tweet.id)
            return PostResult(
                success=True,
                platform_post_id=tweet_id,
                post_url=f"https://x.com/i/status/{tweet_id}",
                posted_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:  # pragma: no cover - defensive API boundary
            logger.error("Twikit publish failed: %s", exc)
            return PostResult(success=False, error=f"unknown: {exc}")

    def delete(self, post_id: str) -> bool:
        async def _delete():
            await self._ensure_login()
            await self.client.delete_tweet(post_id)

        try:
            asyncio.run(_delete())
            return True
        except Exception as exc:  # pragma: no cover - defensive API boundary
            logger.error("Twikit delete failed: %s", exc)
            return False
