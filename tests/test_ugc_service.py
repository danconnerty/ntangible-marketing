import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app.services.ugc_service as ugc_service_module
from app.models.ugc import UGCRequestStatus, UGCSubmissionStatus
from app.services.ugc_service import UGCService


class FakeCanvaRenderer:
    def __init__(self):
        self.calls = []

    def render(self, request):
        self.calls.append(request)
        return SimpleNamespace(
            assets=[
                SimpleNamespace(
                    storage_path="/tmp/score.png",
                    url="https://cdn.example.com/score.png",
                )
            ],
            design_id="design-1",
            provider_job_id="job-1",
        )


def test_create_testimonial_request_requires_threshold():
    db = MagicMock()
    service = UGCService(db)

    with pytest.raises(ValueError, match="at least 750"):
        service.create_testimonial_request(athlete_name="Jane Smith", score=749)


def test_create_testimonial_request_bridges_into_control_room_workflow(monkeypatch):
    db = MagicMock()
    db.add = MagicMock()
    db.flush = MagicMock()
    service = UGCService(db)

    fake_renderer = FakeCanvaRenderer()
    fake_workflow = SimpleNamespace(id=uuid.uuid4(), slug="ugc-testimonial-request-newsletter")
    fake_trigger = SimpleNamespace(id=uuid.uuid4(), trigger_type=None, source_payload={"existing": "payload"})
    fake_job = SimpleNamespace(id=uuid.uuid4(), status="completed", error_message=None)

    monkeypatch.setattr(ugc_service_module, "get_canva_renderer", lambda: fake_renderer)
    monkeypatch.setattr(service.agent, "build_testimonial_request", lambda **kwargs: {
        "subject": f"{kwargs['athlete_name']}, share your clutch story",
        "preview_text": "Certified tier opens the door.",
        "request_copy": "Please send a short testimonial.",
        "athlete_name": kwargs["athlete_name"],
        "athlete_email": kwargs["athlete_email"],
        "parent_name": kwargs["parent_name"],
        "parent_email": kwargs["parent_email"],
        "score": kwargs["score"],
        "score_tier": kwargs["score_tier"],
        "sport": kwargs["sport"],
    })
    monkeypatch.setattr(service, "_resolve_request_workflow", lambda: fake_workflow)
    service.trigger_engine = MagicMock()
    service.trigger_engine.create_manual_request.return_value = fake_trigger
    service.workflow_engine = MagicMock()
    service.workflow_engine.execute.return_value = fake_job

    result = service.create_testimonial_request(
        athlete_name="Jane Smith",
        score=780,
        athlete_email="jane@example.com",
        parent_name="Pat Smith",
        parent_email="pat@example.com",
        athlete_age=17,
        sport="softball",
        context="Alliance Fastpitch assessment",
        source_partner="alliance_fastpitch",
    )

    assert result["status"] == UGCRequestStatus.SENT.value
    assert result["workflow_slug"] == fake_workflow.slug
    assert result["graphic_url"] == "https://cdn.example.com/score.png"
    assert fake_renderer.calls[0].template_family == "ugc_score_graphic"
    service.trigger_engine.create_manual_request.assert_called_once()
    service.workflow_engine.execute.assert_called_once_with(fake_trigger)


def test_submit_testimonial_requires_parent_consent_for_minors():
    db = MagicMock()
    service = UGCService(db)

    with pytest.raises(ValueError, match="Parent consent is required"):
        service.submit_testimonial(
            athlete_name="Jane Smith",
            score=800,
            video_url="https://video.example.com/1",
            athlete_age=17,
            consent_athlete=True,
            consent_parent=False,
            consent_share=True,
        )


def test_submit_testimonial_bridges_high_score_submission_into_video_brief(monkeypatch):
    db = MagicMock()
    db.add = MagicMock()
    db.flush = MagicMock()
    service = UGCService(db)

    fake_renderer = FakeCanvaRenderer()
    fake_workflow = SimpleNamespace(id=uuid.uuid4(), slug="ugc-testimonial-submission-instagram")
    fake_trigger = SimpleNamespace(id=uuid.uuid4(), trigger_type=None, source_payload={"existing": "payload"})
    fake_job = SimpleNamespace(id=uuid.uuid4(), status="completed", error_message=None)
    fake_brief = {"id": str(uuid.uuid4()), "title": "Jane Smith testimonial video brief"}

    monkeypatch.setattr(ugc_service_module, "get_canva_renderer", lambda: fake_renderer)
    monkeypatch.setattr(service, "_resolve_submission_workflow", lambda: fake_workflow)
    service.trigger_engine = MagicMock()
    service.trigger_engine.create_manual_request.return_value = fake_trigger
    service.workflow_engine = MagicMock()
    service.workflow_engine.execute.return_value = fake_job
    service.video_service = MagicMock()
    service.video_service.create_brief_from_submission.return_value = fake_brief

    result = service.submit_testimonial(
        athlete_name="Jane Smith",
        score=810,
        video_url="https://video.example.com/1",
        testimonial_text="Pressure makes me sharper.",
        athlete_email="jane@example.com",
        parent_name="Pat Smith",
        parent_email="pat@example.com",
        athlete_age=18,
        consent_athlete=True,
        consent_parent=False,
        consent_share=True,
        request_id=str(uuid.uuid4()),
        source_partner="alliance_fastpitch",
        context="Alliance Fastpitch assessment",
    )

    assert result["status"] == UGCSubmissionStatus.ACCEPTED.value
    assert result["shareable_score_public"] is True
    assert result["video_brief"]["id"] == fake_brief["id"]
    assert result["video_brief_id"] == fake_brief["id"]
    assert result["graphic_url"] == "https://cdn.example.com/score.png"
    service.video_service.create_brief_from_submission.assert_called_once()
    assert fake_renderer.calls[0].template_family == "ugc_score_graphic"
