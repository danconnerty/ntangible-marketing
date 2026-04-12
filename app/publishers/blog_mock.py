import uuid
from datetime import datetime, timezone

from app.publishers.blog_base import BaseBlogPublisher, BlogPublishResult


class MockBlogPublisher(BaseBlogPublisher):
    def __init__(self) -> None:
        self.published: list[dict] = []

    def publish_article(
        self,
        *,
        title: str,
        slug: str,
        body_markdown: str,
        body_html: str,
        meta_description: str,
        target_keywords: list[str],
        headings: list[str],
        audience: str,
        topic: str,
        angle: str | None = None,
        excerpt: str | None = None,
        scheduled_at: datetime | None = None,
    ) -> BlogPublishResult:
        article_id = f"blog-{uuid.uuid4().hex[:12]}"
        url = f"https://blog.mock/{slug}"
        published_at = datetime.now(timezone.utc)
        self.published.append(
            {
                "title": title,
                "slug": slug,
                "body_markdown": body_markdown,
                "body_html": body_html,
                "meta_description": meta_description,
                "target_keywords": target_keywords,
                "headings": headings,
                "audience": audience,
                "topic": topic,
                "angle": angle,
                "excerpt": excerpt,
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
                "article_id": article_id,
                "url": url,
            }
        )
        return BlogPublishResult(
            success=True,
            article_id=article_id,
            url=url,
            published_at=published_at,
        )

