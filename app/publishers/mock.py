import uuid
from datetime import datetime, timezone

from app.publishers.base import BasePublisher, PostResult


class MockPublisher(BasePublisher):
    def __init__(self):
        self.posted: list[dict] = []
        self.deleted: list[str] = []

    def publish(self, text: str, media: str | None = None, metadata: dict | None = None) -> PostResult:
        post_id = str(uuid.uuid4())[:12]
        posted_at = datetime.now(timezone.utc).isoformat()
        self.posted.append({"text": text, "media": media, "metadata": metadata or {}, "post_id": post_id})
        return PostResult(
            success=True,
            platform_post_id=post_id,
            post_url=f"https://x.com/mock/status/{post_id}",
            posted_at=posted_at,
        )

    def delete(self, post_id: str) -> bool:
        self.deleted.append(post_id)
        return True
