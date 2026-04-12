import uuid
from datetime import datetime, timezone

from app.publishers.instagram_base import BaseInstagramPublisher, InstagramPublishResult


class MockInstagramPublisher(BaseInstagramPublisher):
    def __init__(self):
        self.posted: list[dict] = []

    def publish_post(self, caption: str, asset_urls: list[str], publish_mode: str = "feed") -> InstagramPublishResult:
        post_id = f"ig-{uuid.uuid4().hex[:16]}"
        posted_at = datetime.now(timezone.utc).isoformat()
        self.posted.append(
            {
                "caption": caption,
                "asset_urls": asset_urls,
                "publish_mode": publish_mode,
                "post_id": post_id,
            }
        )
        return InstagramPublishResult(
            success=True,
            post_id=post_id,
            post_url=f"https://www.instagram.com/p/{post_id}/",
            posted_at=posted_at,
        )
