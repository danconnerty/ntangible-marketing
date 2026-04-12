from app.config import load_yaml


def test_brand_voice_loads():
    data = load_yaml("brand_voice.yaml")
    assert "voice" in data
    assert "banned_phrases" in data
    assert "trademarks" in data
    assert "restricted_clients" in data
    assert "verified_clients" in data
    assert len(data["banned_phrases"]) > 0


def test_content_pillars_loads():
    data = load_yaml("content_pillars.yaml")
    assert "pillars" in data
    expected_pillars = {
        "blind_spot",
        "cost_of_guessing",
        "client_proof",
        "thought_leadership",
        "product",
    }
    assert set(data["pillars"].keys()) == expected_pillars
    for pillar in data["pillars"].values():
        assert "description" in pillar
        assert "example_angles" in pillar


def test_approved_claims_loads():
    data = load_yaml("approved_claims.yaml")
    assert "claims" in data
    for claim in data["claims"].values():
        assert "text" in claim
        assert "check_value_groups" in claim
        assert "source" in claim
        assert "verified_date" in claim
        for group in claim["check_value_groups"]:
            assert isinstance(group, list)
            assert len(group) > 0


def test_platform_x_loads():
    data = load_yaml("platforms/x.yaml")
    assert "x" in data
    assert data["x"]["single_tweet_max_chars"] == 280
    assert data["x"]["max_hashtags"] == 2


def test_platform_linkedin_loads():
    data = load_yaml("platforms/linkedin.yaml")
    assert "linkedin" in data
    linkedin = data["linkedin"]
    assert linkedin["max_chars"] == 3000
    assert linkedin["max_hashtags"] == 5
    assert linkedin["auto_publish_default_tier"] == "tier_1"
    assert linkedin["content_types"]["thought_leadership"]["target_min_chars"] == 1200
    assert linkedin["content_types"]["thought_leadership"]["target_max_chars"] == 1500
    assert linkedin["content_types"]["data_insight"]["target_min_chars"] == 600
    assert linkedin["content_types"]["data_insight"]["target_max_chars"] == 800
    assert linkedin["content_types"]["company_update"]["target_min_chars"] == 300
    assert linkedin["content_types"]["company_update"]["target_max_chars"] == 900


def test_platform_instagram_loads():
    data = load_yaml("platforms/instagram.yaml")
    assert "instagram" in data
    instagram = data["instagram"]
    assert instagram["max_caption_chars"] == 2200
    assert instagram["min_hashtags"] == 6
    assert instagram["max_hashtags"] == 10
    assert instagram["auto_publish_default_tier"] == "tier_1"
    assert instagram["posting_windows_et"] == ["Tue-Fri 11:00-13:00", "Tue-Fri 19:00-21:00"]
    assert instagram["template_families"]["education_carousel"]["min_slides"] == 5
    assert instagram["template_families"]["education_carousel"]["max_slides"] == 8
