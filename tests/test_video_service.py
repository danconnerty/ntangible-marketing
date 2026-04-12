import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.agents.video_writer import VideoWriterAgent
from app.models.video import VideoBriefKind, VideoBriefStatus
from app.models.workflow import Platform, WorkflowMode
from app.services.video_content_service import VideoContentService


def test_video_writer_agent_builds_motion_graphic_reel_brief():
    brief = VideoWriterAgent().build_brief(
        kind="reel_from_static",
        target_platform="linkedin",
        context="A data point about pressure performance.",
        source_mode="manual",
        source_material="750+ score data",
    )

    assert brief["kind"] == VideoBriefKind.REEL_FROM_STATIC.value
    assert brief["brief_format"] == "reel"
    assert brief["motion_graphic_notes"]
    assert "kinetic text" in brief["motion_graphic_notes"]
    assert brief["estimated_duration_seconds"] == 20


def test_create_brief_bridges_into_control_room_workflow(monkeypatch):
    db = MagicMock()
    db.add = MagicMock()
    db.flush = MagicMock()
    service = VideoContentService(db)

    fake_workflow = SimpleNamespace(
        id=uuid.uuid4(),
        slug="video-founder_raw-linkedin",
        platform=Platform.LINKEDIN,
        mode=WorkflowMode.MANUAL,
    )
    fake_trigger = SimpleNamespace(
        id=uuid.uuid4(),
        trigger_type=None,
        source_payload={"existing": "payload"},
    )
    fake_job = SimpleNamespace(id=uuid.uuid4(), status="completed", error_message=None)
    fake_draft = SimpleNamespace(id=uuid.uuid4(), state=None)

    monkeypatch.setattr(
        service.agent,
        "build_brief",
        lambda **kwargs: {
            "title": "Founder raw video brief",
            "kind": "founder_raw",
            "target_platform": "linkedin",
            "brief_format": "founder_raw",
            "source_mode": kwargs["source_mode"],
            "focus": kwargs["context"],
            "hook": "Open with the core point.",
            "thesis": "Founder-facing raw video should sound like a direct explanation from the arena.",
            "script": "Hook: Open with the core point.\nCTA: Thoughts?",
            "shot_list": ["Opening direct-to-camera hook"],
            "motion_graphic_notes": "Keep cuts simple and let the speaking track carry the clip.",
            "caption": "Founder raw video concept around the core point",
            "cta": "Thoughts?",
            "estimated_duration_seconds": 45,
            "request_text": "Please write the brief",
            "source_context": {"context": kwargs["context"], "source_mode": kwargs["source_mode"]},
        },
    )
    monkeypatch.setattr(service, "_resolve_workflow", lambda kind, platform, brief_data: fake_workflow)
    monkeypatch.setattr(service, "_latest_draft_for_job", lambda job_id: fake_draft)
    service.trigger_engine = MagicMock()
    service.trigger_engine.create_manual_request.return_value = fake_trigger
    service.workflow_engine = MagicMock()
    service.workflow_engine.execute.return_value = fake_job

    result = service.create_brief(
        kind="founder_raw",
        target_platform="linkedin",
        context="Founder proof from the field.",
        source_material="Raw clip notes.",
        source_mode="manual",
        title="Founder raw video brief",
        audience="coaches",
        cta="Thoughts?",
    )

    assert result["status"] == VideoBriefStatus.BRIEFED.value
    assert result["workflow_slug"] == fake_workflow.slug
    assert result["content_job_id"] == str(fake_job.id)
    assert result["draft_variant_id"] == str(fake_draft.id)
    assert result["hook"] == "Open with the core point."
    assert result["motion_graphic_notes"] == "Keep cuts simple and let the speaking track carry the clip."
    service.trigger_engine.create_manual_request.assert_called_once_with("Please write the brief", fake_workflow.id)
    service.workflow_engine.execute.assert_called_once_with(fake_trigger)
    assert db.add.call_count >= 1


def test_create_brief_from_submission_targets_testimonial_video(monkeypatch):
    db = MagicMock()
    db.add = MagicMock()
    db.flush = MagicMock()
    service = VideoContentService(db)

    fake_workflow = SimpleNamespace(id=uuid.uuid4(), slug="video-testimonial-instagram")
    fake_trigger = SimpleNamespace(id=uuid.uuid4(), trigger_type=None, source_payload={})
    fake_job = SimpleNamespace(id=uuid.uuid4(), status="completed")
    fake_draft = SimpleNamespace(id=uuid.uuid4(), state=None)

    monkeypatch.setattr(service, "_resolve_workflow", lambda kind, platform, brief_data: fake_workflow)
    monkeypatch.setattr(service, "_latest_draft_for_job", lambda job_id: fake_draft)
    monkeypatch.setattr(
        service.agent,
        "build_brief",
        lambda **kwargs: {
            "title": kwargs["title"],
            "kind": "testimonial",
            "target_platform": kwargs["target_platform"],
            "brief_format": "testimonial_video",
            "source_mode": kwargs["source_mode"],
            "focus": kwargs["context"],
            "hook": "Lead with the athlete voice, not the marketing voice.",
            "thesis": "A consented athlete story becomes a credibility asset across channels.",
            "script": "Hook: Lead with the athlete voice, not the marketing voice.",
            "shot_list": ["Open with the athlete on camera"],
            "motion_graphic_notes": "Keep cuts simple and let the speaking track carry the clip.",
            "caption": "Athlete testimonial concept centered on the story",
            "cta": "Watch the full testimonial.",
            "estimated_duration_seconds": 35,
            "request_text": "Please generate a testimonial brief",
            "source_context": {},
        },
    )
    service.trigger_engine = MagicMock()
    service.trigger_engine.create_manual_request.return_value = fake_trigger
    service.workflow_engine = MagicMock()
    service.workflow_engine.execute.return_value = fake_job

    result = service.create_brief_from_submission(
        athlete_name="Jane Smith",
        score=810,
        score_tier="Silver",
        testimonial_text="Pressure makes me more focused.",
        parent_name="Pat Smith",
        source_request_id="request-1",
    )

    assert result["kind"] == VideoBriefKind.TESTIMONIAL.value
    assert result["title"] == "Jane Smith testimonial video brief"
    assert result["workflow_slug"] == fake_workflow.slug
    assert result["status"] == VideoBriefStatus.BRIEFED.value
