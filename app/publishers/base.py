from dataclasses import dataclass


@dataclass
class PostResult:
    success: bool
    tweet_id: str | None = None
    tweet_url: str | None = None
    posted_at: str | None = None
    error: str | None = None


class BasePublisher:
    def post_tweet(self, text: str, media: str | None = None) -> PostResult:
        raise NotImplementedError

    def delete_tweet(self, tweet_id: str) -> bool:
        raise NotImplementedError
