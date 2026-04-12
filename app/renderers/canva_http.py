import time

import httpx

from app.config import get_settings
from app.renderers.base import BaseCanvaRenderer, CanvaRenderRequest, CanvaRenderResult, RenderedAsset


class HttpCanvaRenderer(BaseCanvaRenderer):
    def __init__(self):
        settings = get_settings()
        self.client = httpx.Client(
            base_url="https://api.canva.com/rest/v1",
            headers={
                "Authorization": f"Bearer {settings.canva_api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def _build_autofill_payload(self, request: CanvaRenderRequest) -> dict:
        data: dict[str, dict] = {}
        for key, value in request.text_fields.items():
            data[key] = {"type": "text", "text": value}
        for key, value in request.numeric_fields.items():
            data[key] = {"type": "text", "text": str(value)}
        return {
            "brand_template_id": request.canva_template_id,
            "title": request.title or request.template_family.replace("_", " ").title(),
            "data": data,
        }

    def render(self, request: CanvaRenderRequest) -> CanvaRenderResult:
        if not request.canva_template_id:
            return CanvaRenderResult(success=False, error="Missing Canva brand template id")

        autofill_response = self.client.post("/autofills", json=self._build_autofill_payload(request))
        if not autofill_response.is_success:
            return CanvaRenderResult(success=False, error=f"{autofill_response.status_code}: {autofill_response.text}")

        autofill_job = autofill_response.json().get("job", {})
        autofill_job_id = autofill_job.get("id")
        design_id = None

        for _ in range(5):
            job_response = self.client.get(f"/autofills/{autofill_job_id}")
            if not job_response.is_success:
                return CanvaRenderResult(success=False, provider_job_id=autofill_job_id, error=job_response.text)
            job = job_response.json().get("job", {})
            if job.get("status") == "success":
                design_id = job.get("result", {}).get("design", {}).get("id")
                break
            if job.get("status") == "failed":
                return CanvaRenderResult(
                    success=False,
                    provider_job_id=autofill_job_id,
                    error=job.get("error", {}).get("message", "Canva autofill failed"),
                )
            time.sleep(1)

        if not design_id:
            return CanvaRenderResult(success=False, provider_job_id=autofill_job_id, error="Canva autofill timed out")

        format_payload: dict[str, object] = {"type": "png", "lossless": True}
        if request.output_dimensions:
            format_payload.update(request.output_dimensions)
        export_response = self.client.post("/exports", json={"design_id": design_id, "format": format_payload})
        if not export_response.is_success:
            return CanvaRenderResult(success=False, provider_job_id=autofill_job_id, error=export_response.text)

        export_job_id = export_response.json().get("job", {}).get("id")
        export_urls: list[str] = []
        for _ in range(5):
            status_response = self.client.get(f"/exports/{export_job_id}")
            if not status_response.is_success:
                return CanvaRenderResult(success=False, provider_job_id=export_job_id, error=status_response.text)
            job = status_response.json().get("job", {})
            if job.get("status") == "success":
                export_urls = job.get("urls", [])
                break
            if job.get("status") == "failed":
                return CanvaRenderResult(
                    success=False,
                    provider_job_id=export_job_id,
                    error=job.get("error", {}).get("message", "Canva export failed"),
                )
            time.sleep(1)

        if not export_urls:
            return CanvaRenderResult(success=False, provider_job_id=export_job_id, error="Canva export timed out")

        roles = request.output_asset_roles or [f"asset_{index + 1}" for index in range(len(export_urls))]
        assets = [
            RenderedAsset(
                asset_role=roles[index] if index < len(roles) else f"asset_{index + 1}",
                storage_path=url,
                url=url,
            )
            for index, url in enumerate(export_urls)
        ]
        return CanvaRenderResult(
            success=True,
            assets=assets,
            provider_job_id=export_job_id,
            design_id=design_id,
            design_url=f"https://www.canva.com/design/{design_id}/edit",
        )
