from datetime import UTC, datetime

from app.content_brain.parsers import (
    parse_generic_document,
    parse_instagram_post_document,
    parse_instagram_profile_rendered,
    parse_js_text_chunk,
    parse_youtube_feed,
)


YOUTUBE_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/">
  <title>NTangible</title>
  <entry>
    <id>yt:video:abc123</id>
    <yt:videoId>abc123</yt:videoId>
    <yt:channelId>channel-1</yt:channelId>
    <title>What is NTelligence?</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=abc123" />
    <author>
      <name>NTangible</name>
      <uri>https://www.youtube.com/channel/channel-1</uri>
    </author>
    <published>2026-02-01T12:00:00+00:00</published>
    <updated>2026-02-01T12:00:00+00:00</updated>
    <media:group>
      <media:title>What is NTelligence?</media:title>
      <media:thumbnail url="https://img.youtube.com/vi/abc123/hqdefault.jpg" />
      <media:description>Channel explainer</media:description>
      <media:community>
        <media:starRating count="1" average="5.00" min="1" max="5" />
        <media:statistics views="4" />
      </media:community>
    </media:group>
  </entry>
</feed>
"""

ARTICLE_HTML = """\
<!doctype html>
<html lang="en">
  <head>
    <title>Mind Over Matter</title>
    <meta name="description" content="How big-time athletes build unbreakable mental games." />
    <meta property="og:image" content="https://example.com/cover.jpg" />
    <meta property="article:published_time" content="2025-04-16T10:00:00+00:00" />
    <meta name="author" content="NTangible" />
  </head>
  <body>
    <article>
      <h1>Mind Over Matter</h1>
      <p>Elite athletes train their mind as deliberately as their body.</p>
      <p>This article explains how NTangible frames clutch performance.</p>
    </article>
  </body>
</html>
"""

ROUTE_CHUNK_JS = r"""\
const team=[{
  name:"Dan Connerty",
  role:"Founder and CEO",
  tagline:"Redefining how performance under pressure is measured.",
  image:"https://example.com/dan.jpg",
  bio:["Dan Connerty is a former professional baseball player.","He now leads NTangible."],
  cls:"text-xl md:text-3xl font-bold text-white"
},{
  title:"Research & Validation",
  link:"https://drive.google.com/file/d/abc/view?usp=sharing"
}];
"""

INSTAGRAM_RENDERED_HTML = """\
<!doctype html>
<html lang="en">
  <head>
    <title>(@ntangiblesports) • Instagram photos and videos</title>
    <meta
      name="description"
      content='908 Followers, 241 Following, 140 Posts - @ntangiblesports on Instagram: "NTangible™ - The Pressure Test
Official Mental Performance Partner of @rfkracing, @thealliancefastpitch"'
    />
  </head>
  <body>
    <main>
      <span class="outer"><span class="inner">140</span></span> posts
      <span class="outer" title="909"><span class="inner">909</span></span> followers
      <span class="outer"><span class="inner">239</span></span> following

      <a href="/ntangiblesports/p/DOJIVUqEXmr/" role="link" tabindex="0">
        <img
          alt="Photo by @ntangiblesports on September 03, 2025."
          src="https://instagram.example.com/photo.jpg"
        />
      </a>

      <a href="/ntangiblesports/reel/DVYwPJIk2n_/" role="link" tabindex="0">
        <img
          alt="ADs evaluate culture. They evaluate character. They evaluate who shows up when it matters. Jeff Curtis, Director of Athletics at Northwood University, knows what separates good programs from great ones."
          src="https://instagram.example.com/reel.jpg"
        />
      </a>
    </main>
  </body>
</html>
"""

LINKEDIN_POST_HTML = """\
<!doctype html>
<html lang="en">
  <head>
    <title>Absolutely huge announcements... | William Carroll</title>
    <meta
      name="description"
      content="Absolutely huge announcements coming after the holidays for NTangible."
    />
    <meta property="og:title" content="Absolutely huge announcements coming after the holidays for NTangible. | William Carroll" />
    <meta property="og:image" content="https://linkedin.example.com/post.jpg" />
  </head>
  <body>
    <script type="application/ld+json">
      {
        "@context": "http://schema.org",
        "@type": "SocialMediaPosting",
        "headline": "Absolutely huge announcements coming after the holidays for NTangible.",
        "datePublished": "2024-12-20T09:25:34.666Z",
        "commentCount": 2,
        "articleBody": "Absolutely huge announcements coming after the holidays for NTangible. I couldn't be more excited.",
        "author": {
          "@type": "Person",
          "name": "William Carroll"
        },
        "interactionStatistic": [
          {
            "@type": "InteractionCounter",
            "interactionType": "http://schema.org/LikeAction",
            "userInteractionCount": 43
          },
          {
            "@type": "InteractionCounter",
            "interactionType": "https://schema.org/CommentAction",
            "userInteractionCount": 2
          }
        ]
      }
    </script>
  </body>
</html>
"""

INSTAGRAM_POST_HTML = """\
<!doctype html>
<html lang="en">
  <head>
    <title>Instagram</title>
    <meta
      property="og:title"
      content='@ntangiblesports on Instagram: "Most athletes train the body. Few train the mind. Clutch is not luck - it is a skill."' />
    <meta
      name="description"
      content='5 likes, 3 comments - ntangiblesports on September 3, 2025: "Most athletes train the body. Few train the mind. Clutch is not luck - it is a skill."' />
    <meta
      property="og:description"
      content='5 likes, 3 comments - ntangiblesports on September 3, 2025: "Most athletes train the body. Few train the mind. Clutch is not luck - it is a skill."' />
    <meta property="og:image" content="https://instagram.example.com/post-full.jpg" />
  </head>
  <body></body>
