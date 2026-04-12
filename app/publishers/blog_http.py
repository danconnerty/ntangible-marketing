from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx

from app.publishers.blog_base import BaseBlogPublisher, BlogPublishResult


class HttpBlogPublisher(BaseBlogPublisher):
    def __init__(self, *, runtime_config: dict | None = None) -> None:
        runtime_config = runtime_config or {}
        self.base_url = (runtime_config.get("base_url") or os.getenv("BLOG_CMS_BASE_URL", "")).rstrip("/")
        self.api_token = runtime_config.get("api_token") or os.getenv("BLOG_CMS_TOKEN", "")
        self.create_path = runtime_config.get("create_path") or os.getenv("BLOG_CMS_CREATE_PATH", "/api/articles")
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_token}"} if self.api_token else {},
            timeout=20.0,
        )

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
        if not self.base_url:
            return BlogPublishResult(success=False, error="Missing BLOG_CMS_BASE_URL")

        payload: dict[str, Any] = {
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
        }
        response = self.client.post(self.create_path, json=payload)
        if not response.is_success:
            return BlogPublishResult(success=False, error=f"{response.status_code}: {response.text}")

        data = response.json() if response.content else {}
        article_id = data.get("id") or response.headers.get("x-article-id")
        url = data.get("url") or data.get("canonical_url") or response.headers.get("location")
        return BlogPublishResult(
            success=True,
            article_id=article_id,
            url=url,
            published_at=datetime.now(timezone.utc),
        )
