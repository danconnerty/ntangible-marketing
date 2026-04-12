from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin
from xml.etree import ElementTree

from app.content_brain.types import ParsedAsset, ParsedContentItem, ParsedMetricSnapshot


YOUTUBE_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _parse_instagram_alt_date(value: str | None) -> datetime | None:
    if not value:
        return None
    match = re.match(r"Photo by @[\w.]+ on ([A-Za-z]+ \d{2}, \d{4})\.", value.strip())
    if not match:
        return None
    return datetime.strptime(match.group(1), "%B %d, %Y").replace(tzinfo=UTC)


def _clean_text(value: str) -> str:
    collapsed = " ".join(unescape(value).split())
    return collapsed.strip()


def _extract_meta_content(meta: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = meta.get(key)
        if value:
            return value.strip()
    return None


def _flatten_json_ld(value: object) -> list[dict]:
    if isinstance(value, list):
        flattened: list[dict] = []
        for item in value:
            flattened.extend(_flatten_json_ld(item))
        return flattened
    if isinstance(value, dict):
        flattened = [value] if value.get("@type") else []
        graph = value.get("@graph")
        if graph is not None:
            flattened.extend(_flatten_json_ld(graph))
        return flattened
    return []


def _extract_json_ld_objects(html: str) -> list[dict]:
    objects: list[dict] = []
    pattern = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(?P<body>.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(html):
        raw = match.group("body").strip()
        if raw.startswith("<!--") and raw.endswith("-->"):
            raw = raw[4:-3].strip()
        try:
            payload = json.loads(unescape(raw))
        except json.JSONDecodeError:
            continue
        objects.extend(_flatten_json_ld(payload))
    return objects


def _json_ld_types(value: object) -> set[str]:
    if isinstance(value, list):
        return {str(item) for item in value}
    if value is None:
        return set()
    return {str(value)}


def _pick_structured_document(html: str) -> dict | None:
    for candidate in _extract_json_ld_objects(html):
        types = _json_ld_types(candidate.get("@type"))
        if {"SocialMediaPosting", "Article"} & types:
            return candidate
    return None


def _extract_author_name(value: object) -> str | None:
    if isinstance(value, dict):
        name = value.get("name")
        return _clean_text(str(name)) if name else None
    if isinstance(value, list):
        for item in value:
            author = _extract_author_name(item)
            if author:
                return author
        return None
    if value:
        return _clean_text(str(value))
    return None


def _extract_image_url(value: object) -> str | None:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        url = value.get("url")
        return str(url).strip() if url else None
    if isinstance(value, list):
        for item in value:
            image_url = _extract_image_url(item)
            if image_url:
                return image_url
    return None


def _extract_structured_metrics(structured: dict, *, source_url: str) -> list[ParsedMetricSnapshot]:
    payload: dict[str, int] = {}
    interaction_stats = structured.get("interactionStatistic")
    if isinstance(interaction_stats, dict):
        interaction_stats = [interaction_stats]
    if isinstance(interaction_stats, list):
        for entry in interaction_stats:
            if not isinstance(entry, dict):
                continue
            interaction_type = str(entry.get("interactionType", ""))
            count = entry.get("userInteractionCount")
            if count is None:
                continue
            if "LikeAction" in interaction_type:
                payload["likes"] = int(count)
            elif "CommentAction" in interaction_type:
                payload["comments"] = int(count)
            elif "ShareAction" in interaction_type:
                payload["shares"] = int(count)

    if structured.get("commentCount") is not None and "comments" not in payload:
        payload["comments"] = int(structured["commentCount"])

    observed_at = _parse_datetime(structured.get("datePublished")) or datetime.now(UTC)
    return [ParsedMetricSnapshot(observed_at=observed_at, payload=payload, source_url=source_url)] if payload else []


def _infer_platform_from_url(url: str) -> str:
    lowered = url.lower()
    if "linkedin.com" in lowered:
        return "linkedin"
    if "instagram.com" in lowered:
        return "instagram"
    if "youtube.com" in lowered or "youtu.be" in lowered:
        return "youtube"
    return "web"


def _extract_linkedin_company_metrics(html: str, *, source_url: str) -> list[ParsedMetricSnapshot]:
    payload: dict[str, int] = {}
    followers = re.search(r"([\d,]+)\s+followers\b", html, re.IGNORECASE)
    employees = re.search(r"([\d,]+)\s+associated members\b", html, re.IGNORECASE)
    if followers:
        payload["followers"] = int(followers.group(1).replace(",", ""))
    if employees:
        payload["associated_members"] = int(employees.group(1).replace(",", ""))
    return [ParsedMetricSnapshot(observed_at=datetime.now(UTC), payload=payload, source_url=source_url)] if payload else []


def _parse_instagram_description_date(value: str | None) -> datetime | None:
    if not value:
        return None
    match = re.search(r" on ([A-Za-z]+ \d{1,2}, \d{4})[:.]", value)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%B %d, %Y").replace(tzinfo=UTC)


def _extract_instagram_caption(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r'Instagram:\s*"(?P<caption>.*)"', value)
    if match:
        return _clean_text(match.group("caption"))
    match = re.search(r':\s*"(?P<caption>.*)"', value)
    if match:
        return _clean_text(match.group("caption"))
    return None


def _extract_instagram_post_metrics(description: str | None, *, source_url: str) -> list[ParsedMetricSnapshot]:
    if not description:
        return []
    payload: dict[str, int] = {}
    for label in ("likes", "comments", "views"):
        match = re.search(rf"\b([\d,]+)\s+{label}\b", description, re.IGNORECASE)
        if match:
            payload[label] = int(match.group(1).replace(",", ""))
    observed_at = _parse_instagram_description_date(description) or datetime.now(UTC)
    return [ParsedMetricSnapshot(observed_at=observed_at, payload=payload, source_url=source_url)] if payload else []


class _DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._title_active = False
        self.title = ""
        self.meta: dict[str, str] = {}
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value for key, value in attrs if value is not None}
        lowered = tag.lower()

        if lowered in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return

        if lowered == "title":
            self._title_active = True
            return

        if lowered == "meta":
            name = attr_map.get("name") or attr_map.get("property")
            content = attr_map.get("content")
            if name and content:
                self.meta[name.lower()] = content.strip()

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if lowered == "title":
            self._title_active = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        cleaned = _clean_text(data)
        if not cleaned:
            return
        if self._title_active:
            self.title = cleaned
            return
        self.text_parts.append(cleaned)


def parse_youtube_feed(feed_xml: str, source_url: str) -> list[ParsedContentItem]:
    root = ElementTree.fromstring(feed_xml)
    items: list[ParsedContentItem] = []

    for entry in root.findall("atom:entry", YOUTUBE_NS):
        video_id = entry.findtext("yt:videoId", default="", namespaces=YOUTUBE_NS).strip()
        title = entry.findtext("atom:title", default="", namespaces=YOUTUBE_NS).strip() or None
        link = entry.find("atom:link", YOUTUBE_NS)
        link_url = link.get("href", "").strip() if link is not None else ""
        author = entry.findtext("atom:author/atom:name", default="", namespaces=YOUTUBE_NS).strip() or None
        published_at = _parse_datetime(
            entry.findtext("atom:published", default=None, namespaces=YOUTUBE_NS)
        )
        description = entry.findtext(
            "media:group/media:description",
            default="",
            namespaces=YOUTUBE_NS,
        ).strip() or None
        thumbnail = entry.find("media:group/media:thumbnail", YOUTUBE_NS)
        statistics = entry.find("media:group/media:community/media:statistics", YOUTUBE_NS)
        rating = entry.find("media:group/media:community/media:starRating", YOUTUBE_NS)

        assets: list[ParsedAsset] = []
        if thumbnail is not None and thumbnail.get("url"):
            assets.append(
                ParsedAsset(
                    asset_type="thumbnail",
                    url=thumbnail.get("url", "").strip(),
                )
            )

        metrics: list[ParsedMetricSnapshot] = []
        if statistics is not None or rating is not None:
            payload: dict[str, int | float] = {}
            if statistics is not None and statistics.get("views"):
                payload["views"] = int(statistics.get("views", "0"))
            if rating is not None and rating.get("count"):
                payload["rating_count"] = int(rating.get("count", "0"))
            if rating is not None and rating.get("average"):
                payload["rating_average"] = float(rating.get("average", "0"))
            metrics.append(
                ParsedMetricSnapshot(
                    observed_at=published_at or datetime.now(UTC),
                    payload=payload,
                    source_url=source_url,
                )
            )

        items.append(
            ParsedContentItem(
                canonical_key=f"youtube:video:{video_id}",
                platform="youtube",
                item_type="video",
                url=link_url,
                title=title,
                author=author,
                published_at=published_at,
                body_text=description,
                summary=description,
                external_id=video_id or None,
                metadata={"source_url": source_url},
                assets=assets,
                metrics=metrics,
            )
        )

    return items


def parse_generic_document(html: str, url: str, source_slug: str) -> list[ParsedContentItem]:
    parser = _DocumentParser()
    parser.feed(html)
    structured = _pick_structured_document(html)

    structured_title = None
    structured_author = None
    structured_published_at = None
    structured_body = None
    structured_metrics: list[ParsedMetricSnapshot] = []
    structured_type = None
    structured_image = None

    if structured:
        structured_title = structured.get("name") or structured.get("headline")
        structured_author = _extract_author_name(structured.get("author"))
        structured_published_at = _parse_datetime(structured.get("datePublished"))
        structured_body = structured.get("articleBody") or structured.get("text")
        structured_metrics = _extract_structured_metrics(structured, source_url=url)
        types = _json_ld_types(structured.get("@type"))
        if "SocialMediaPosting" in types:
            structured_type = "social_post"
        elif "Article" in types:
            structured_type = "article"
        structured_image = _extract_image_url(structured.get("image"))

    title = structured_title or parser.meta.get("og:title") or parser.title or None
    summary = _extract_meta_content(parser.meta, "description", "og:description")
    author = structured_author or parser.meta.get("author") or parser.meta.get("article:author")
    published_at = structured_published_at or _parse_datetime(
        _extract_meta_content(parser.meta, "article:published_time", "og:published_time")
    )
    body_text = _clean_text(str(structured_body)) if structured_body else _clean_text(" ".join(parser.text_parts))
    platform = _infer_platform_from_url(url)

    assets: list[ParsedAsset] = []
    image_url = _extract_meta_content(parser.meta, "og:image") or structured_image
    if image_url:
        assets.append(
            ParsedAsset(
                asset_type="image",
                url=image_url,
            )
        )

    metrics = structured_metrics
    if not metrics and platform == "linkedin" and not structured:
        metrics = _extract_linkedin_company_metrics(html, source_url=url)

    return [
        ParsedContentItem(
            canonical_key=f"web:page:{url}",
            platform=platform,
            item_type=structured_type or "page",
            url=url,
            title=title,
            author=author,
            published_at=published_at,
            body_text=body_text or None,
            summary=summary,
            metadata={"source_slug": source_slug, "schema_type": structured.get("@type") if structured else None},
            assets=assets,
            metrics=metrics,
        )
    ]


def parse_sitemap_xml(xml_text: str, source_url: str, source_slug: str) -> list[ParsedContentItem]:
    root = ElementTree.fromstring(xml_text)
    items: list[ParsedContentItem] = []

    for url_node in root.findall("sm:url", SITEMAP_NS):
        loc = url_node.findtext("sm:loc", default="", namespaces=SITEMAP_NS).strip()
        lastmod = _parse_datetime(
            url_node.findtext("sm:lastmod", default=None, namespaces=SITEMAP_NS)
        )
        if not loc:
            continue
        items.append(
            ParsedContentItem(
                canonical_key=f"sitemap:url:{loc}",
                platform="web",
                item_type="sitemap_entry",
                url=loc,
                published_at=lastmod,
                metadata={"source_slug": source_slug, "source_url": source_url},
            )
        )

    return items


def _decode_js_string(raw_value: str) -> str:
    return json.loads(f'"{raw_value}"')


def _looks_like_class_list(value: str) -> bool:
    tokens = value.split()
    if len(tokens) < 3:
        return False
    utility_like = 0
    for token in tokens:
        if any(marker in token for marker in ("-", ":", "/", "[", "]")):
            utility_like += 1
    return utility_like >= max(2, len(tokens) - 1)


def _should_keep_js_literal(value: str) -> bool:
    text = value.strip()
    if not text or len(text) < 4:
        return False
    if text.startswith("./") and text.endswith(".js"):
        return False
    if text == "noopener noreferrer":
        return False
    if re.fullmatch(r"M[\d\sA-Za-z.\-]+", text):
        return False
    if " " not in text and text.count("-") >= 3:
        return False
    if _looks_like_class_list(text):
        return False
    if text.startswith(("http://", "https://", "/")):
        return True
    if " " in text:
        return True
    if any(symbol in text for symbol in ("™", "’", ".", ",")):
        return True
    return False


def parse_js_text_chunk(js_text: str, url: str, source_slug: str) -> list[ParsedContentItem]:
    literals: list[str] = []
    seen: set[str] = set()

    for match in re.finditer(r'"([^"\\]*(?:\\.[^"\\]*)*)"', js_text):
        decoded = _decode_js_string(match.group(1)).strip()
        if not _should_keep_js_literal(decoded):
            continue
        if decoded in seen:
            continue
        seen.add(decoded)
        literals.append(decoded)

    assets: list[ParsedAsset] = []
    body_lines: list[str] = []
    for literal in literals:
        if literal.startswith(("http://", "https://", "/")) and any(
            marker in literal.lower() for marker in (".png", ".jpg", ".jpeg", ".webp", "content-type=image")
        ):
            assets.append(ParsedAsset(asset_type="image", url=urljoin(url, literal)))
            continue
        body_lines.append(literal)

    return [
        ParsedContentItem(
            canonical_key=f"bundle:chunk:{url}",
            platform="web",
            item_type="bundle_chunk",
            url=url,
            title=source_slug,
            body_text="\n".join(body_lines) or None,
            summary=body_lines[0] if body_lines else None,
            metadata={"source_slug": source_slug},
            assets=assets,
        )
    ]


def _extract_instagram_profile_counts(html: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for label in ("posts", "followers", "following"):
        match = re.search(rf">([\d,]+)</span>\s*(?:</span>\s*)+{label}\b", html, re.IGNORECASE)
        if match:
            counts[label] = int(match.group(1).replace(",", ""))
    return counts


def _extract_instagram_profile_handle(source_url: str) -> str:
    path = source_url.rstrip("/").split("/")
    return path[-1].lstrip("@")


def _extract_instagram_post_items(html: str, source_url: str, source_slug: str) -> list[ParsedContentItem]:
    items: list[ParsedContentItem] = []
    seen: set[str] = set()
    pattern = re.compile(
        r'href="(?P<href>/[^"]+/(?P<kind>p|reel)/(?P<shortcode>[A-Za-z0-9_-]+)/)"[^>]*>'
        r'.*?<img[^>]+alt="(?P<alt>[^"]*)"[^>]+src="(?P<src>[^"]+)"',
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(html):
        shortcode = match.group("shortcode")
        if shortcode in seen:
            continue
        seen.add(shortcode)

        href = unescape(match.group("href"))
        alt = _clean_text(unescape(match.group("alt")))
        src = unescape(match.group("src"))
        kind = match.group("kind").lower()

        items.append(
            ParsedContentItem(
                canonical_key=f"instagram:{'reel' if kind == 'reel' else 'post'}:{shortcode}",
                platform="instagram",
                item_type="reel" if kind == "reel" else "post",
                url=urljoin(source_url, href),
                title=(alt[:120] if alt else shortcode),
                published_at=_parse_instagram_alt_date(alt),
                body_text=alt or None,
                summary=(alt[:280] if alt else None),
                external_id=shortcode,
                metadata={
                    "source_slug": source_slug,
                    "relative_url": href,
                    "media_kind": "reel" if kind == "reel" else "post",
                },
                assets=[ParsedAsset(asset_type="image", url=src)],
            )
        )

    return items


def parse_instagram_profile_rendered(
    html: str,
    source_url: str,
    source_slug: str,
) -> list[ParsedContentItem]:
    parser = _DocumentParser()
    parser.feed(html)

    handle = _extract_instagram_profile_handle(source_url)
    counts = _extract_instagram_profile_counts(html)
    observed_at = datetime.now(UTC)

    profile_item = ParsedContentItem(
        canonical_key=f"instagram:profile:{handle}",
        platform="instagram",
        item_type="profile",
        url=source_url,
        title=f"@{handle}",
        summary=parser.meta.get("description") or None,
        body_text=_clean_text(" ".join(parser.text_parts)) or None,
        metadata={"source_slug": source_slug, "handle": handle},
        metrics=[
            ParsedMetricSnapshot(
                observed_at=observed_at,
                payload=counts,
                source_url=source_url,
            )
        ]
        if counts
        else [],
    )

    return [profile_item, *_extract_instagram_post_items(html, source_url, source_slug)]


def parse_instagram_post_document(
    html: str,
    source_url: str,
    source_slug: str,
) -> list[ParsedContentItem]:
    parser = _DocumentParser()
    parser.feed(html)

    path_parts = [part for part in source_url.rstrip("/").split("/") if part]
    handle = path_parts[-3] if len(path_parts) >= 3 else None
    kind = path_parts[-2] if len(path_parts) >= 2 else "p"
    shortcode = path_parts[-1] if path_parts else source_url.rstrip("/").split("/")[-1]
    description = _extract_meta_content(parser.meta, "description", "og:description")
    title_meta = _extract_meta_content(parser.meta, "og:title")
    caption = _extract_instagram_caption(title_meta) or _extract_instagram_caption(description)
    published_at = _parse_instagram_description_date(description)
    metrics = _extract_instagram_post_metrics(description, source_url=source_url)

    assets: list[ParsedAsset] = []
    image_url = _extract_meta_content(parser.meta, "og:image")
    if image_url:
        assets.append(ParsedAsset(asset_type="image", url=image_url))

    item_kind = "reel" if kind == "reel" else "post"

    return [
        ParsedContentItem(
            canonical_key=f"instagram:{item_kind}:{shortcode}",
            platform="instagram",
            item_type=item_kind,
            url=source_url,
            title=(caption[:120] if caption else shortcode),
            author=handle,
            published_at=published_at,
            body_text=caption or None,
            summary=description,
            external_id=shortcode,
            metadata={"source_slug": source_slug, "handle": handle, "media_kind": item_kind},
            assets=assets,
            metrics=metrics,
        )
    ]


def parse_payload(parser_name: str, payload: str, source_url: str, source_slug: str) -> list[ParsedContentItem]:
    if parser_name == "youtube_feed":
        return parse_youtube_feed(payload, source_url=source_url)
    if parser_name == "sitemap_xml":
        return parse_sitemap_xml(payload, source_url=source_url, source_slug=source_slug)
    if parser_name == "instagram_profile_rendered":
        return parse_instagram_profile_rendered(payload, source_url=source_url, source_slug=source_slug)
    if parser_name == "js_text_chunk":
        return parse_js_text_chunk(payload, url=source_url, source_slug=source_slug)
    if parser_name == "generic_document":
        return parse_generic_document(payload, url=source_url, source_slug=source_slug)
    raise ValueError(f"Unsupported parser: {parser_name}")
