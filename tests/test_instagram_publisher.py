from app.publishers.instagram_factory import get_instagram_publisher
from app.publishers.instagram_mock import MockInstagramPublisher


def test_instagram_factory_defaults_to_mock(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_PUBLISHER", "mock")
    publisher = get_instagram_publisher()
    assert isinstance(publisher, MockInstagramPublisher)


def test_mock_instagram_publisher_tracks_asset_urls():
    publisher = MockInstagramPublisher()
    result = publisher.publish_post(
        "Pressure is visible.\nMost programs still guess.\nComment if your staff wants cleaner signal.",
        ["https://cdn.example.com/slide-1.png", "https://cdn.example.com/slide-2.png"],
        publish_mode="carousel",
    )
    assert result.success is True
    assert result.post_id is not None
    assert publisher.posted[0]["publish_mode"] == "carousel"
    assert publisher.posted[0]["asset_urls"][0].endswith("slide-1.png")
