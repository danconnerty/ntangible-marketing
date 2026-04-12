from app.content_brain.sources import load_seed_targets


def test_load_seed_targets_includes_confirmed_public_sources():
    targets = load_seed_targets()
    slugs = {target.slug for target in targets}

    assert "ntangible_home" in slugs
    assert "ntangible_youtube_feed" in slugs
    assert "wayback_archived_sitemap" in slugs
    assert "alliance_blog_article" in slugs

    youtube_target = next(target for target in targets if target.slug == "ntangible_youtube_feed")
    assert youtube_target.parser == "youtube_feed"
    assert youtube_target.url == "https://www.youtube.com/feeds/videos.xml?channel_id=UC6k2GMbwnIGyEOzXKPZZpWQ"

    instagram_target = next(target for target in targets if target.slug == "ntangible_instagram_profile")
    assert instagram_target.parser == "instagram_profile_rendered"
    assert instagram_target.metadata["fetch_mode"] == "rendered"

    future_stars_target = next(target for target in targets if target.slug == "future_stars_ntangible_article")
    assert future_stars_target.metadata["headers"]["User-Agent"].startswith("Mozilla/")
