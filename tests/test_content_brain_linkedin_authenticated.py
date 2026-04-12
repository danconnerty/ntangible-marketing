from datetime import UTC, datetime

from app.content_brain.linkedin_authenticated import build_linkedin_authenticated_post_items


def test_build_linkedin_authenticated_post_items_extracts_visual_assets():
    payload = {
        "posts": [
            {
                "position": 1,
                "activity_urn": "urn:li:activity:7444796045227606016",
                "text": "\n".join(
                    [
                        "Feed post number 1",
                        "NTangible",
                        "NTangible",
                        "160 followers",
                        "160 followers",
                        "6d • Edited •",
                        "6 days ago • Edited • Visible to anyone on or off LinkedIn",
                        "Proud to share that NTangible has been nominated for the 2026 Built in Canada Awards.",
                    ]
                ),
                "links": [],
                "buttons": [
                    {"text": "7", "aria": "Dan Connerty and 6 others"},
                    {"text": "", "aria": "1 comment on NTangible's post"},
                    {"text": "", "aria": "1 repost of NTangible's post"},
                ],
                "images": [
                    {
                        "src": "https://media.licdn.com/dms/image/v2/D560BAQGIraIEUr5POQ/company-logo_100_100/B56Zd0k774H8AQ-/0/1750007529641?e=1776902400&v=beta&t=logo",
                        "alt": "",
                    },
                    {
                        "src": "https://media.licdn.com/dms/image/v2/D4E10AQEUs0VRD2a9fQ/image-shrink_800/B4EZ1E6eu0I4Ag-/0/1774977674533?e=1776168000&v=beta&t=post",
                        "alt": "No alternative text description for this image",
                    },
                    {
                        "src": "https://static.licdn.com/aero-v1/sc/h/8ekq8gho1ruaf8i7f86vd1ftt",
                        "alt": "like",
                    },
                ],
            }
        ]
    }

    items = build_linkedin_authenticated_post_items(
        payload,
        observed_at=datetime(2026, 4, 7, 11, 8, tzinfo=UTC),
    )

    assert len(items) == 1
    item = items[0]
    assert item.canonical_key == "linkedin:activity:7444796045227606016"
    assert item.assets
    assert [asset.url for asset in item.assets] == [
        "https://media.licdn.com/dms/image/v2/D4E10AQEUs0VRD2a9fQ/image-shrink_800/B4EZ1E6eu0I4Ag-/0/1774977674533?e=1776168000&v=beta&t=post"
    ]
    assert item.metrics[0].payload == {"reactions": 7, "comments": 1, "reposts": 1}
