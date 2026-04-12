import os

from app.publishers.blog_base import BaseBlogPublisher
from app.publishers.blog_http import HttpBlogPublisher
from app.publishers.blog_mock import MockBlogPublisher


def get_blog_publisher(*, runtime_config: dict | None = None) -> BaseBlogPublisher:
    publisher_type = (runtime_config or {}).get("provider_key") or os.getenv("BLOG_PUBLISHER", "mock").lower()
    if publisher_type == "mock":
        return MockBlogPublisher()
    if publisher_type == "http":
        return HttpBlogPublisher(runtime_config=runtime_config)
    if publisher_type == "blog":
        return HttpBlogPublisher(runtime_config=runtime_config)
    raise ValueError(f"Unknown blog publisher: {publisher_type}. Use mock or http.")
