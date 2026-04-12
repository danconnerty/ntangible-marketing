import pytest

from app.agents.linkedin_writer import build_linkedin_prompt, parse_linkedin_response


def test_build_linkedin_prompt_uses_linkedin_voice():
    prompt = build_linkedin_prompt(
        content_type="thought_leadership",
        pillar="thought_leadership",
        claims=[],
        context="Transfer portal inefficiency",
    )
    assert "professional but not corporate" in prompt["system"].lower()
    assert "3-5 hashtags" in prompt["system"]


def test_parse_linkedin_response_requires_fields():
    with pytest.raises(ValueError):
        parse_linkedin_response({"content": "Only content"})
