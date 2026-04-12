from pydantic import BaseModel, Field


class LinkedInGenerateRequest(BaseModel):
    content_type: str
    pillar: str
    approval_tier: str = "tier_1"
    claims: list[str] = Field(default_factory=list)
    context: str | None = None


class LinkedInReviewRequest(BaseModel):
    notes: str | None = None
