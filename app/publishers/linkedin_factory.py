from app.config import get_settings
from app.publishers.linkedin_base import BaseLinkedInPublisher
from app.publishers.linkedin_http import HttpLinkedInPublisher
from app.publishers.linkedin_mock import MockLinkedInPublisher


def get_linkedin_publisher(*, runtime_config: dict | None = None) -> BaseLinkedInPublisher:
    publisher_type = (runtime_config or {}).get("provider_key") or get_settings().linkedin_publisher.lower()
    if publisher_type == "mock":
        return MockLinkedInPublisher()
    if publisher_type == "http":
        return HttpLinkedInPublisher(runtime_config=runtime_config)
    if publisher_type == "linkedin":
        return HttpLinkedInPublisher(runtime_config=runtime_config)
    raise ValueError(f"Unknown LinkedIn publisher: {publisher_type}. Use mock or http.")
