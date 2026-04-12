from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.content_brain.types import ParsedAsset, ParsedContentItem, ParsedMetricSnapshot


def _extract_int(text: str | None) -> int | None:
    match = re.search(r"(\d+)", text or "")
    return int(match.group(1)) if match else None


def _extract_assets(images: list[dict[str, Any]] | None) -> list[ParsedAsset]:
    assets: list[ParsedAsset] = []
    seen: set[str] = set()
    for image in images or []:
        url = str(image.get("src") or "").strip()
        alt = str(image.get("alt") or "").strip()
        lowered_url = url.lower()
        lowered_alt = alt.lower()
        if not url or url in seen:
            continue
        if "static.licdn.com" in lowered_url:
            continue
        if "company-logo" in lowered_url:
            continue
        if lowered_alt in {"like", "love", "celebrate", "insightful", "support", "funny"}:
            continue
        seen.add(url)
        assets.append(
            ParsedAsset(
                asset_type="image",
                url=url,
                metadata={"alt": alt} if alt else {},
            )
        )
    return assets


def build_linkedin_authenticated_post_items(
    payload: dict[str, Any],
    *,
    observed_at: datetime,
) -> list[ParsedContentItem]:
    items: list[ParsedContentItem] = []

    for post in payload.get("posts", []):
        lines = [line.strip() for line in str(post.get("text") or "").splitlines() if line.strip()]
        if not lines:
            continue

        if "NTangible reposted this" in lines[:6]:
            item_type = "repost"
            author = None
            for line in lines[2:8]:
                if line not in {"NTangible", "NTangible reposted this", "160 followers", "2nd", "1st"} and not line.startswith("•"):
                    author = line
                    break
            metadata: dict[str, Any] = {"reposted_by": "NTangible"}
        else:
            item_type = "social_post"
            author = "NTangible"
            metadata = {}

        try:
            visibility_idx = next(i for i, line in enumerate(lines) if "Visible to" in line)
        except StopIteration:
            visibility_idx = 0

        relative_label = lines[visibility_idx - 1] if visibility_idx > 0 else None
        metadata["relative_published_label"] = relative_label
        metadata["visibility_label"] = lines[visibility_idx] if visibility_idx < len(lines) else None
        metadata["activity_urn"] = post.get("activity_urn")
        metadata["position"] = post.get("position")
        metadata["links"] = [link for link in post.get("links", []) if link.get("href")]

        hashtags: list[str] = []
        body_lines: list[str] = []
        idx = visibility_idx + 1 if visibility_idx else 1
        stop_prefixes = (
            "Activate to view larger image",
            "Loaded:",
            "Remaining time",
            "Playback speed",
            "Turn closed captions",
            "Unmute",
            "Turn fullscreen",
            "Close modal window",
            "Like",
            "Comment",
            "Repost",
            "Send",
            "Play",
        )
        while idx < len(lines):
            line = lines[idx]
            if line == "Follow":
                idx += 1
                continue
            if line == "…more":
                break
            if line == "hashtag":
                if idx + 1 < len(lines) and lines[idx + 1].startswith("#"):
                    hashtags.append(lines[idx + 1])
                    idx += 2
                    continue
            if any(line.startswith(prefix) for prefix in stop_prefixes):
                break
            if re.fullmatch(r"\d+", line):
                break
            if re.fullmatch(r"\d+ comments?", line) or re.fullmatch(r"\d+ reposts?", line):
                break
            if " and " in line and " others" in line:
                break
            body_lines.append(line)
            idx += 1

        if hashtags:
            metadata["hashtags"] = hashtags

        metric_payload: dict[str, int] = {}
        for button in post.get("buttons", []):
            text = str(button.get("text") or "")
            aria = str(button.get("aria") or "")
            lowered_aria = aria.lower()
            if "comment" in lowered_aria and "comments" not in metric_payload:
                comments = _extract_int(aria) or _extract_int(text)
                if comments is not None:
                    metric_payload["comments"] = comments
            elif "repost" in lowered_aria and "reposts" not in metric_payload:
                reposts = _extract_int(aria) or _extract_int(text)
                if reposts is not None:
                    metric_payload["reposts"] = reposts
            elif ("reaction" in lowered_aria or "others" in lowered_aria) and "reactions" not in metric_payload:
                reactions = _extract_int(text) or _extract_int(aria)
                if reactions is not None:
                    metric_payload["reactions"] = reactions

        metrics = []
        if metric_payload:
            metrics.append(
                ParsedMetricSnapshot(
                    observed_at=observed_at,
                    payload=metric_payload,
                    source_url=f"https://www.linkedin.com/feed/update/{post['activity_urn']}/",
                )
            )

        body_text = "\n\n".join(body_lines).strip() or None
        title = (body_lines[0] if body_lines else str(post.get("activity_urn") or ""))[:240]
        summary = body_text[:400] if body_text else None
        activity_urn = str(post.get("activity_urn") or "")
        activity_id = activity_urn.split(":")[-1] if activity_urn else ""
        items.append(
            ParsedContentItem(
                canonical_key=f"linkedin:activity:{activity_id}",
                platform="linkedin",
                item_type=item_type,
                url=f"https://www.linkedin.com/feed/update/{activity_urn}/",
                title=title,
                author=author,
                body_text=body_text,
                summary=summary,
                external_id=activity_id or None,
                metadata=metadata,
                assets=_extract_assets(post.get("images")),
                metrics=metrics,
            )
        )

    return items
