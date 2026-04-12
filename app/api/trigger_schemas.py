from typing import Any

from pydantic import BaseModel, Field


class PartnerWebhookRequest(BaseModel):
    event_type: str
    external_event_id: str
    athlete_name: str | None = None
    commitment_school: str | None = None
    offer_school: str | None = None
    position: str | None = None
    score: int | None = None
    score_tier: str | None = None
    event_name: str | None = None
    registration_deadline: str | None = None
    milestone_name: str | None = None
    milestone_value: int | str | None = None
    athlete_count: int | None = None
    top_performers: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
