from dataclasses import dataclass


@dataclass
class InstagramPublishResult:
    success: bool
    post_id: str | None = None
    post_url: str | None = None
    posted_at: str | None = None
    error: str | None = None


class BaseInstagramPublisher:
    def publish_post(self, caption: str, asset_urls: list[str], publish_mode: str = "feed") -> InstagramPublishResult:
        raise NotImplementedError
