"""Normalize and route partner events into trigger requests for the workflow engine."""

from dataclasses import dataclass, field
from enum import Enum

from app.config import get_brand_voice
from app.models.workflow import Platform


class PartnerEventType(str, Enum):
    ASSESSMENT_COMPLETED = "assessment_completed"
    COMMITMENT_UPDATE = "commitment_update"
    OFFER_UPDATE = "offer_update"
    MILESTONE_REACHED = "milestone_reached"
    LEADERBOARD_PUBLISHED = "leaderboard_published"
    BIG_EVENT_HYPE = "big_event_hype"
    REGISTRATION_PUSH = "registration_push"
    EVENT_PROMOTION = "event_promotion"


@dataclass(frozen=True)
class NormalizedPartnerEvent:
    partner_slug: str
    partner_name: str
    event_type: str
    external_event_id: str
    payload: dict


@dataclass(frozen=True)
class TriggerRequest:
    partner_slug: str
    event_type: str
    platform: Platform
    workflow_slug: str
    content_type: str
    pillar: str
    context: str
    dynamic_value_groups: list[list[str]] = field(default_factory=list)
    approval_tier: str = "tier_1"

    def as_generation_payload(self) -> dict:
        return {
            "content_type": self.content_type,
            "pillar": self.pillar,
            "claims": [],
            "context": self.context,
            "dynamic_value_groups": self.dynamic_value_groups,
            "approval_tier": self.approval_tier,
        }


def _display_name_from_slug(partner_slug: str) -> str:
    return partner_slug.replace("_", " ").replace("-", " ").title()


def _score_tier(event: NormalizedPartnerEvent) -> str | None:
    score_tier = event.payload.get("score_tier")
    if score_tier:
        return score_tier

    score = event.payload.get("score")
    if score is None:
        return None
    if score >= 850:
        return "Elite"
    if score >= 800:
        return "Gold"
    if score >= 750:
        return "Silver"
    return "Developing"


def _score_is_publishable(event: NormalizedPartnerEvent) -> bool:
    score = event.payload.get("score")
    if score is None:
        return False

    score_rules = get_brand_voice()["score_publishing"]
    if event.event_type in {
        PartnerEventType.LEADERBOARD_PUBLISHED.value,
        PartnerEventType.MILESTONE_REACHED.value,
    } and score_rules["allow_aggregate_full_range"]:
        return True
    return int(score) >= int(score_rules["min_threshold"])


def _dynamic_value_groups(event: NormalizedPartnerEvent) -> list[list[str]]:
    groups: list[list[str]] = []
    payload = event.payload

    if payload.get("athlete_count") is not None:
        groups.append([str(payload["athlete_count"])])
    if payload.get("milestone_value") is not None:
        groups.append([str(payload["milestone_value"])])
    if _score_is_publishable(event):
        groups.append([str(payload["score"])])

    for performer in payload.get("top_performers", []):
        if performer.get("score") is not None:
            groups.append([str(performer["score"])])

    return groups


def normalize_partner_event(partner_slug: str, raw_payload: dict) -> NormalizedPartnerEvent:
    """Normalize a raw partner event payload into a canonical shape."""
    event_type = raw_payload.get("event_type")
    external_event_id = raw_payload.get("external_event_id")
    if not event_type:
        raise ValueError("event_type is required")
    if not external_event_id:
        raise ValueError("external_event_id is required")

    normalized_event_type = PartnerEventType(event_type).value
    return NormalizedPartnerEvent(
        partner_slug=partner_slug,
        partner_name=raw_payload.get("partner_name") or _display_name_from_slug(partner_slug),
        event_type=normalized_event_type,
        external_event_id=external_event_id,
        payload=raw_payload,
    )


def _x_content_type_for(event_type: str) -> str:
    if event_type == PartnerEventType.BIG_EVENT_HYPE.value:
        return "trend_jack"
    return "data_drop"


def _linkedin_content_type_for(event_type: str) -> str:
    if event_type in {
        PartnerEventType.LEADERBOARD_PUBLISHED.value,
        PartnerEventType.MILESTONE_REACHED.value,
        PartnerEventType.ASSESSMENT_COMPLETED.value,
    }:
        return "data_insight"
    return "company_update"


def _build_commitment_requests(event: NormalizedPartnerEvent) -> list[TriggerRequest]:
    """Route a commitment_update event to X only."""
    payload = event.payload
    athlete = payload.get("athlete_name", "Unknown athlete")
    school = payload.get("commitment_school") or payload.get("offer_school") or "Unknown school"
    position = payload.get("position", "Unknown position")
    score_tier = _score_tier(event)

    context_parts = [
        f"Partner commitment update from {event.partner_name}.",
        f"Athlete: {athlete}.",
        f"School: {school}.",
        f"Position: {position}.",
    ]
    if score_tier:
        context_parts.append(f"Use the athlete's Clutch Factor™ tier: {score_tier}.")
    context_parts.append("Do not invent extra statistics or coach quotes.")

    requests = [
        TriggerRequest(
            partner_slug=event.partner_slug,
            event_type=event.event_type,
            platform=Platform.X,
            workflow_slug=f"partner-{event.partner_slug}-{event.event_type}-{Platform.X.value}".replace("_", "-"),
            content_type="data_drop",
            pillar="client_proof",
            context=" ".join(context_parts),
            dynamic_value_groups=[],
        )
    ]
    if event.event_type == PartnerEventType.OFFER_UPDATE.value:
        requests.append(
            TriggerRequest(
                partner_slug=event.partner_slug,
                event_type=event.event_type,
                platform=Platform.INSTAGRAM,
                workflow_slug=f"partner-{event.partner_slug}-{event.event_type}-{Platform.INSTAGRAM.value}".replace("_", "-"),
                content_type="partner_content",
                pillar="client_proof",
                context=" ".join(context_parts),
                dynamic_value_groups=[],
            )
        )
    else:
        requests.append(
            TriggerRequest(
                partner_slug=event.partner_slug,
                event_type=event.event_type,
                platform=Platform.INSTAGRAM,
                workflow_slug=f"partner-{event.partner_slug}-{event.event_type}-{Platform.INSTAGRAM.value}".replace("_", "-"),
                content_type="partner_content",
                pillar="client_proof",
                context=" ".join(context_parts),
                dynamic_value_groups=[],
            )
        )
    return requests


