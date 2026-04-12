import json
from datetime import date, datetime, timedelta

from unittest.mock import patch
from fastapi.testclient import TestClient

import app.web.routes as web_routes
from app.main import app


def _make_empty_calendar_data():
    today = date.today()
    anchor = today
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    month_start = date(today.year, today.month, 1)
    prev_month = (month_start - timedelta(days=1)).replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)

    month_days = []
    grid_start = month_start - timedelta(days=month_start.weekday())
    for i in range(42):
        d = grid_start + timedelta(days=i)
        month_days.append({
            "date": d.isoformat(),
            "day": d.day,
            "weekday": d.strftime("%a"),
            "label": d.strftime("%b %d"),
            "full_label": d.strftime("%A, %B %d, %Y"),
            "is_today": d == today,
            "is_current_month": d.month == today.month,
            "is_weekend": d.weekday() >= 5,
            "items": [],
        })

    week_days = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        week_days.append({
            "date": d.isoformat(),
            "day": d.day,
            "weekday_short": d.strftime("%a"),
            "weekday_full": d.strftime("%A"),
            "label": d.strftime("%b %d"),
            "full_label": d.strftime("%A, %B %d, %Y"),
            "is_today": d == today,
            "is_weekend": d.weekday() >= 5,
            "items": [],
        })

    hours = []
    for h in range(24):
        hours.append({
            "hour": h,
            "label": f"{h:02d}:00" if h > 0 else "12 AM",
            "label_12": datetime(2000, 1, 1, h).strftime("%I %p").lstrip("0"),
            "items": [],
        })

    return {
        "anchor": anchor.isoformat(),
        "today": today.isoformat(),
        "month_label": anchor.strftime("%B %Y"),
        "week_label": f"{week_start.strftime('%b %d')} – {(week_end - timedelta(days=1)).strftime('%b %d, %Y')}",
        "day_label": anchor.strftime("%A, %B %d, %Y"),
        "month_days": month_days,
        "week_days": week_days,
        "day_hours": hours,
        "day_items": [],
        "nav": {
            "prev_month": prev_month.isoformat(),
            "next_month": next_month.isoformat(),
            "prev_week": (week_start - timedelta(days=7)).isoformat(),
            "next_week": (week_start + timedelta(days=7)).isoformat(),
            "prev_day": (today - timedelta(days=1)).isoformat(),
            "next_day": (today + timedelta(days=1)).isoformat(),
            "today": today.isoformat(),
        },
        "partner_sources": [],
        "items_json": "{}",
    }


def test_calendar_view_renders_month_view():
    with patch.object(web_routes, "load_calendar_view_data", return_value=_make_empty_calendar_data()):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/control-room/calendar")
    assert response.status_code == 200
    body = response.text
    assert "Calendar" in body
    assert "Month" in body
    assert "Week" in body
    assert "Day" in body


def test_calendar_view_renders_week_view():
    with patch.object(web_routes, "load_calendar_view_data", return_value=_make_empty_calendar_data()):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/control-room/calendar?view=week")
    assert response.status_code == 200
    assert "gcal-week-wrap" in response.text


def test_calendar_view_renders_day_view():
    with patch.object(web_routes, "load_calendar_view_data", return_value=_make_empty_calendar_data()):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/control-room/calendar?view=day")
    assert response.status_code == 200
    assert "gcal-day-wrap" in response.text


def test_calendar_view_has_workflow_wizard():
    with patch.object(web_routes, "load_calendar_view_data", return_value=_make_empty_calendar_data()):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/control-room/calendar")
    assert response.status_code == 200
    assert "workflowWizard" in response.text
    assert "gcal-wizard-panel" in response.text


def test_calendar_view_shows_events():
    data = _make_empty_calendar_data()
    today = date.today()
    # Add an event to today
    for day in data["month_days"]:
        if day["date"] == today.isoformat():
            day["items"] = [{
                "type": "rule",
                "platform": "linkedin",
                "title": "LinkedIn Thought Leadership",
                "time": "09:00",
                "time_label": "9:00 AM",
                "status": "recurring",
                "detail": "Every Tue 9:00 AM",
                "content": "",
            }]
            break

    with patch.object(web_routes, "load_calendar_view_data", return_value=data):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/control-room/calendar")
    assert response.status_code == 200
    assert "LinkedIn Thought Leadership" in response.text
    assert "9:00 AM" in response.text
