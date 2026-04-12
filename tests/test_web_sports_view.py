from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient


templates = Jinja2Templates(directory="app/web/templates")


def _client():
    app = FastAPI()

    @app.get("/sports")
    def sports_page(request: Request):
        return templates.TemplateResponse(
            request,
            "sports.html",
            {
                "page": "sports",
                "windows": [
                    {
                        "slug": "womens-summer-signing-window",
                        "title": "Signing Day Window",
                        "sport": "multi-sport",
                        "window_type": "signing_day",
                        "start_date": "2026-04-01",
                        "end_date": "2026-04-30",
                        "summary": "Celebrate signings with proof-first framing.",
                        "stage_angle": "Make the athlete feel seen.",
                        "default_platforms": ["linkedin", "instagram"],
                    }
                ],
                "calendar_days": [
                    {
                        "label": "Apr 01",
                        "weekday": "Wed",
                        "windows": [
                            {
                                "title": "Signing Day Window",
                            }
                        ],
                    }
                ],
            },
        )

    return TestClient(app, raise_server_exceptions=False)


def test_sports_page_renders_window_and_calendar_sections():
    response = _client().get("/sports")

    assert response.status_code == 200
    assert "Sports Calendar" in response.text
    assert "Signing Day Window" in response.text
    assert "Rolling 4-Week View" in response.text
    assert "Stage Window" in response.text
