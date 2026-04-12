import uuid
from datetime import datetime, timezone

from app.publishers.linkedin_base import BaseLinkedInPublisher, LinkedInPublishResult


class MockLinkedInPublisher(BaseLinkedInPublisher):
    def __init__(self):
        self.posted: list[dict] = []

    def publish_post(self, text: str) -> LinkedInPublishResult:
        post_id = f"urn:li:share:{uuid.uuid4().int % 10**12}"
        posted_at = datetime.now(timezone.utc).isoformat()
        self.posted.append({"text": text, "post_id": post_id})
        return LinkedInPublishResult(
            success=True,
            post_id=post_id,
            post_url=f"https://www.linkedin.com/feed/update/{post_id}",
            posted_at=posted_at,
        )
