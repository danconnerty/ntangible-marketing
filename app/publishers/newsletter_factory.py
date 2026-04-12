from app.config import get_settings
from app.publishers.mailchimp_http import MailchimpNewsletterPublisher
from app.publishers.newsletter_base import BaseNewsletterPublisher
from app.publishers.newsletter_mock import MockNewsletterPublisher


def get_newsletter_publisher(*, runtime_config: dict | None = None) -> BaseNewsletterPublisher:
    publisher_type = (runtime_config or {}).get("provider_key") or get_settings().newsletter_publisher.lower()
    if publisher_type == "mock":
        return MockNewsletterPublisher()
    if publisher_type == "mailchimp":
        return MailchimpNewsletterPublisher(runtime_config=runtime_config)
    raise ValueError(f"Unknown newsletter publisher: {publisher_type}. Use mock or mailchimp.")
