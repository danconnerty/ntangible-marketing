import pytest

from app.agents.newsletter_writer import build_newsletter_prompt, parse_newsletter_response


def test_build_newsletter_prompt_mentions_segments_and_required_sections():
    prompt = build_newsletter_prompt(
        content_type="monthly_newsletter",
        pillar="thought_leadership",
        claims=[],
        context="April recruiting pressure data",
        segment="coaches_front_offices",
    )

    assert "coaches_front_offices" in prompt["system"]
    assert "subject" in prompt["system"].lower()
    assert "preview_text" in prompt["system"]
    assert "proof_point" in prompt["system"]
    assert "product_update" in prompt["system"]


def test_parse_newsletter_response_requires_fields():
    with pytest.raises(ValueError):
        parse_newsletter_response({"subject": "Only subject"})


def test_parse_newsletter_response_accepts_complete_payload():
    parsed = parse_newsletter_response(
        {
            "segment": "coaches_front_offices",
            "subject": "Pressure data coaches should not ignore",
            "preview_text": "What April showed before film caught up.",
            "hook": "Most misses happen before the board is final.",
            "proof_point": "Alliance coaches surfaced earlier separation on pressure profiles.",
            "product_update": "Workflow previews now show rejected examples.",
            "cta": "Reply to book a demo",
            "body_markdown": "## April\nBody",
            "body_html": "<h2>April</h2><p>Body</p>",
        }
    )

    assert parsed["segment"] == "coaches_front_offices"
    assert parsed["subject"].startswith("Pressure data")
