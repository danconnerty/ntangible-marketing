from app.config import get_settings
from app.publishers.base import BasePublisher, PostResult
from app.publishers.linkedin_factory import get_linkedin_publisher
from app.publishers.newsletter_factory import get_newsletter_publisher


class LinkedInPublisherAdapter(BasePublisher):
    def __init__(self, publisher) -> None:
        self.publisher = publisher

    def publish(self, text: str, media: str | None = None, metadata: dict | None = None) -> PostResult:
        result = self.publisher.publish_post(text)
        return PostResult(
            success=result.success,
            platform_post_id=result.post_id,
            post_url=result.post_url,
            posted_at=result.posted_at,
            error=result.error,
        )

    def delete(self, post_id: str) -> bool:
        return False


class NewsletterPublisherAdapter(BasePublisher):
    def __init__(self, publisher) -> None:
        self.publisher = publisher

    def publish(self, text: str, media: str | None = None, metadata: dict | None = None) -> PostResult:
        payload = metadata or {}
        result = self.publisher.send_campaign(
            subject=payload["subject"],
            preview_text=payload.get("preview_text", ""),
            body_markdown=text,
            body_html=payload.get("body_html"),
            segment=payload["segment"],
            scheduled_at=payload.get("scheduled_at"),
        )
        return PostResult(
            success=result.success,
            platform_post_id=result.campaign_id,
            post_url=result.archive_url,
            posted_at=result.sent_at,
            error=result.error,
        )

    def delete(self, post_id: str) -> bool:
        return False


def _build_with_optional_runtime(factory, runtime_config: dict | None):
    if runtime_config:
        try:
            return factory(runtime_config=runtime_config)
        except TypeError:
            return factory()
    return factory()


def get_publisher(platform: str = "x", *, runtime_config: dict | None = None) -> BasePublisher:
    if platform == "linkedin":
        return LinkedInPublisherAdapter(_build_with_optional_runtime(get_linkedin_publisher, runtime_config))
    if platform == "newsletter":
        return NewsletterPublisherAdapter(_build_with_optional_runtime(get_newsletter_publisher, runtime_config))

    runtime_config = runtime_config or {}
    publisher_type = (
        runtime_config.get("provider_key")
        or runtime_config.get("publisher_type")
        or get_settings().x_publisher.lower()
    )

    if publisher_type == "mock":
        from app.publishers.mock import MockPublisher

        return MockPublisher()
    if publisher_type == "tweepy":
        from app.publishers.tweepy_pub import TweepyPublisher

        return _build_with_optional_runtime(TweepyPublisher, runtime_config)
    if publisher_type == "twikit":
        from app.publishers.twikit_pub import TwikitPublisher

        return _build_with_optional_runtime(TwikitPublisher, runtime_config)
    raise ValueError(f"Unknown publisher: {publisher_type}. Use mock, tweepy, or twikit.")
