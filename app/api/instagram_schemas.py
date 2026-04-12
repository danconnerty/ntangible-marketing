from pydantic import BaseModel, Field


class InstagramGenerateRequest(BaseModel):
    content_type: str
    pillar: str
    approval_tier: str = "tier_1"
    claims: list[str] = Field(default_factory=list)
    context: str | None = None
    partner_name: str | None = None
    source_event_type: str | None = None
    canva_template_id: str | None = None
    publish_mode: str | None = None
