from app.agents.linkedin_compliance import run_linkedin_compliance_checks


def _draft(
    content: str,
    hashtags: list[str] | None = None,
    claim_keys_used: list[str] | None = None,
):
    return {
        "content": content,
        "hashtags": hashtags or [],
        "claim_keys_used": claim_keys_used or [],
    }


def test_linkedin_rejects_over_3000_chars():
    result = run_linkedin_compliance_checks(_draft("x" * 3001), requested_claims=[])
    assert not result.passed
    assert result.failed_check == "char_limit"


def test_linkedin_trims_hashtags_to_five():
    result = run_linkedin_compliance_checks(
        _draft("Pressure data wins.", hashtags=["#one", "#two", "#three", "#four", "#five", "#six"]),
        requested_claims=[],
    )
    assert result.passed
    assert len(result.corrected_hashtags) == 5