</html>
"""


def test_parse_youtube_feed_extracts_structured_video_items():
    items = parse_youtube_feed(
        YOUTUBE_FEED,
        source_url="https://www.youtube.com/feeds/videos.xml?channel_id=channel-1",
    )

    assert len(items) == 1
    item = items[0]
    assert item.canonical_key == "youtube:video:abc123"
    assert item.platform == "youtube"
    assert item.item_type == "video"
    assert item.title == "What is NTelligence?"
    assert item.author == "NTangible"
    assert item.external_id == "abc123"
    assert item.published_at == datetime(2026, 2, 1, 12, 0, tzinfo=UTC)
    assert item.assets[0].url == "https://img.youtube.com/vi/abc123/hqdefault.jpg"
    assert item.metrics[0].payload["views"] == 4


def test_parse_generic_document_extracts_page_text_and_metadata():
    items = parse_generic_document(
        ARTICLE_HTML,
        url="https://thealliancefastpitch.com/blog/mind-over-matter",
        source_slug="alliance_blog_article",
    )

    assert len(items) == 1
    item = items[0]
    assert item.canonical_key == "web:page:https://thealliancefastpitch.com/blog/mind-over-matter"
    assert item.platform == "web"
    assert item.item_type == "page"
    assert item.title == "Mind Over Matter"
    assert item.author == "NTangible"
    assert item.summary == "How big-time athletes build unbreakable mental games."
    assert "Elite athletes train their mind" in item.body_text
    assert item.assets[0].url == "https://example.com/cover.jpg"
    assert item.published_at == datetime(2025, 4, 16, 10, 0, tzinfo=UTC)


def test_parse_generic_document_extracts_linkedin_json_ld_metrics():
    items = parse_generic_document(
        LINKEDIN_POST_HTML,
        url="https://www.linkedin.com/posts/injuryexpert_ntangible-post",
        source_slug="william_carroll_ntangible_linkedin_post",
    )

    assert len(items) == 1
    item = items[0]
    assert item.platform == "linkedin"
    assert item.item_type == "social_post"
    assert item.title == "Absolutely huge announcements coming after the holidays for NTangible."
    assert item.author == "William Carroll"
    assert item.published_at == datetime(2024, 12, 20, 9, 25, 34, 666000, tzinfo=UTC)
    assert item.metrics[0].payload == {"likes": 43, "comments": 2}
    assert item.assets[0].url == "https://linkedin.example.com/post.jpg"
    assert "Absolutely huge announcements" in (item.body_text or "")


def test_parse_js_text_chunk_extracts_meaningful_content_and_assets():
    items = parse_js_text_chunk(
        ROUTE_CHUNK_JS,
        url="https://ntangible.co/assets/Team-D9JR-r6u.js",
        source_slug="ntangible_team_chunk",
    )

    assert len(items) == 1
    item = items[0]
    assert item.item_type == "bundle_chunk"
    assert item.title == "ntangible_team_chunk"
    assert "Dan Connerty" in item.body_text
    assert "Founder and CEO" in item.body_text
    assert "Research & Validation" in item.body_text
    assert "text-xl md:text-3xl" not in item.body_text
    assert item.assets[0].url == "https://example.com/dan.jpg"


def test_parse_instagram_profile_rendered_extracts_profile_and_posts():
    items = parse_instagram_profile_rendered(
        INSTAGRAM_RENDERED_HTML,
        source_url="https://www.instagram.com/ntangiblesports",
        source_slug="ntangible_instagram_profile",
    )

    assert len(items) == 3

    profile = items[0]
    assert profile.canonical_key == "instagram:profile:ntangiblesports"
    assert profile.platform == "instagram"
    assert profile.item_type == "profile"
    assert profile.title == "@ntangiblesports"
    assert "NTangible" in (profile.summary or "")
    assert profile.metrics[0].payload == {"posts": 140, "followers": 909, "following": 239}

    post = next(item for item in items if item.external_id == "DOJIVUqEXmr")
    assert post.item_type == "post"
    assert post.url == "https://www.instagram.com/ntangiblesports/p/DOJIVUqEXmr/"
    assert post.assets[0].url == "https://instagram.example.com/photo.jpg"
    assert post.published_at == datetime(2025, 9, 3, tzinfo=UTC)

    reel = next(item for item in items if item.external_id == "DVYwPJIk2n_")
    assert reel.item_type == "reel"
    assert reel.url == "https://www.instagram.com/ntangiblesports/reel/DVYwPJIk2n_/"
    assert reel.assets[0].url == "https://instagram.example.com/reel.jpg"
    assert "Jeff Curtis" in (reel.body_text or "")


def test_parse_instagram_post_document_extracts_public_metrics_and_caption():
    items = parse_instagram_post_document(
        INSTAGRAM_POST_HTML,
        source_url="https://www.instagram.com/ntangiblesports/p/DOJIVUqEXmr/",
        source_slug="ntangible_instagram_profile",
    )

    assert len(items) == 1
    item = items[0]
    assert item.canonical_key == "instagram:post:DOJIVUqEXmr"
    assert item.platform == "instagram"
    assert item.item_type == "post"
    assert item.author == "ntangiblesports"
    assert item.published_at == datetime(2025, 9, 3, tzinfo=UTC)
    assert item.metrics[0].payload == {"likes": 5, "comments": 3}
    assert item.assets[0].url == "https://instagram.example.com/post-full.jpg"
    assert "Most athletes train the body" in (item.body_text or "")
