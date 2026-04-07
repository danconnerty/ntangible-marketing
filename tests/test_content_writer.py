import pytest

from app.agents.content_writer import build_prompt, parse_generation_response


def test_build_prompt_includes_brand_voice():
    prompt = build_prompt(
        content_type="hot_take",
        pillar="blind_spot",
        claims=[],
        context=None,
    )
    assert "sports bar meets data lab" in prompt["system"].lower() or "punchy" in prompt["system"].lower()


def test_build_prompt_includes_pillar():
    prompt = build_prompt(
        content_type="hot_take",
        pillar="blind_spot",
        claims=[],
        context=None,
    )
    assert "evaluating half the picture" in prompt["system"].lower() or "blind_spot" in prompt["user"].lower()


def test_build_prompt_includes_banned_phrases():
    prompt = build_prompt(
        content_type="hot_take",
        pillar="blind_spot",
        claims=[],
        context=None,
    )
    system = prompt["system"].lower()
    assert "game-changing" in system or "banned" in system


def test_build_prompt_includes_claims():
    prompt = build_prompt(
        content_type="data_drop",
        pillar="cost_of_guessing",
        claims=["failed_transfer_cost"],
        context=None,
    )
    combined = prompt["system"] + prompt["user"]
    assert "$150K" in combined or "150K" in combined


def test_build_prompt_includes_context():
    prompt = build_prompt(
        content_type="trend_jack",
        pillar="blind_spot",
        claims=[],
        context="Transfer portal just opened",
    )
    assert "Transfer portal just opened" in prompt["user"]


def test_build_prompt_char_limit():
    prompt = build_prompt(
        content_type="hot_take",
        pillar="blind_spot",
        claims=[],
        context=None,
    )
    assert "280" in prompt["system"]


def test_parse_valid_response():
    raw = {
        "content": "Test tweet",
        "content_type": "hot_take",
        "pillar": "blind_spot",
        "claim_keys_used": [],
        "hashtags": ["#Test"],
        "media_needed": False,
        "intent": "brand",
    }
    parsed = parse_generation_response(raw)
    assert parsed["content"] == "Test tweet"
    assert parsed["intent"] == "brand"


def test_parse_response_missing_field_raises():
    with pytest.raises(ValueError):
        parse_generation_response({"content": "Test tweet"})
