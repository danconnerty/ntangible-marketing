from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.publishers.newsletter_base import BaseNewsletterPublisher, NewsletterPublishResult


class MailchimpNewsletterPublisher(BaseNewsletterPublisher):
    def __init__(self, *, runtime_config: dict | None = None) -> None:
        settings = get_settings()
        runtime_config = runtime_config or {}
        self.api_key = runtime_config.get("api_key") or settings.mailchimp_api_key
        self.server_prefix = runtime_config.get("server_prefix") or settings.mailchimp_server_prefix
        self.default_from_name = runtime_config.get("default_from_name") or settings.newsletter_default_from_name
        self.reply_to_email = runtime_config.get("reply_to_email") or settings.newsletter_reply_to_email
        self.segment_list_ids = {
            "coaches_front_offices": runtime_config.get("coaches_list_id") or settings.newsletter_coaches_list_id,
            "partners_event_directors": runtime_config.get("partners_list_id") or settings.newsletter_partners_list_id,
        }
        self.client = httpx.Client(
            base_url=f"https://{self.server_prefix}.api.mailchimp.com/3.0" if self.server_prefix else "",
            auth=("anystring", self.api_key or ""),
            timeout=20.0,
        )

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
        if not self.api_key or not self.server_prefix:
            return NewsletterPublishResult(success=False, error="Missing Mailchimp API configuration")

        list_id = self.segment_list_ids.get(segment)
        if not list_id:
            return NewsletterPublishResult(success=False, error=f"Missing Mailchimp audience id for segment '{segment}'")
        if not self.reply_to_email:
            return NewsletterPublishResult(success=False, error="Missing newsletter reply-to email")

        title = f"{segment}-{subject[:40]}".replace(" ", "-").lower()
        try:
            create_response = self.client.post(
                "/campaigns",
                json={
                    "type": "regular",
                    "recipients": {"list_id": list_id},
                    "settings": {
                        "subject_line": subject,
                        "preview_text": preview_text,
                        "title": title,
                        "from_name": self.default_from_name,
                        "reply_to": self.reply_to_email,
                    },
                },
            )
            create_response.raise_for_status()
            campaign = create_response.json()
            campaign_id = campaign["id"]

            content_response = self.client.put(
                f"/campaigns/{campaign_id}/content",
                json={
                    "html": body_html or body_markdown.replace("\n", "<br>\n"),
                    "plain_text": body_markdown,
                },
            )
            content_response.raise_for_status()

            send_response = self.client.post(f"/campaigns/{campaign_id}/actions/send")
            send_response.raise_for_status()

            archive_url = campaign.get("archive_url")
            return NewsletterPublishResult(
                success=True,
                campaign_id=campaign_id,
                archive_url=archive_url,
                sent_at=datetime.now(timezone.utc).isoformat(),
                scheduled_at=scheduled_at,
            )
        except httpx.HTTPError as exc:
            return NewsletterPublishResult(success=False, error=str(exc))
