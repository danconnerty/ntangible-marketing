from app.config import get_settings
from app.publishers.base import BasePublisher


def get_publisher() -> BasePublisher:
    publisher_type = get_settings().x_publisher.lower()

    if publisher_type == "mock":
        from app.publishers.mock import MockPublisher

        return MockPublisher()
    if publisher_type == "tweepy":
        from app.publishers.tweepy_pub import TweepyPublisher

        return TweepyPublisher()
    if publisher_type == "twikit":
        from app.publishers.twikit_pub import TwikitPublisher

        return TwikitPublisher()
    raise ValueError(f"Unknown publisher: {publisher_type}. Use mock, tweepy, or twikit.")
