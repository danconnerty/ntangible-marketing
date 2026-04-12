from dataclasses import dataclass


@dataclass
class PostResult:
    success: bool
    platform_post_id: str | None = None
    post_url: str | None = None
    posted_at: str | None = None
    error: str | None = None

    # Backward-compatible aliases
    @property
    def tweet_id(self) -> str | None:
        return self.platform_post_id

    @property
    def tweet_url(self) -> str | None:
        return self.post_url


class BasePublisher:
    def publish(
        self,
        text: str,
        media: str | None = None,
        metadata: dict | None = None,
    ) -> PostResult:
        raise NotImplementedError

    def delete(self, post_id: str) -> bool:
        raise NotImplementedError

    # Backward-compatible aliases
    def post_tweet(self, text: str, media: str | None = None, metadata: dict | None = None) -> PostResult:
        return self.publish(text, media, metadata)

    def delete_tweet(self, tweet_id: str) -> bool:
        return self.delete(tweet_id)