def _build_multi_platform_requests(event: NormalizedPartnerEvent) -> list[TriggerRequest]:
    payload = event.payload
    dynamic_groups = _dynamic_value_groups(event)
    event_name = payload.get("event_name", "Upcoming event")
    athlete_count = payload.get("athlete_count", "unknown")
    milestone_name = payload.get("milestone_name", "Milestone")
    milestone_value = payload.get("milestone_value", "unknown")
    performers = ", ".join(
        f"{performer.get('athlete_name', 'Unknown athlete')} ({performer.get('score', 'n/a')})"
        for performer in payload.get("top_performers", [])
    )

    if event.event_type == PartnerEventType.LEADERBOARD_PUBLISHED.value:
        context = (
            f"Partner leaderboard update from {event.partner_name}. "
            f"Event: {event_name}. Athletes in field: {athlete_count}. "
            f"Top performers: {performers}. Focus on pressure-performance data and event relevance."
        )
    elif event.event_type == PartnerEventType.MILESTONE_REACHED.value:
        context = (
            f"Partner milestone from {event.partner_name}. "
            f"Milestone: {milestone_name}. Value: {milestone_value}. "
            f"Event context: {event_name}. Use this as partner proof and a data-backed momentum story."
        )
    elif event.event_type == PartnerEventType.BIG_EVENT_HYPE.value:
        context = (
            f"Pre-event hype for {event.partner_name}. Event: {event_name}. "
            f"Athletes competing: {athlete_count}. Highlight the scale of the partner dataset and why this event matters."
        )
    elif event.event_type in {
        PartnerEventType.REGISTRATION_PUSH.value,
        PartnerEventType.EVENT_PROMOTION.value,
    }:
        registration_deadline = payload.get("registration_deadline", "unknown")
        context = (
            f"Partner event promotion from {event.partner_name}. "
            f"Event: {event_name}. Registration deadline: {registration_deadline}. "
            "Drive action without sounding generic and make the event feel timely."
        )
    else:
        context_parts = [
            f"Partner assessment update from {event.partner_name}.",
            f"Athlete: {payload.get('athlete_name', 'Unknown athlete')}.",
        ]
        score_tier = _score_tier(event)
        if score_tier:
            context_parts.append(f"Clutch Factor™ tier: {score_tier}.")
        if _score_is_publishable(event):
            context_parts.append(f"Exact Clutch Factor™ score available: {payload['score']}.")
        context_parts.append("Keep the angle data-backed and partner-specific.")
        context = " ".join(context_parts)

    return [
        TriggerRequest(
            partner_slug=event.partner_slug,
            event_type=event.event_type,
            platform=Platform.X,
            workflow_slug=f"partner-{event.partner_slug}-{event.event_type}-{Platform.X.value}".replace("_", "-"),
            content_type=_x_content_type_for(event.event_type),
            pillar="client_proof",
            context=context,
            dynamic_value_groups=dynamic_groups,
        ),
        TriggerRequest(
            partner_slug=event.partner_slug,
            event_type=event.event_type,
            platform=Platform.LINKEDIN,
            workflow_slug=f"partner-{event.partner_slug}-{event.event_type}-{Platform.LINKEDIN.value}".replace("_", "-"),
            content_type=_linkedin_content_type_for(event.event_type),
            pillar="client_proof",
            context=context,
            dynamic_value_groups=dynamic_groups,
        ),
        TriggerRequest(
            partner_slug=event.partner_slug,
            event_type=event.event_type,
            platform=Platform.INSTAGRAM,
            workflow_slug=f"partner-{event.partner_slug}-{event.event_type}-{Platform.INSTAGRAM.value}".replace("_", "-"),
            content_type="partner_content",
            pillar="client_proof",
            context=context,
            dynamic_value_groups=dynamic_groups,
        ),
    ]


EVENT_ROUTERS = {
    PartnerEventType.COMMITMENT_UPDATE.value: _build_commitment_requests,
    PartnerEventType.OFFER_UPDATE.value: _build_commitment_requests,
    PartnerEventType.ASSESSMENT_COMPLETED.value: _build_multi_platform_requests,
    PartnerEventType.MILESTONE_REACHED.value: _build_multi_platform_requests,
    PartnerEventType.LEADERBOARD_PUBLISHED.value: _build_multi_platform_requests,
    PartnerEventType.BIG_EVENT_HYPE.value: _build_multi_platform_requests,
    PartnerEventType.REGISTRATION_PUSH.value: _build_multi_platform_requests,
    PartnerEventType.EVENT_PROMOTION.value: _build_multi_platform_requests,
}


def build_trigger_requests(event: NormalizedPartnerEvent) -> list[TriggerRequest]:
    """Route a normalized partner event to one or more trigger requests."""
    router = EVENT_ROUTERS.get(event.event_type)
    if not router:
        raise ValueError(f"No router for event type: {event.event_type}")
    return router(event)
