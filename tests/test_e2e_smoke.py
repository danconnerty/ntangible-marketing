"""
End-to-end smoke test for the generate -> comply -> publish flow.
Uses MockPublisher and skips the real Claude API.
"""

from app.agents.compliance import run_compliance_checks
from app.agents.content_writer import build_prompt
from app.publishers.mock import MockPublisher


def test_generate_comply_publish_flow():
    prompt = build_prompt(
        content_type="hot_take",
        pillar="blind_spot",
        claims=[],
        context=None,
    )
    assert "system" in prompt
    assert "user" in prompt

    mock_variation = {
        "content": "You measure arm strength, speed, GPA. What about pressure?",
        "content_type": "hot_take",
        "pillar": "blind_spot",
        "claim_keys_used": [],
        "hashtags": ["#MentalPerformance"],
        "media_needed": False,
        "intent": "brand",
    }

    result = run_compliance_checks(mock_variation, requested_claims=[])
    assert result.passed, f"Compliance failed: {result.failure_reason}"

    publisher = MockPublisher()
    post_result = publisher.post_tweet(result.corrected_content)
    assert post_result.success
    assert post_result.tweet_url is not None


def test_compliance_rejects_bad_tweet():
    bad_tweet = {
        "content": "This game-changing product will unlock insights!",
        "content_type": "hot_take",
        "pillar": "blind_spot",
        "claim_keys_used": [],
        "hashtags": [],
        "media_needed": False,
        "intent": "brand",
    }
    result = run_compliance_checks(bad_tweet, requested_claims=[])
    assert not result.passed


def test_compliance_rejects_undeclared_number():
    tweet_with_fake_stat = {
        "content": "95% of athletes fail under pressure without training",
        "content_type": "data_drop",
        "pillar": "blind_spot",
        "claim_keys_used": [],
        "hashtags": [],
        "media_needed": False,
        "intent": "brand",
    }
    result = run_compliance_checks(tweet_with_fake_stat, requested_claims=[])
    assert not result.passed
    assert "undeclared_numerics" in result.failed_check


def test_compliance_passes_with_approved_claim():
    tweet_with_claim = {
        "content": "The average failed D1 transfer costs $150K. Know the mental game before you commit.",
        "content_type": "data_drop",
        "pillar": "cost_of_guessing",
        "claim_keys_used": ["failed_transfer_cost"],
        "hashtags": ["#TransferPortal"],
        "media_needed": False,
        "intent": "revenue",
    }
    result = run_compliance_checks(tweet_with_claim, requested_claims=["failed_transfer_cost"])
    assert result.passed, f"Compliance failed: {result.failure_reason}"
