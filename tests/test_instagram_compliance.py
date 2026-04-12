from app.agents.instagram_compliance import run_instagram_compliance_checks


def _draft(
    caption: str,
    hashtags: list[str] | None = None,
    claim_keys_used: list[str] | None = None,
    cta_type: str = "comment",
    asset_plan: dict | None = None,
):
    return {
        "caption": caption,
        "hashtags": hashtags or [],
        "claim_keys_used": claim_keys_used or [],
        "cta_type": cta_type,
        "asset_plan": asset_plan or {},
    }


def test_instagram_rejects_too_few_hashtags():
    result = run_instagram_compliance_checks(
        _draft(
            "Pressure is visible.\nMost programs still guess.\nComment if your staff wants cleaner signal.",
            hashtags=["#one", "#two"],
        ),
        requested_claims=[],
    )
    assert not result.passed
    assert result.failed_check == "hashtags"


def test_instagram_trims_hashtags_to_maximum():
    result = run_instagram_compliance_checks(
        _draft(
            "Pressure is visible.\nMost programs still guess.\nComment if your staff wants cleaner signal.",
            hashtags=[
                "#one",
                "#two",
                "#three",
                "#four",
                "#five",
                "#six",
                "#seven",
                "#eight",
                "#nine",
                "#ten",
                "#eleven",
            ],
        ),
        requested_claims=[],
    )
    assert result.passed
    assert len(result.corrected_hashtags) == 10


def test_instagram_rejects_public_athlete_score_when_not_eligible():
    result = run_instagram_compliance_checks(
        _draft(
            "Pressure is visible.\nThis athlete handled the hardest inning.\nShare this with a coach.",
            hashtags=["#one", "#two", "#three", "#four", "#five", "#six"],
            cta_type="share",
            asset_plan={"athlete_score_eligible": False, "text_fields": {"score": "612"}},
        ),
        requested_claims=[],
    )
    assert not result.passed
    assert result.failed_check == "athlete_score_visibility"
