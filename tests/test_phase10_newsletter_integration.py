from app.models.workflow import Platform
from app.services.platform_generation import PlatformGenerationService


class _Workflow:
    platform = Platform.NEWSLETTER


class _Version:
    config = {}


def test_platform_generation_supports_newsletter(monkeypatch):
    payload = {
        "content_type": "monthly_newsletter",
        "pillar": "thought_leadership",
        "claims": [],
        "context": "April recruiting pressure data",
        "workflow_version_config": {
            "routing": {
                "target_audience_segment": "coaches_front_offices",
            }
        },
    }

    monkeypatch.setattr(
        "app.services.platform_generation.generate_newsletter_draft",
        lambda content_type, pillar, claims, context, segment: (
            {
                "segment": segment,
                "subject": "April pressure data coaches should use",
                "preview_text": "What the latest dataset changed.",
                "hook": "Most recruiting misses happen before film catches up.",
                "proof_point": "Alliance coaches separated late evaluations earlier.",
                "product_update": "Workflow previews now show rejected examples.",
                "cta": "Reply to book a demo.",
                "body_markdown": (
                    "Most recruiting misses happen before film catches up. "
                    "Alliance coaches separated late evaluations earlier by pairing pressure profiles "
                    "with existing board work. Workflow previews now show rejected examples before activation, "
                    "which gives staff a cleaner view of what to avoid next month. Reply to book a demo."
                ),
                "body_html": (
                    "<p>Most recruiting misses happen before film catches up. "
                    "Alliance coaches separated late evaluations earlier by pairing pressure profiles "
                    "with existing board work. Workflow previews now show rejected examples before activation, "
                    "which gives staff a cleaner view of what to avoid next month. Reply to book a demo.</p>"
                ),
            },
            {"response": {"raw_text": "{}"}, "prompt_snapshot": "snapshot"},
        ),
    )

    candidates = PlatformGenerationService(None).generate(_Workflow(), _Version(), payload)

    assert len(candidates) == 1
    assert "Most recruiting misses happen" in candidates[0].content
    assert candidates[0].hashtags == []
    assert candidates[0].compliance_result["segment"] == "coaches_front_offices"
    assert candidates[0].compliance_result["subject"].startswith("April pressure data")
