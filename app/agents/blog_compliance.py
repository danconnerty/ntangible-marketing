from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


@dataclass
class BlogComplianceResult:
    passed: bool
    failed_check: str | None = None
    failure_reason: str | None = None
    corrected_body_markdown: str | None = None
    checks_run: list[str] = field(default_factory=list)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def run_blog_compliance_checks(draft: dict[str, Any]) -> BlogComplianceResult:
    checks_run: list[str] = []
    title = (draft.get("title") or "").strip()
    meta_description = (draft.get("meta_description") or "").strip()
    body_markdown = (draft.get("body_markdown") or "").strip()
    target_keywords = [keyword.strip().lower() for keyword in draft.get("target_keywords", []) if keyword]
    headings = draft.get("headings") or []

    checks_run.append("required_fields")
    if not title or not meta_description or not body_markdown:
        return BlogComplianceResult(
            passed=False,
            failed_check="required_fields",
            failure_reason="Missing title, meta description, or body content",
            checks_run=checks_run,
        )

    checks_run.append("word_count")
    word_count = _word_count(body_markdown)
    if word_count < 800 or word_count > 1500:
        return BlogComplianceResult(
            passed=False,
            failed_check="word_count",
            failure_reason=f"Blog draft is {word_count} words (must be between 800 and 1500)",
            checks_run=checks_run,
        )

    checks_run.append("meta_description")
    if len(meta_description) < 120 or len(meta_description) > 170:
        return BlogComplianceResult(
            passed=False,
            failed_check="meta_description",
            failure_reason="Meta description must be between 120 and 170 characters",
            checks_run=checks_run,
        )

    checks_run.append("headings")
    if len(headings) < 3:
        return BlogComplianceResult(
            passed=False,
            failed_check="headings",
            failure_reason="Blog draft needs at least 3 H2 headings",
            checks_run=checks_run,
        )

    checks_run.append("keywords")
    haystack = " ".join([title, meta_description, body_markdown]).lower()
    missing_keywords = [keyword for keyword in target_keywords if keyword not in haystack]
    if missing_keywords:
        return BlogComplianceResult(
            passed=False,
            failed_check="keywords",
            failure_reason=f"Missing target keyword(s): {', '.join(missing_keywords)}",
            checks_run=checks_run,
        )

    checks_run.append("cta")
    if "cta:" not in body_markdown.lower():
        return BlogComplianceResult(
            passed=False,
            failed_check="cta",
            failure_reason="Blog draft needs a clear CTA section",
            checks_run=checks_run,
        )

    return BlogComplianceResult(
        passed=True,
        corrected_body_markdown=body_markdown,
        checks_run=checks_run,
    )

