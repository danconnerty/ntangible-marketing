import pytest

from app.publishers import get_publisher
from app.publishers.mock import MockPublisher


def test_get_mock_publisher(monkeypatch):
    monkeypatch.setenv("X_PUBLISHER", "mock")
    pub = get_publisher()
    assert isinstance(pub, MockPublisher)


def test_get_publisher_default_is_mock(monkeypatch):
    monkeypatch.delenv("X_PUBLISHER", raising=False)
    pub = get_publisher()
    assert isinstance(pub, MockPublisher)


def test_get_tweepy_publisher(monkeypatch):
    from app.publishers import tweepy_pub

    class DummyPublisher:
        pass

    monkeypatch.setenv("X_PUBLISHER", "tweepy")
    monkeypatch.setattr(tweepy_pub, "TweepyPublisher", DummyPublisher)
    pub = get_publisher()
    assert isinstance(pub, DummyPublisher)


def test_get_twikit_publisher(monkeypatch):
    from app.publishers import twikit_pub

    class DummyPublisher:
        pass

    monkeypatch.setenv("X_PUBLISHER", "twikit")
    monkeypatch.setattr(twikit_pub, "TwikitPublisher", DummyPublisher)
    pub = get_publisher()
    assert isinstance(pub, DummyPublisher)


def test_get_publisher_invalid_raises(monkeypatch):
    monkeypatch.setenv("X_PUBLISHER", "invalid")
    with pytest.raises(ValueError, match="Unknown publisher"):
        get_publisher()
