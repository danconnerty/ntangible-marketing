import uuid
from datetime import datetime, timezone

from app.publishers.newsletter_base import BaseNewsletterPublisher, NewsletterPublishResult


class MockNewsletterPublisher(BaseNewsletterPublisher):
    def __init__(self) -> None:
        self.sent: list[dict] = []

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
        campaign_id = f"cmp-{uuid.uuid4().hex[:10]}"
        sent_at = datetime.now(timezone.utc).isoformat()
        self.sent.append(
            {
                "subject": subject,
                "preview_text": preview_text,
                "body_markdown": body_markdown,
                "body_html": body_html,
                "segment": segment,
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
                "campaign_id": campaign_id,
            }
        )
        return NewsletterPublishResult(
            success=True,
            campaign_id=campaign_id,
            archive_url=f"https://mailchi.mp/mock/{campaign_id}",
            sent_at=sent_at,
            scheduled_at=scheduled_at,
        )
