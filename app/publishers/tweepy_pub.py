import logging
import time
from datetime import datetime, timezone

try:  # pragma: no cover - exercised indirectly in environments without tweepy
    import tweepy
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    tweepy = None

from app.config import get_settings
from app.publishers.base import BasePublisher, PostResult


logger = logging.getLogger(__name__)


class TweepyPublisher(BasePublisher):
    def __init__(self, *, runtime_config: dict | None = None):
        if tweepy is None:
            raise RuntimeError("tweepy is not installed. Use mock publisher or install tweepy.")
        settings = get_settings()
        runtime_config = runtime_config or {}
        self.client = tweepy.Client(
            consumer_key=runtime_config.get("api_key") or settings.x_api_key,
            consumer_secret=runtime_config.get("api_secret") or settings.x_api_secret,
            access_token=runtime_config.get("access_token") or settings.x_access_token,
            access_token_secret=runtime_config.get("access_token_secret") or settings.x_access_token_secret,
        )

    def publish(self, text: str, media: str | None = None, metadata: dict | None = None) -> PostResult:
        backoff_seconds = [30, 60, 120]

        for attempt in range(len(backoff_seconds) + 1):
            try:
                response = self.client.create_tweet(text=text)
                tweet_id = str(response.data["id"])
                return PostResult(
                    success=True,
                    platform_post_id=tweet_id,
                    post_url=f"https://x.com/i/status/{tweet_id}",
                    posted_at=datetime.now(timezone.utc).isoformat(),
                )
            except tweepy.TooManyRequests:
                if attempt < len(backoff_seconds):
                    wait_time = backoff_seconds[attempt]
                    logger.warning("Rate limited, retrying in %ss", wait_time)
                    time.sleep(wait_time)
                    continue
                return PostResult(success=False, error="Rate limited after max retries")
            except tweepy.Unauthorized:
                return PostResult(success=False, error="Authentication failed (401)")
            except tweepy.Forbidden:
                return PostResult(success=False, error="Forbidden (403)")
            except tweepy.BadRequest as exc:
                return PostResult(success=False, error=f"Bad request: {exc}")
            except Exception as exc:  # pragma: no cover - defensive API boundary
                logger.error("Ambiguous publish result: %s", exc)
                return PostResult(success=False, error=f"unknown: {exc}")

        return PostResult(success=False, error="Exhausted retries")

    def delete(self, post_id: str) -> bool:
        try:
            self.client.delete_tweet(post_id)
            return True
        except Exception as exc:  # pragma: no cover - defensive API boundary
            logger.error("Failed to delete tweet %s: %s", post_id, exc)
            return False
