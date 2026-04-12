import pytest

from app.agents.instagram_writer import build_instagram_prompt, parse_instagram_response


def test_build_instagram_prompt_mentions_hook_body_cta():
    prompt = build_instagram_prompt(
        content_type="education_carousel",
        pillar="thought_leadership",
        claims=[],
        context="Transfer portal pressure",
    )
    assert "hook" in prompt["system"].lower()
    assert "6-10 hashtags" in prompt["system"]
    assert "template-driven" in prompt["system"].lower()


def test_parse_instagram_response_requires_fields():
    with pytest.raises(ValueError):
        parse_instagram_response({"caption": "Only caption"})
