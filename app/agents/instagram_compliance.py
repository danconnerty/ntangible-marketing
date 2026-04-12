from collections.abc import Mapping, Sequence
import re

from app.agents.compliance import ComplianceResult, _protect_and_correct_trademarks
from app.agents.numeric_tokenizer import extract_claim_numerics
from app.config import get_approved_claims, get_brand_voice, get_platform_config


CTA_PATTERNS = {
    "tag": re.compile(r"\btag\b", re.IGNORECASE),
    "comment": re.compile(r"\bcomment\b", re.IGNORECASE),
    "share": re.compile(r"\bshare\b", re.IGNORECASE),
    "link_in_bio": re.compile(r"\blink in bio\b", re.IGNORECASE),
    "save": re.compile(r"\bsave\b", re.IGNORECASE),
}


def _flatten_text_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        results: list[str] = []
        for nested in value.values():
            results.extend(_flatten_text_values(nested))
        return results
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        results = []
        for nested in value:
            results.extend(_flatten_text_values(nested))
        return results
    return []


def _covered_values(claim_keys_used: list[str], claims_config: dict) -> set[str]:
    covered: set[str] = set()
    for key in claim_keys_used:
        claim = claims_config["claims"][key]
        for value_group in claim["check_value_groups"]:
            covered.update(value_group)
    return covered


def run_instagram_compliance_checks(
    draft: dict,
    requested_claims: list[str],
) -> ComplianceResult:
    brand = get_brand_voice()
    claims_config = get_approved_claims()
    platform = get_platform_config("instagram")["instagram"]
    caption = draft["caption"]
    claim_keys_used = draft.get("claim_keys_used", [])
    hashtags = list(draft.get("hashtags", []))
    cta_type = draft.get("cta_type", "")
    asset_plan = draft.get("asset_plan", {})
    asset_text = "\n".join(_flatten_text_values(asset_plan))
    combined_text = "\n".join(part for part in [caption, asset_text] if part)
    checks_run: list[str] = []

    checks_run.append("banned_phrases")
    lowered = caption.lower()
    for phrase in brand["banned_phrases"]:
        if phrase.lower() in lowered:
            return ComplianceResult(
                passed=False,
                failed_check="banned_phrases",
                failure_reason=f"Contains banned phrase: '{phrase}'",
                checks_run=checks_run,
            )

    checks_run.append("trademarks")
    corrected_caption = _protect_and_correct_trademarks(caption, brand["trademarks"])

    checks_run.append("restricted_clients")
    for restricted_name in brand["restricted_clients"]["hard_block"]:
        if restricted_name.lower() in corrected_caption.lower():
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
            if not any(variant in combined_text for variant in value_group):
                return ComplianceResult(
                    passed=False,
                    failed_check="claim_text",
                    failure_reason=(
                        f"Claim '{key}' declared but required values {value_group} were not found in caption or asset text"
                    ),
                    checks_run=checks_run,
                )

    checks_run.append("athlete_score_visibility")
    if asset_plan.get("athlete_score_eligible") is False:
        return ComplianceResult(
            passed=False,
            failed_check="athlete_score_visibility",
            failure_reason="Athlete-specific score is not eligible for public Instagram output",
            checks_run=checks_run,
        )

    covered_values = _covered_values(claim_keys_used, claims_config)

    checks_run.append("undeclared_numerics")
    for token in extract_claim_numerics(combined_text):
        normalized = token.lower()
        if not any(
            normalized == covered.lower()
            or normalized in covered.lower()
            or covered.lower() in normalized
            for covered in covered_values
        ):
            return ComplianceResult(
                passed=False,
                failed_check="undeclared_numerics",
                failure_reason=f"Undeclared numeric '{token}' in caption or asset text",
                checks_run=checks_run,
            )

    checks_run.append("structure")
    lines = [line.strip() for line in corrected_caption.splitlines() if line.strip()]
    if len(lines) < 3:
        return ComplianceResult(
            passed=False,
            failed_check="structure",
            failure_reason="Caption must include hook, body, and CTA on separate lines",
            checks_run=checks_run,
        )

    if "#" in corrected_caption:
        return ComplianceResult(
            passed=False,
            failed_check="hashtags_position",
            failure_reason="Hashtags must be stored separately so they appear only at the end",
            checks_run=checks_run,
        )

    checks_run.append("cta")
    pattern = CTA_PATTERNS.get(cta_type)
    if not pattern:
        return ComplianceResult(
            passed=False,
            failed_check="cta",
            failure_reason=f"Unsupported CTA type '{cta_type}'",
            checks_run=checks_run,
        )

    matched_lines = [line for line in lines if any(regex.search(line) for regex in CTA_PATTERNS.values())]
    if len(matched_lines) != 1 or not pattern.search(lines[-1]):
        return ComplianceResult(
            passed=False,
            failed_check="cta",
            failure_reason="Caption must contain exactly one CTA and it must be the final line",
            checks_run=checks_run,
        )

    checks_run.append("hashtags")
    min_hashtags = platform["min_hashtags"]
    max_hashtags = platform["max_hashtags"]
    if len(hashtags) < min_hashtags:
        return ComplianceResult(
            passed=False,
            failed_check="hashtags",
            failure_reason=f"Instagram requires at least {min_hashtags} hashtags",
            checks_run=checks_run,
        )
    corrected_hashtags = hashtags[:max_hashtags]

    checks_run.append("char_limit")
    rendered_caption = corrected_caption + "\n\n" + " ".join(corrected_hashtags)
    if len(rendered_caption) > platform["max_caption_chars"]:
        return ComplianceResult(
            passed=False,
            failed_check="char_limit",
            failure_reason=(
                f"Instagram caption is {len(rendered_caption)} chars "
                f"(max {platform['max_caption_chars']})"
            ),
            checks_run=checks_run,
        )

    return ComplianceResult(
        passed=True,
        corrected_content=corrected_caption,
        corrected_hashtags=corrected_hashtags,
        checks_run=checks_run,
    )
