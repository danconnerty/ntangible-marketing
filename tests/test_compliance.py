from app.agents.compliance import run_compliance_checks


def _make_draft(content: str, claim_keys_used: list[str] | None = None):
    return {
        "content": content,
        "claim_keys_used": claim_keys_used or [],
        "hashtags": [],
    }


def test_banned_phrase_rejected():
    draft = _make_draft("This is a game-changing product")
    result = run_compliance_checks(draft, requested_claims=[])
    assert not result.passed
    assert "banned_phrases" in result.failed_check


def test_banned_phrase_case_insensitive():
    draft = _make_draft("We LEVERAGE DATA to win")
    result = run_compliance_checks(draft, requested_claims=[])
    assert not result.passed
    assert "banned_phrases" in result.failed_check


def test_trademark_auto_corrected():
    draft = _make_draft("The Clutch Factor score matters")
    result = run_compliance_checks(draft, requested_claims=[])
    assert result.passed
    assert "Clutch Factor™" in result.corrected_content


def test_trademark_already_correct():
    draft = _make_draft("The Clutch Factor™ score matters")
    result = run_compliance_checks(draft, requested_claims=[])
    assert result.passed
    assert result.corrected_content == "The Clutch Factor™ score matters"


def test_restricted_client_rejected():
    draft = _make_draft("Florida A&M is using our platform")
    result = run_compliance_checks(draft, requested_claims=[])
    assert not result.passed
    assert "restricted_clients" in result.failed_check


def test_restricted_client_famu_rejected():
    draft = _make_draft("FAMU signed up today")
    result = run_compliance_checks(draft, requested_claims=[])
    assert not result.passed


def test_verified_client_allowed():
    draft = _make_draft("Michigan State is measuring what matters")
    result = run_compliance_checks(draft, requested_claims=[])
    assert result.passed


def test_claim_key_not_in_request_rejected():
    draft = _make_draft("73% success rate", claim_keys_used=["cf_all_american"])
    result = run_compliance_checks(draft, requested_claims=[])
    assert not result.passed
    assert "claim_keys" in result.failed_check


def test_claim_key_valid():
    draft = _make_draft("73% of athletes above 800 CF", claim_keys_used=["cf_all_american"])
    result = run_compliance_checks(draft, requested_claims=["cf_all_american"])
    assert result.passed


def test_claim_wrong_number_rejected():
    draft = _make_draft("85% of athletes above 800 CF", claim_keys_used=["cf_all_american"])
    result = run_compliance_checks(draft, requested_claims=["cf_all_american"])
    assert not result.passed
    assert "claim_text" in result.failed_check


def test_undeclared_numeric_rejected():
    draft = _make_draft("90% of coaches agree this works", claim_keys_used=[])
    result = run_compliance_checks(draft, requested_claims=[])
    assert not result.passed
    assert "undeclared_numerics" in result.failed_check


def test_ordinal_not_flagged():
    draft = _make_draft("The 1st thing D1 coaches notice")
    result = run_compliance_checks(draft, requested_claims=[])
    assert result.passed


def test_exclamation_rejected():
    draft = _make_draft("This is amazing! Wow!")
    result = run_compliance_checks(draft, requested_claims=[])
    assert not result.passed
    assert "tone" in result.failed_check


def test_over_280_rejected():
    draft = _make_draft("x" * 281)
    result = run_compliance_checks(draft, requested_claims=[])
    assert not result.passed
    assert "char_limit" in result.failed_check


def test_exactly_280_passes():
    draft = _make_draft("x" * 280)
    result = run_compliance_checks(draft, requested_claims=[])
    assert result.passed


def test_excess_hashtags_trimmed():
    draft = _make_draft("Good tweet")
    draft["hashtags"] = ["#one", "#two", "#three"]
    result = run_compliance_checks(draft, requested_claims=[])
    assert result.passed
    assert len(result.corrected_hashtags) == 2


def test_clean_tweet_passes():
    draft = _make_draft(
        "Personality profiles tell you who someone is in the locker room. Not who they are in the bottom of the 9th."
    )
    result = run_compliance_checks(draft, requested_claims=[])
    assert result.passed
    assert result.failed_check is None
