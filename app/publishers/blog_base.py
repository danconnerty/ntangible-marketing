from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class BlogPublishResult:
    success: bool
    article_id: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    error: str | None = None


class BaseBlogPublisher:
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
        raise NotImplementedError

