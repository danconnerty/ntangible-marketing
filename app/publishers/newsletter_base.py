from dataclasses import dataclass
from datetime import datetime


@dataclass
class NewsletterPublishResult:
    success: bool
    campaign_id: str | None = None
    archive_url: str | None = None
    sent_at: str | None = None
    scheduled_at: datetime | None = None
    error: str | None = None


class BaseNewsletterPublisher:
    def send_campaign(
        self,
        *,
        subject: str,
        preview_text: str,
        body_markdown: str,
        body_html: str | None,
        segment: str,
        scheduled_at: datetime | None = None,
    ) -> NewsletterPublishResult:
        raise NotImplementedError
