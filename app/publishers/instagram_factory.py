from app.config import get_settings
from app.publishers.instagram_base import BaseInstagramPublisher
from app.publishers.instagram_http import HttpInstagramPublisher
from app.publishers.instagram_mock import MockInstagramPublisher


def get_instagram_publisher(*, runtime_config: dict | None = None) -> BaseInstagramPublisher:
    publisher_type = (runtime_config or {}).get("provider_key") or get_settings().instagram_publisher.lower()
    if publisher_type == "mock":
        return MockInstagramPublisher()
    if publisher_type == "http":
        return HttpInstagramPublisher(runtime_config=runtime_config)
    if publisher_type in {"instagram", "instagram_graph"}:
        return HttpInstagramPublisher(runtime_config=runtime_config)
    raise ValueError(f"Unknown Instagram publisher: {publisher_type}. Use mock or http.")
