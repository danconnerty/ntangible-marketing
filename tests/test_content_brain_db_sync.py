import json
from datetime import UTC, datetime
from pathlib import Path

from app.content_brain.types import SourceTarget
from app.content_brain.db_sync import (
    SnapshotImportPayload,
    prepare_snapshot_payload,
    prepare_target_payload,
    resolve_raw_storage_path,
)


def test_resolve_raw_storage_path_prefers_exact_slug_file(tmp_path):
    day_root = tmp_path / "raw" / "2026-04-07"
    day_root.mkdir(parents=True)
    exact = day_root / "ntangible_instagram_profile.html"
    exact.write_text("<html></html>", encoding="utf-8")
    (day_root / "ntangible_instagram_profile__DVvywRbjrLC.html").write_text(
        "<html>post</html>",
        encoding="utf-8",
    )

    path = resolve_raw_storage_path(
        storage_root=tmp_path,
        target_slug="ntangible_instagram_profile",
        fetched_at=datetime(2026, 4, 7, 3, 28, tzinfo=UTC),
    )

    assert path == "raw/2026-04-07/ntangible_instagram_profile.html"


def test_prepare_target_payload_uses_seed_target_when_present():
    seed_target = SourceTarget(
        slug="ntangible_home",
        display_name="NTangible Home",
        url="https://ntangible.co/",
        parser="generic_document",
        platform="web",
        source_kind="website",
        notes="Live NTangible homepage.",
        metadata={"source": "seed"},
    )
    payload = {
        "target_slug": "ntangible_home",
        "source_url": "https://ntangible.co/",
        "items": [
            {
                "title": "NTangible",
                "platform": "web",
            }
        ],
    }

    prepared = prepare_target_payload(payload, seed_target=seed_target)

    assert prepared["slug"] == "ntangible_home"
    assert prepared["display_name"] == "NTangible Home"
    assert prepared["source_kind"] == "website"
    assert prepared["platform"] == "web"
    assert prepared["parser"] == "generic_document"
    assert prepared["target_metadata"]["notes"] == "Live NTangible homepage."
    assert prepared["target_metadata"]["source"] == "seed"


def test_prepare_target_payload_falls_back_for_unseeded_slug():
    payload = {
        "target_slug": "research_alignment_index_pdf",
        "source_url": "https://drive.google.com/file/d/17LjW7fip5Jw91lmeKc89mF5yu3__kNB5/view",
        "items": [
            {
                "title": "The Science of Dyadic Congruence",
                "platform": "web",
                "item_type": "research_pdf",
            }
        ],
    }

    prepared = prepare_target_payload(payload, seed_target=None)

    assert prepared["slug"] == "research_alignment_index_pdf"
    assert prepared["display_name"] == "The Science of Dyadic Congruence"
    assert prepared["source_kind"] == "external"
    assert prepared["platform"] == "web"
    assert prepared["parser"] == "db_import_fallback"
    assert prepared["target_metadata"]["derived"] is True


def test_prepare_target_payload_maps_press_seed_target_to_external():
    seed_target = SourceTarget(
        slug="founderspress_rfk_article",
        display_name="FoundersPress RFK Partnership Article",
        url="https://thefounderspress.com/ntangible-brings-mental-fitness-tech-to-rfk-elevate-pit-crew-performance/",
        parser="generic_document",
        platform="web",
        source_kind="press",
        notes="Public press coverage.",
        metadata={},
    )
    payload = {
        "target_slug": "founderspress_rfk_article",
        "source_url": seed_target.url,
        "items": [{"title": "NTangible Brings Mental Fitness Tech to RFK Racing", "platform": "web"}],
    }

    prepared = prepare_target_payload(payload, seed_target=seed_target)

    assert prepared["source_kind"] == "external"


def test_prepare_snapshot_payload_prefers_raw_file_extension_for_format(tmp_path):
    day_root = tmp_path / "raw" / "2026-04-07"
    day_root.mkdir(parents=True)
    raw_path = day_root / "research_alignment_index_pdf.txt"
    raw_path.write_text("pdf text extract", encoding="utf-8")

    payload = {
        "target_slug": "research_alignment_index_pdf",
        "source_url": "https://drive.google.com/file/d/17LjW7fip5Jw91lmeKc89mF5yu3__kNB5/view",
        "fetched_at": "2026-04-07T03:37:08+00:00",
        "content_type": "application/pdf",
        "body_sha256": "abc123",
    }
    run_result = {
        "status_code": 200,
        "raw_path": "raw/2026-04-07/research_alignment_index_pdf.txt",
    }

    prepared = prepare_snapshot_payload(
        payload,
        storage_root=tmp_path,
        run_result=run_result,
    )

    assert isinstance(prepared, SnapshotImportPayload)
    assert prepared.status_code == 200
    assert prepared.snapshot_format == "text"
    assert prepared.storage_path == "raw/2026-04-07/research_alignment_index_pdf.txt"
    assert prepared.body_sha256 == "abc123"
