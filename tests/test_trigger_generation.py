from app.models.workflow import Platform
from app.services.trigger_generation import generate_trigger_draft
from app.triggers.partner_events import TriggerRequest


def test_generate_trigger_draft_for_x_returns_manual_candidate(monkeypatch):
    request = TriggerRequest(
        partner_slug="alliance_fastpitch",
        event_type="commitment_update",
        platform=Platform.X,
        workflow_slug="partner-alliance-fastpitch-commitment-update-x",
        content_type="data_drop",
        pillar="client_proof",
        context="Partner commitment update from Alliance Fastpitch.",
        dynamic_value_groups=[],
    )

    def fake_generate_tweets(content_type, pillar, claims, context):
        assert content_type == "data_drop"
        return (
            [
                {
                    "content": "Jane Smith committed to Oklahoma. Gold tier under pressure.",
                    "content_type": "data_drop",
                    "pillar": "client_proof",
                    "claim_keys_used": [],
                    "hashtags": ["#AllianceFastpitch"],
                    "media_needed": False,
                    "intent": "partner",
                }
            ],
            {
                "prompt_snapshot": "prompt",
                "response": {"raw_text": "text"},
                "model": "claude",
                "tokens_in": 10,
                "tokens_out": 20,
                "cost_estimate": 0.1,
                "duration_ms": 100,
            },
        )

    def fake_compliance(draft, requested_claims, dynamic_value_groups=None):
        assert requested_claims == []
        assert dynamic_value_groups == []

        class Result:
            passed = True
            corrected_content = draft["content"]
            corrected_hashtags = draft["hashtags"]
            checks_run = ["trademarks"]

        return Result()

    monkeypatch.setattr("app.services.trigger_generation.generate_tweets", fake_generate_tweets)
    monkeypatch.setattr("app.services.trigger_generation.run_compliance_checks", fake_compliance)

    result = generate_trigger_draft(request)

    assert result.platform == Platform.X
    assert result.content.startswith("Jane Smith committed")
    assert result.post_url is None
    assert result.platform_post_id is None


def test_generate_trigger_draft_for_linkedin_stays_unpublished(monkeypatch):
    request = TriggerRequest(
        partner_slug="alliance_fastpitch",
        event_type="leaderboard_published",
        platform=Platform.LINKEDIN,
        workflow_slug="partner-alliance-fastpitch-leaderboard-published-linkedin",
        content_type="data_insight",
        pillar="client_proof",
        context="Partner leaderboard update from Alliance Fastpitch.",
        dynamic_value_groups=[["812"], ["804"]],
    )

    def fake_generate_linkedin_post(content_type, pillar, claims, context):
        assert content_type == "data_insight"
        return (
            {
                "content": "Alliance Nationals data shows Jane Smith and Ava Brown leading the field.",
                "content_type": "data_insight",
                "pillar": "client_proof",
                "claim_keys_used": [],
                "hashtags": ["#AllianceFastpitch", "#SoftballData"],
                "intent": "partner",
            },
            {
                "prompt_snapshot": "prompt",
                "response": {"raw_text": "text"},
                "model": "claude",
                "tokens_in": 10,
                "tokens_out": 20,
                "cost_estimate": 0.1,
                "duration_ms": 100,
            },
        )

    def fake_compliance(draft, requested_claims, dynamic_value_groups=None):
        assert dynamic_value_groups == [["812"], ["804"]]

        class Result:
            passed = True
            corrected_content = draft["content"]
            corrected_hashtags = draft["hashtags"]
            checks_run = ["trademarks"]

        return Result()

    monkeypatch.setattr("app.services.trigger_generation.generate_linkedin_post", fake_generate_linkedin_post)
    monkeypatch.setattr("app.services.trigger_generation.run_linkedin_compliance_checks", fake_compliance)

    result = generate_trigger_draft(request)

    assert result.platform == Platform.LINKEDIN
    assert result.content.startswith("Alliance Nationals data")
    assert result.post_url is None
    assert result.platform_post_id is None
