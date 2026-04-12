from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.publishers.linkedin_base import BaseLinkedInPublisher, LinkedInPublishResult


class HttpLinkedInPublisher(BaseLinkedInPublisher):
    def __init__(self, *, runtime_config: dict | None = None):
        settings = get_settings()
        runtime_config = runtime_config or {}
        self.organization_urn = runtime_config.get("organization_urn") or settings.linkedin_organization_urn
        access_token = runtime_config.get("access_token") or settings.linkedin_access_token
        api_version = runtime_config.get("api_version") or settings.linkedin_api_version
        self.client = httpx.Client(
            base_url="https://api.linkedin.com",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Linkedin-Version": api_version,
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            },
            timeout=20.0,
        )

    def publish_post(self, text: str) -> LinkedInPublishResult:
        payload = {
            "author": self.organization_urn,
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        response = self.client.post("/rest/posts", json=payload)
        if response.is_success:
            post_id = response.headers.get("x-restli-id", "")
            return LinkedInPublishResult(
                success=True,
                post_id=post_id,
                post_url=f"https://www.linkedin.com/feed/update/{post_id}",
                posted_at=datetime.now(timezone.utc).isoformat(),
            )
        return LinkedInPublishResult(success=False, error=f"{response.status_code}: {response.text}")
