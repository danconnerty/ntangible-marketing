from app.agents.compliance import ComplianceResult, _protect_and_correct_trademarks
from app.config import get_brand_voice, get_platform_config


def run_newsletter_compliance_checks(draft: dict) -> ComplianceResult:
    brand = get_brand_voice()
    platform = get_platform_config("newsletter")["newsletter"]
    checks_run: list[str] = []

    subject = draft.get("subject", "").strip()
    preview_text = draft.get("preview_text", "").strip()
    segment = draft.get("segment", "").strip()
    body_markdown = draft.get("body_markdown", "").strip()

    checks_run.append("metadata")
    if not subject or not preview_text or not segment:
        return ComplianceResult(
            passed=False,
            failed_check="metadata",
            failure_reason="Missing newsletter subject, preview text, or segment",
            checks_run=checks_run,
        )

    checks_run.append("segment")
    allowed_segments = set(platform.get("allowed_segments", []))
    if segment not in allowed_segments:
        return ComplianceResult(
            passed=False,
            failed_check="segment",
            failure_reason=f"Unsupported newsletter segment '{segment}'",
            checks_run=checks_run,
        )

    checks_run.append("required_sections")
    required_sections = {
        "hook": draft.get("hook", "").strip(),
        "proof_point": draft.get("proof_point", "").strip(),
        "product_update": draft.get("product_update", "").strip(),
        "cta": draft.get("cta", "").strip(),
    }
    missing_sections = [name for name, value in required_sections.items() if not value]
    if missing_sections:
        return ComplianceResult(
            passed=False,
            failed_check="required_sections",
            failure_reason=f"Missing required newsletter sections: {', '.join(missing_sections)}",
            checks_run=checks_run,
        )

    checks_run.append("banned_phrases")
    lowered = " ".join([subject, preview_text, body_markdown]).lower()
    for phrase in brand["banned_phrases"]:
        if phrase.lower() in lowered:
            return ComplianceResult(
                passed=False,
                failed_check="banned_phrases",
                failure_reason=f"Contains banned phrase: '{phrase}'",
                checks_run=checks_run,
            )

    checks_run.append("trademarks")
    corrected_body = _protect_and_correct_trademarks(body_markdown, brand["trademarks"])

    checks_run.append("spam_risk")
    if subject == subject.upper() or subject.count("!") > 1:
        return ComplianceResult(
            passed=False,
            failed_check="spam_risk",
            failure_reason="Subject line reads like spam",
            checks_run=checks_run,
        )

    if len(subject) > platform["subject_max_chars"]:
        return ComplianceResult(
            passed=False,
            failed_check="spam_risk",
            failure_reason=f"Subject line exceeds {platform['subject_max_chars']} characters",
            checks_run=checks_run,
        )

    if len(preview_text) > platform["preview_max_chars"]:
        return ComplianceResult(
            passed=False,
            failed_check="spam_risk",
            failure_reason=f"Preview text exceeds {platform['preview_max_chars']} characters",
            checks_run=checks_run,
        )

    checks_run.append("body_length")
    if len(corrected_body) < platform["min_body_chars"] or len(corrected_body) > platform["max_body_chars"]:
        return ComplianceResult(
            passed=False,
            failed_check="body_length",
            failure_reason=(
                f"Newsletter body must be between {platform['min_body_chars']} and "
                f"{platform['max_body_chars']} characters"
            ),
            checks_run=checks_run,
        )

    return ComplianceResult(
        passed=True,
        corrected_content=corrected_body,
        checks_run=checks_run,
    )
