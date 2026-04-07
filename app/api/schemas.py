from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    content_type: str
    pillar: str
    claims: list[str] = Field(default_factory=list)
    context: str | None = None


class ResolveRequest(BaseModel):
    outcome: str
    tweet_url: str | None = None
    tweet_id: str | None = None
