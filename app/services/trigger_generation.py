from dataclasses import dataclass

from app.agents.compliance import run_compliance_checks
from app.agents.content_writer import generate_tweets
from app.agents.linkedin_compliance import run_linkedin_compliance_checks
from app.agents.linkedin_writer import generate_linkedin_post
from app.models.workflow import Platform


@dataclass(frozen=True)
class GeneratedTriggerDraft:
    platform: Platform
    content: str
    hashtags: list[str]
    compliance_result: dict
    prompt_snapshot: str
    generation_trace: dict
    platform_post_id: str | None = None
    post_url: str | None = None
    published_at: str | None = None
    failure_reason: str | None = None


def _generate_x_draft(request) -> GeneratedTriggerDraft:
    variations, log_data = generate_tweets(
        content_type=request.content_type,
        pillar=request.pillar,
        claims=[],
        context=request.context,
    )
    if not variations:
        raise ValueError("No valid X variations generated")

    for variation in variations:
        compliance_result = run_compliance_checks(
            variation,
            requested_claims=[],
            dynamic_value_groups=request.dynamic_value_groups,
        )
        if compliance_result.passed:
            return GeneratedTriggerDraft(
                platform=Platform.X,
                content=compliance_result.corrected_content or variation["content"],
                hashtags=compliance_result.corrected_hashtags,
                compliance_result={
                    "passed": True,
                    "checks_run": compliance_result.checks_run,
                },
                prompt_snapshot=log_data["prompt_snapshot"],
                generation_trace=log_data["response"],
            )

    raise ValueError("No X variations passed compliance")


def _generate_linkedin_draft(request) -> GeneratedTriggerDraft:
    generated, log_data = generate_linkedin_post(
        content_type=request.content_type,
        pillar=request.pillar,
        claims=[],
        context=request.context,
    )
    compliance_result = run_linkedin_compliance_checks(
        generated,
        requested_claims=[],
        dynamic_value_groups=request.dynamic_value_groups,
    )
    if not compliance_result.passed:
        raise ValueError(compliance_result.failure_reason or "LinkedIn compliance failed")

    return GeneratedTriggerDraft(
        platform=Platform.LINKEDIN,
        content=compliance_result.corrected_content or generated["content"],
        hashtags=compliance_result.corrected_hashtags,
        compliance_result={
            "passed": True,
            "checks_run": compliance_result.checks_run,
        },
        prompt_snapshot=log_data["prompt_snapshot"],
        generation_trace=log_data["response"],
    )


def generate_trigger_draft(request) -> GeneratedTriggerDraft:
    if request.platform == Platform.X:
        return _generate_x_draft(request)
    if request.platform == Platform.LINKEDIN:
        return _generate_linkedin_draft(request)
    raise ValueError(f"Unsupported trigger platform: {request.platform.value}")
