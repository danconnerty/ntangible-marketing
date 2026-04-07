import asyncio
import concurrent.futures
import logging
from datetime import datetime, timezone

from twikit import Client

from app.config import get_settings
from app.publishers.base import BasePublisher, PostResult


logger = logging.getLogger(__name__)


class TwikitPublisher(BasePublisher):
    """Dev/test only; Twikit uses session cookies and is not production-safe."""

    def __init__(self):
        settings = get_settings()
        self.client = Client("en-US")
        self._username = settings.x_twikit_username
        self._password = settings.x_twikit_password
        self._email = settings.x_twikit_email
        self._logged_in = False

    async def _ensure_login(self) -> None:
        if not self._logged_in:
            await self.client.login(
                auth_info_1=self._username,
                auth_info_2=self._email,
                password=self._password,
            )
            self._logged_in = True

    def post_tweet(self, text: str, media: str | None = None) -> PostResult:
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
                tweet_id=tweet_id,
                tweet_url=f"https://x.com/i/status/{tweet_id}",
                posted_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:  # pragma: no cover - defensive API boundary
            logger.error("Twikit publish failed: %s", exc)
            return PostResult(success=False, error=f"unknown: {exc}")

    def delete_tweet(self, tweet_id: str) -> bool:
        async def _delete():
            await self._ensure_login()
            await self.client.delete_tweet(tweet_id)

        try:
            asyncio.run(_delete())
            return True
        except Exception as exc:  # pragma: no cover - defensive API boundary
            logger.error("Twikit delete failed: %s", exc)
            return False
