from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient


templates = Jinja2Templates(directory="app/web/templates")


def _client():
    app = FastAPI()

    @app.get("/repurposing")
    def repurposing_page(request: Request):
        return templates.TemplateResponse(
            request,
            "repurposing.html",
            {
                "page": "repurposing",
                "sources": [
                    {
                        "title": "Pressure Performance",
                        "source_kind": "manual",
                        "channel": "linkedin",
                    }
                ],
                "derivatives": [
                    {
                        "title": "LinkedIn draft",
                        "channel": "linkedin",
                        "status": "manual_ready",
                        "content": "Repurposed content body that is long enough to render a preview.",
                    }
                ],
            },
        )

    return TestClient(app, raise_server_exceptions=False)


def test_repurposing_page_renders_sources_and_derivatives():
    response = _client().get("/repurposing")

    assert response.status_code == 200
    assert "Repurposing Engine" in response.text
    assert "Pressure Performance" in response.text
    assert "LinkedIn draft" in response.text
