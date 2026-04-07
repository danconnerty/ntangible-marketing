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
