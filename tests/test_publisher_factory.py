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


def test_get_linkedin_publisher_adapter(monkeypatch):
    from app.publishers import get_publisher as factory_get_publisher
    import app.publishers as publishers_module

    class DummyLinkedInPublisher:
        def publish_post(self, text: str):
            from app.publishers.linkedin_base import LinkedInPublishResult

            return LinkedInPublishResult(
                success=True,
                post_id="urn:li:share:123",
                post_url="https://www.linkedin.com/feed/update/urn:li:share:123",
                posted_at="2026-04-06T12:00:00+00:00",
            )

    monkeypatch.setattr(
        publishers_module,
        "get_linkedin_publisher",
        lambda: DummyLinkedInPublisher(),
    )
    publisher = factory_get_publisher(platform="linkedin")
    result = publisher.publish("hello linkedin")

    assert result.success is True
    assert result.platform_post_id == "urn:li:share:123"


def test_get_linkedin_publisher_adapter_passes_runtime_config(monkeypatch):
    from app.publishers import get_publisher as factory_get_publisher
    import app.publishers as publishers_module

    captured = {}

    class DummyLinkedInPublisher:
        def publish_post(self, text: str):
            from app.publishers.linkedin_base import LinkedInPublishResult

            return LinkedInPublishResult(
                success=True,
                post_id="urn:li:share:999",
                post_url="https://www.linkedin.com/feed/update/urn:li:share:999",
                posted_at="2026-04-09T12:00:00+00:00",
            )

    def fake_get_linkedin_publisher(*, runtime_config=None):
        captured["runtime_config"] = runtime_config
        return DummyLinkedInPublisher()

    monkeypatch.setattr(
        publishers_module,
        "get_linkedin_publisher",
        fake_get_linkedin_publisher,
    )
    publisher = factory_get_publisher(
        platform="linkedin",
        runtime_config={
            "provider_key": "linkedin",
            "access_token": "runtime-linkedin-token",
            "organization_urn": "urn:li:organization:999",
        },
    )
    result = publisher.publish("hello linkedin")

    assert result.success is True
    assert captured["runtime_config"]["organization_urn"] == "urn:li:organization:999"


def test_get_newsletter_publisher_adapter(monkeypatch):
    from app.publishers import get_publisher as factory_get_publisher
    import app.publishers as publishers_module

    class DummyNewsletterPublisher:
        def send_campaign(self, **kwargs):
            from app.publishers.newsletter_base import NewsletterPublishResult

            assert kwargs["subject"] == "April pressure data"
            assert kwargs["segment"] == "coaches_front_offices"
            return NewsletterPublishResult(
                success=True,
                campaign_id="cmp-123",
                archive_url="https://mailchi.mp/example/cmp-123",
                sent_at="2026-04-06T12:00:00+00:00",
            )

    monkeypatch.setattr(
        publishers_module,
        "get_newsletter_publisher",
        lambda: DummyNewsletterPublisher(),
    )
    publisher = factory_get_publisher(platform="newsletter")
    result = publisher.publish(
        "newsletter body",
        metadata={
            "subject": "April pressure data",
            "preview_text": "What changed in recruiting pressure.",
            "segment": "coaches_front_offices",
        },
    )

    assert result.success is True
    assert result.platform_post_id == "cmp-123"


def test_get_x_publisher_uses_runtime_provider_key(monkeypatch):
    from app.publishers import get_publisher as factory_get_publisher
    import app.publishers as publishers_module

    class DummyPublisher:
        def publish(self, text: str, media: str | None = None, metadata: dict | None = None):
            from app.publishers.base import PostResult

            return PostResult(
                success=True,
                platform_post_id="x-123",
                post_url="https://x.com/i/status/x-123",
                posted_at="2026-04-09T12:00:00+00:00",
            )

    monkeypatch.setattr(publishers_module, "MockPublisher", DummyPublisher, raising=False)
    monkeypatch.setattr(publishers_module.tweepy_pub, "TweepyPublisher", DummyPublisher)

    publisher = factory_get_publisher(
        platform="x",
        runtime_config={"provider_key": "tweepy"},
    )
    result = publisher.publish("hello x")

    assert result.success is True
    assert result.platform_post_id == "x-123"


def test_tweepy_publisher_missing_dependency_raises_clear_error(monkeypatch):
    from app.publishers.tweepy_pub import TweepyPublisher
    import app.publishers.tweepy_pub as tweepy_pub

    monkeypatch.setattr(tweepy_pub, "tweepy", None)
    with pytest.raises(RuntimeError, match="tweepy is not installed"):
        TweepyPublisher()


def test_twikit_publisher_missing_dependency_raises_clear_error(monkeypatch):
    from app.publishers.twikit_pub import TwikitPublisher
    import app.publishers.twikit_pub as twikit_pub

    monkeypatch.setattr(twikit_pub, "Client", None)
    with pytest.raises(RuntimeError, match="twikit is not installed"):
        TwikitPublisher()
