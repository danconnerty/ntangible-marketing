import uuid
from datetime import date
from types import SimpleNamespace

from app.models.brain import KnowledgeNode
from app.models.workflow import Platform
from app.services.sports_calendar_service import SportsCalendarService
from data.sports_calendar import get_calendar_window, rolling_calendar_days


class FakeDB:
    def __init__(self):
        self.added = []
        self.flush_count = 0

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flush_count += 1


def test_macro_sports_calendar_helpers_expose_key_windows():
    window = get_calendar_window("womens-summer-signing-window")
    assert window is not None
    assert window.title == "Signing Day Window"
    assert window.default_platforms == ("linkedin", "instagram")

    days = rolling_calendar_days(days=7, anchor=date(2026, 4, 1))
    assert len(days) == 7
    assert days[0]["is_today"] is True


def test_list_calendar_window_returns_event_feed():
    service = SportsCalendarService(FakeDB())

    events = service.list_calendar_window(days=45, anchor=date(2026, 4, 1))

    assert any(event["event_name"] == "Signing Day Window" for event in events)
    assert all("start_at" in event and "event_type" in event for event in events)


def test_stage_window_creates_workflow_jobs_and_stage_runs(monkeypatch):
    fake_db = FakeDB()
    service = SportsCalendarService(fake_db)
    workflow = SimpleNamespace(id=uuid.uuid4(), slug="sports-signing-day-linkedin", name="Signing Day LinkedIn")
    job = SimpleNamespace(id=uuid.uuid4(), status="completed")
    draft = SimpleNamespace(id=uuid.uuid4(), content="LinkedIn draft body")
    captured = {}

    def fake_ensure_workflow(request):
        captured["request"] = request
        return workflow, SimpleNamespace(id=uuid.uuid4(), version_number=1)

    def fake_create_manual_request(context, workflow_id):
        captured["manual_request"] = {"context": context, "workflow_id": workflow_id}
        return SimpleNamespace(id=uuid.uuid4(), source_payload={"request": context})

    monkeypatch.setattr(service.trigger_engine, "ensure_workflow", fake_ensure_workflow)
    monkeypatch.setattr(service.trigger_engine, "create_manual_request", fake_create_manual_request)
    monkeypatch.setattr(service.workflow_engine, "execute", lambda trigger: job)
    monkeypatch.setattr(service, "_first_draft_for_job", lambda content_job_id: draft)

    result = service.stage_window(
        "womens-summer-signing-window",
        actor="planner",
        platforms=["linkedin"],
        note="Lead with proof.",
    )

    assert result["window_title"] == "Signing Day Window"
    assert result["runs"][0]["platform"] == Platform.LINKEDIN.value
    assert result["runs"][0]["content"] == "LinkedIn draft body"
    assert captured["request"].workflow_slug == "sports-womens-summer-signing-window-linkedin"
    assert captured["manual_request"]["workflow_id"] == workflow.id
    assert any(isinstance(run, KnowledgeNode) and (run.metadata_ or {}).get("run_type") == "sports_stage" for run in fake_db.added)
