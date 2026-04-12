from app.publishers.newsletter_base import NewsletterPublishResult
from app.publishers.newsletter_mock import MockNewsletterPublisher


def test_mock_newsletter_publisher_tracks_campaigns():
    publisher = MockNewsletterPublisher()

    result = publisher.send_campaign(
        subject="April pressure data",
        preview_text="What changed this month.",
        body_markdown="Body",
        body_html=None,
        segment="coaches_front_offices",
    )

    assert result.success is True
    assert result.campaign_id is not None
    assert publisher.sent[0]["subject"] == "April pressure data"


def test_newsletter_publish_result_fields():
    result = NewsletterPublishResult(
        success=True,
        campaign_id="cmp-123",
        archive_url="https://mailchi.mp/example/cmp-123",
        sent_at="2026-04-06T12:00:00+00:00",
    )

    assert result.success is True
    assert result.campaign_id == "cmp-123"
