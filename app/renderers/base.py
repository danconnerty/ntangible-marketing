from dataclasses import dataclass, field


@dataclass
class RenderedAsset:
    asset_role: str
    storage_path: str
    url: str
    mime_type: str = "image/png"


@dataclass
class CanvaRenderRequest:
    template_family: str
    brand_mode: str
    canva_template_id: str
    text_fields: dict[str, str]
    numeric_fields: dict[str, str | int | float]
    image_references: list[str]
    output_dimensions: dict[str, int] | None = None
    output_asset_roles: list[str] = field(default_factory=list)
    title: str | None = None


@dataclass
class CanvaRenderResult:
    success: bool
    assets: list[RenderedAsset] = field(default_factory=list)
    provider_job_id: str | None = None
    design_id: str | None = None
    design_url: str | None = None
    error: str | None = None


class BaseCanvaRenderer:
    def render(self, request: CanvaRenderRequest) -> CanvaRenderResult:
        raise NotImplementedError
