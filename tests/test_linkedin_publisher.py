from app.publishers.linkedin_factory import get_linkedin_publisher
from app.publishers.linkedin_mock import MockLinkedInPublisher


def test_linkedin_factory_defaults_to_mock(monkeypatch):
    monkeypatch.setenv("LINKEDIN_PUBLISHER", "mock")
    publisher = get_linkedin_publisher()
    assert isinstance(publisher, MockLinkedInPublisher)


def test_mock_linkedin_publisher_tracks_posts():
    publisher = MockLinkedInPublisher()
    result = publisher.publish_post("Pressure data beats vibes.")
    assert result.success is True
    assert result.post_id is not None
    assert publisher.posted[0]["text"] == "Pressure data beats vibes."
