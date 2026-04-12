from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.publishers.instagram_base import BaseInstagramPublisher, InstagramPublishResult


class HttpInstagramPublisher(BaseInstagramPublisher):
    def __init__(self, *, runtime_config: dict | None = None):
        settings = get_settings()
        runtime_config = runtime_config or {}
        self.business_account_id = runtime_config.get("business_account_id") or settings.instagram_business_account_id
        access_token = runtime_config.get("access_token") or settings.instagram_access_token
        graph_api_version = runtime_config.get("graph_api_version") or settings.instagram_graph_api_version
        self.client = httpx.Client(
            base_url=f"https://graph.facebook.com/{graph_api_version}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )

    def _create_media_container(self, payload: dict[str, str]) -> str:
        response = self.client.post(f"/{self.business_account_id}/media", data=payload)
        response.raise_for_status()
        return response.json()["id"]

    def publish_post(self, caption: str, asset_urls: list[str], publish_mode: str = "feed") -> InstagramPublishResult:
        if not self.business_account_id:
            return InstagramPublishResult(success=False, error="Missing Instagram business account id")
        if not asset_urls:
            return InstagramPublishResult(success=False, error="Instagram publish requires at least one asset URL")

        try:
            if publish_mode == "carousel" or len(asset_urls) > 1:
                child_ids = [
                    self._create_media_container({"image_url": url, "is_carousel_item": "true"})
                    for url in asset_urls
                ]
                creation_id = self._create_media_container(
                    {
                        "media_type": "CAROUSEL",
                        "children": ",".join(child_ids),
                        "caption": caption,
                    }
                )
            else:
                primary_url = asset_urls[0]
                payload = {"caption": caption}
                if publish_mode == "story":
                    payload["media_type"] = "STORIES"
                elif publish_mode == "reel" or primary_url.lower().endswith(".mp4"):
                    payload["media_type"] = "REELS"
                    payload["video_url"] = primary_url
                else:
                    payload["image_url"] = primary_url
                creation_id = self._create_media_container(payload)

            publish_response = self.client.post(
                f"/{self.business_account_id}/media_publish",
                data={"creation_id": creation_id},
            )
            publish_response.raise_for_status()
            post_id = publish_response.json()["id"]
            return InstagramPublishResult(
                success=True,
                post_id=post_id,
                post_url=f"https://www.instagram.com/p/{post_id}/",
                posted_at=datetime.now(timezone.utc).isoformat(),
            )
        except httpx.HTTPError as exc:
            return InstagramPublishResult(success=False, error=str(exc))
