from dataclasses import dataclass


@dataclass
class LinkedInPublishResult:
    success: bool
    post_id: str | None = None
    post_url: str | None = None
    posted_at: str | None = None
    error: str | None = None


class BaseLinkedInPublisher:
    def publish_post(self, text: str) -> LinkedInPublishResult:
        raise NotImplementedError
