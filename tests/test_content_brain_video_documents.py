from app.content_brain.video_documents import build_youtube_oembed_item


def test_build_youtube_oembed_item_sets_core_video_fields():
    item = build_youtube_oembed_item(
        video_id="NMKUJfjI_HQ",
        watch_url="https://www.youtube.com/watch?v=NMKUJfjI_HQ",
        title="NTangible Recruiting Dashboard",
        author_name="NTANGIBLE",
        thumbnail_url="https://i.ytimg.com/vi/NMKUJfjI_HQ/hqdefault.jpg",
        source_slug="supplemental_youtube_video",
    )

    assert item.canonical_key == "youtube:video:NMKUJfjI_HQ"
    assert item.platform == "youtube"
    assert item.item_type == "video"
    assert item.title == "NTangible Recruiting Dashboard"
    assert item.author == "NTANGIBLE"
    assert item.external_id == "NMKUJfjI_HQ"
    assert item.assets[0].url == "https://i.ytimg.com/vi/NMKUJfjI_HQ/hqdefault.jpg"
    assert item.metadata["source_slug"] == "supplemental_youtube_video"
