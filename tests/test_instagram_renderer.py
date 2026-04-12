from app.renderers.base import CanvaRenderRequest
from app.renderers.canva_factory import get_canva_renderer
from app.renderers.canva_mock import MockCanvaRenderer


def test_canva_factory_defaults_to_mock(monkeypatch):
    monkeypatch.setenv("CANVA_RENDERER", "mock")
    renderer = get_canva_renderer()
    assert isinstance(renderer, MockCanvaRenderer)


def test_mock_canva_renderer_returns_ordered_carousel_assets(tmp_path, monkeypatch):
    monkeypatch.setenv("RENDERED_ASSET_ROOT", str(tmp_path))
    renderer = MockCanvaRenderer()

    result = renderer.render(
        CanvaRenderRequest(
            template_family="education_carousel",
            brand_mode="owned",
            canva_template_id="tmpl-123",
            text_fields={"headline": "Pressure reveals preparation."},
            numeric_fields={},
            image_references=[],
            output_dimensions={"width": 1080, "height": 1350},
            output_asset_roles=["slide_1", "slide_2", "slide_3", "slide_4", "slide_5"],
        )
    )

    assert result.success is True
    assert [asset.asset_role for asset in result.assets] == [
        "slide_1",
        "slide_2",
        "slide_3",
        "slide_4",
        "slide_5",
    ]
    assert result.assets[0].storage_path.endswith(".png")
