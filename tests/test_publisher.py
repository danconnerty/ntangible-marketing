from app.publishers.base import PostResult
from app.publishers.mock import MockPublisher


def test_mock_post_tweet_succeeds():
    pub = MockPublisher()
    result = pub.post_tweet("Hello world")
    assert result.success is True
    assert result.tweet_id is not None
    assert "mock" in result.tweet_url
    assert result.posted_at is not None


def test_mock_post_tweet_with_media():
    pub = MockPublisher()
    result = pub.post_tweet("With image", media="image.png")
    assert result.success is True


def test_mock_delete_tweet():
    pub = MockPublisher()
    result = pub.post_tweet("To delete")
    assert pub.delete_tweet(result.tweet_id) is True


def test_mock_tracks_posts():
    pub = MockPublisher()
    pub.post_tweet("First")
    pub.post_tweet("Second")
    assert len(pub.posted) == 2
    assert pub.posted[0]["text"] == "First"
    assert pub.posted[1]["text"] == "Second"


def test_post_result_fields():
    result = PostResult(
        success=True,
        tweet_id="123",
        tweet_url="https://x.com/test/status/123",
        posted_at="2026-04-06T12:00:00Z",
    )
    assert result.success is True
    assert result.tweet_id == "123"
