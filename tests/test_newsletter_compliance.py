from app.agents.newsletter_compliance import run_newsletter_compliance_checks


def _draft(**overrides):
    draft = {
        "segment": "coaches_front_offices",
        "subject": "Pressure data coaches should actually use",
        "preview_text": "What the April NTangible dataset changed.",
        "hook": "Most recruiting misses start before film settles the board.",
        "proof_point": "Alliance coaches used pressure profiles to separate late evaluations.",
        "product_update": "Workflow previews now include rejected examples before activation.",
        "cta": "Reply to book a workflow review.",
        "body_markdown": (
            "## Hook\nMost recruiting misses start before film settles the board.\n\n"
            "## Proof\nAlliance coaches used pressure profiles to separate late evaluations.\n\n"
            "## Update\nWorkflow previews now include rejected examples before activation.\n\n"
            "## CTA\nReply to book a workflow review."
        ),
    }
    draft.update(overrides)
    return draft


def test_newsletter_compliance_rejects_missing_required_sections():
    result = run_newsletter_compliance_checks(
        _draft(
            hook="",
            proof_point="",
            product_update="",
            cta="",
        )
    )

    assert result.passed is False
    assert result.failed_check == "required_sections"


def test_newsletter_compliance_rejects_spammy_subject():
    result = run_newsletter_compliance_checks(
        _draft(subject="APRIL UPDATE!!!")
    )

    assert result.passed is False
    assert result.failed_check == "spam_risk"


def test_newsletter_compliance_accepts_valid_draft():
    result = run_newsletter_compliance_checks(_draft())

    assert result.passed is True
    assert result.corrected_content is not None
    assert "required_sections" in result.checks_run
