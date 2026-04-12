from pydantic import BaseModel, Field


class PromptConfig(BaseModel):
    system_prompt_additions: str = ""
    tone_notes: str = ""
    example_angles: list[str] = Field(default_factory=list)


class RetrievalConfig(BaseModel):
    approved_example_ids: list[str] = Field(default_factory=list)
    rejected_example_ids: list[str] = Field(default_factory=list)
    max_examples: int = 5
    filter_by_pillar: bool = False
    filter_by_intent: bool = False
    include_campaign_context: bool = True
    include_revenue_context: bool = True
    include_market_signals: bool = True
    campaign_context_fields: list[str] = Field(default_factory=list)
    revenue_context_fields: list[str] = Field(default_factory=list)


class FormattingConfig(BaseModel):
    platform_rules_override: dict | None = None
    max_hashtags: int | None = None
    max_chars: int | None = None
    require_subject_line: bool = False
    max_sections: int | None = None


class RoutingConfig(BaseModel):
    target_pillar: str | None = None
    target_intent: str | None = None
    target_content_type: str | None = None
    target_audience_segment: str | None = None


class TimingConfig(BaseModel):
    recommended_post_hour_utc: int | None = None
    publish_delay_minutes: int = 0


class AssetConfig(BaseModel):
    asset_instructions: str = ""
    require_image: bool = False
    image_style_notes: str = ""


class CtaConfig(BaseModel):
    cta_preferences: list[str] = Field(default_factory=list)
    cta_rules: str = ""


class WorkflowVersionConfig(BaseModel):
    prompt: PromptConfig = Field(default_factory=PromptConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    formatting: FormattingConfig = Field(default_factory=FormattingConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    timing: TimingConfig = Field(default_factory=TimingConfig)
    assets: AssetConfig = Field(default_factory=AssetConfig)
    cta: CtaConfig = Field(default_factory=CtaConfig)
