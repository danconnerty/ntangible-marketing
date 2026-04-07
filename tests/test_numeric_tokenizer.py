from app.agents.numeric_tokenizer import extract_claim_numerics


def test_dollar_amounts():
    tokens = extract_claim_numerics("Costs $150K to fail")
    assert "$150K" in tokens


def test_dollar_with_decimal():
    tokens = extract_claim_numerics("Draft bust: $3.5M wasted")
    assert "$3.5M" in tokens


def test_percentage():
    tokens = extract_claim_numerics("73% of athletes above 800 CF")
    assert "73%" in tokens
    assert "800" in tokens


def test_large_number_with_commas():
    tokens = extract_claim_numerics("Over 30,000 athletes tested")
    assert "30,000" in tokens


def test_number_with_plus():
    tokens = extract_claim_numerics("6,000+ assessments completed")
    assert "6,000+" in tokens


def test_bare_suffix():
    tokens = extract_claim_numerics("Reached 1M data points")
    assert "1M" in tokens


def test_ignores_ordinals():
    tokens = extract_claim_numerics("1st round pick failed again")
    assert len(tokens) == 0


def test_ignores_d1_d2_labels():
    tokens = extract_claim_numerics("D1 coaches are watching D2 players")
    assert len(tokens) == 0


def test_ignores_hashtag_numbers():
    tokens = extract_claim_numerics("We are #1 in pressure testing")
    assert len(tokens) == 0


def test_ignores_bare_single_digits():
    tokens = extract_claim_numerics("This is a great day")
    assert len(tokens) == 0


def test_mixed_content():
    text = "The 1st round bust costs $3.5M. D1 coaches see 73% success with 800+ CF scores."
    tokens = extract_claim_numerics(text)
    assert "$3.5M" in tokens
    assert "73%" in tokens
    assert "800+" in tokens
    assert "1st" not in tokens
    assert "D1" not in tokens


def test_seven_sports():
    tokens = extract_claim_numerics("Validated across 7 sports")
    assert "7 sports" in tokens


def test_bare_small_number_without_unit_ignored():
    tokens = extract_claim_numerics("We saw 3 things happen")
    assert len(tokens) == 0


def test_number_k_without_dollar():
    tokens = extract_claim_numerics("150K lifetime value lost")
    assert "150K" in tokens


def test_empty_string():
    tokens = extract_claim_numerics("")
    assert tokens == []
