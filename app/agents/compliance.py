import re
from dataclasses import dataclass, field

from app.agents.numeric_tokenizer import extract_claim_numerics
from app.config import get_approved_claims, get_brand_voice, get_platform_config


@dataclass
class ComplianceResult:
    passed: bool
    failed_check: str | None = None
    failure_reason: str | None = None
    corrected_content: str | None = None
    corrected_hashtags: list[str] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)


def _protect_and_correct_trademarks(content: str, trademarks: dict[str, list[str]]) -> str:
    protected = content
    placeholders: dict[str, str] = {}

    for index, correct_form in enumerate(trademarks):
        placeholder = f"__TRADEMARK_{index}__"
        placeholders[placeholder] = correct_form
        protected = re.sub(re.escape(correct_form), placeholder, protected, flags=re.IGNORECASE)

    corrected = protected
    for placeholder, correct_form in placeholders.items():
        for variant in trademarks[correct_form]:
            pattern = re.compile(rf"(?<!\w){re.escape(variant)}(?!\w)", re.IGNORECASE)
            corrected = pattern.sub(placeholder, corrected)

    for placeholder, correct_form in placeholders.items():
        corrected = corrected.replace(placeholder, correct_form)

    return corrected


def run_compliance_checks(
    draft: dict,
    requested_claims: list[str],
) -> ComplianceResult:
    brand = get_brand_voice()
    claims_config = get_approved_claims()
    platform = get_platform_config("x")
    content = draft["content"]
    claim_keys_used = draft.get("claim_keys_used", [])
    hashtags = list(draft.get("hashtags", []))
    checks_run: list[str] = []

    checks_run.append("banned_phrases")
    lowered = content.lower()
    for phrase in brand["banned_phrases"]:
        if phrase.lower() in lowered:
            return ComplianceResult(
                passed=False,
                failed_check="banned_phrases",
                failure_reason=f"Contains banned phrase: '{phrase}'",
                checks_run=checks_run,
            )

    checks_run.append("trademarks")
    corrected = _protect_and_correct_trademarks(content, brand["trademarks"])

    checks_run.append("restricted_clients")
    for restricted_name in brand["restricted_clients"]["hard_block"]:
        if restricted_name.lower() in corrected.lower():
            return ComplianceResult(
                passed=False,
                failed_check="restricted_clients",
                failure_reason=f"References restricted client: '{restricted_name}'",
                checks_run=checks_run,
            )

    checks_run.append("claim_keys")
    for key in claim_keys_used:
        if key not in requested_claims:
            return ComplianceResult(
                passed=False,
                failed_check="claim_keys",
                failure_reason=f"Claim key '{key}' was not requested",
                checks_run=checks_run,
            )
        if key not in claims_config["claims"]:
            return ComplianceResult(
                passed=False,
                failed_check="claim_keys",
                failure_reason=f"Claim key '{key}' is not approved",
                checks_run=checks_run,
            )

    checks_run.append("claim_text")
    for key in claim_keys_used:
        claim = claims_config["claims"][key]
        for value_group in claim["check_value_groups"]:
            if not any(variant in corrected for variant in value_group):
                return ComplianceResult(
                    passed=False,
                    failed_check="claim_text",
                    failure_reason=(
                        f"Claim '{key}' declared but required values {value_group} were not found in the text"
                    ),
                    checks_run=checks_run,
                )

    checks_run.append("undeclared_numerics")
    covered_values: set[str] = set()
    for key in claim_keys_used:
        claim = claims_config["claims"][key]
        for value_group in claim["check_value_groups"]:
            covered_values.update(value_group)

    for token in extract_claim_numerics(corrected):
        normalized_token = token.lower()
        if not any(
            normalized_token == covered.lower()
            or normalized_token in covered.lower()
            or covered.lower() in normalized_token
            for covered in covered_values
        ):
            return ComplianceResult(
                passed=False,
                failed_check="undeclared_numerics",
                failure_reason=f"Undeclared numeric '{token}' in text",
                checks_run=checks_run,
            )

    checks_run.append("tone")
    exclamation_count = corrected.count("!")
    if exclamation_count:
        return ComplianceResult(
            passed=False,
            failed_check="tone",
            failure_reason=f"Contains {exclamation_count} exclamation point(s)",
            checks_run=checks_run,
        )

    passive_patterns = (
        r"\b(?:was|were|been|being)\s+\w+ed\b",
        r"\b(?:is|are)\s+being\s+\w+ed\b",
    )
    for pattern in passive_patterns:
        if re.search(pattern, corrected, flags=re.IGNORECASE):
            return ComplianceResult(
                passed=False,
                failed_check="tone",
                failure_reason="Contains passive voice construction",
                checks_run=checks_run,
            )

    checks_run.append("char_limit")
    max_chars = platform["x"]["single_tweet_max_chars"]
    if len(corrected) > max_chars:
        return ComplianceResult(
            passed=False,
            failed_check="char_limit",
            failure_reason=f"Tweet is {len(corrected)} chars (max {max_chars})",
            checks_run=checks_run,
        )

    checks_run.append("hashtags")
    corrected_hashtags = hashtags[: platform["x"]["max_hashtags"]]

    return ComplianceResult(
        passed=True,
        corrected_content=corrected,
        corrected_hashtags=corrected_hashtags,
        checks_run=checks_run,
    )
