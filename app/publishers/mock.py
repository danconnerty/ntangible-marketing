import uuid
from datetime import datetime, timezone

from app.publishers.base import BasePublisher, PostResult


class MockPublisher(BasePublisher):
    def __init__(self):
        self.posted: list[dict] = []
        self.deleted: list[str] = []

    def post_tweet(self, text: str, media: str | None = None) -> PostResult:
        tweet_id = str(uuid.uuid4())[:12]
        posted_at = datetime.now(timezone.utc).isoformat()
        self.posted.append({"text": text, "media": media, "tweet_id": tweet_id})
        return PostResult(
            success=True,
            tweet_id=tweet_id,
            tweet_url=f"https://x.com/mock/status/{tweet_id}",
            posted_at=posted_at,
        )

    def delete_tweet(self, tweet_id: str) -> bool:
        self.deleted.append(tweet_id)
        return True
