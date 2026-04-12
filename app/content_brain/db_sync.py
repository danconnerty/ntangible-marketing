from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.content_brain.sources import load_seed_targets
from app.content_brain.types import SourceTarget
from app.models.content_brain import (
    ContentBrainAsset,
    ContentBrainItem,
    ContentBrainMetricSnapshot,
    ContentPlatform,
    ContentSourceKind,
    ContentSourceSnapshot,
    ContentSourceTarget,
    SnapshotFormat,
)


@dataclass(slots=True)
class SnapshotImportPayload:
    source_url: str
    status_code: int | None
    content_type: str | None
    snapshot_format: str
    storage_path: str | None
    body_sha256: str | None
    snapshot_metadata: dict[str, Any]
    fetched_at: datetime


def _sanitize_slug(value: str) -> str:
    normalized = []
    for char in value:
        normalized.append(char if char.isalnum() or char in {"-", "_"} else "_")
    return "".join(normalized).strip("_") or "snapshot"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_normalized_payloads(storage_root: Path) -> list[dict[str, Any]]:
    normalized_root = storage_root / "normalized"
    by_slug: dict[str, Path] = {}
    for path in sorted(normalized_root.rglob("*.json")):
        by_slug[path.stem] = path
    return [_load_json(path) for _, path in sorted(by_slug.items())]


def build_run_result_index(storage_root: Path) -> dict[str, dict[str, Any]]:
    run_root = storage_root / "runs"
    index: dict[str, dict[str, Any]] = {}
    for run_path in sorted(run_root.glob("*.json")):
        payload = _load_json(run_path)
        for result in payload.get("results", []):
            target_slug = result.get("target_slug")
            if not target_slug or result.get("error"):
                continue
            index[target_slug] = result
    return index


def resolve_raw_storage_path(*, storage_root: Path, target_slug: str, fetched_at: datetime) -> str | None:
    day_bucket = fetched_at.strftime("%Y-%m-%d")
    safe_slug = _sanitize_slug(target_slug)
    day_root = storage_root / "raw" / day_bucket
    if not day_root.exists():
        return None

    exact_matches = sorted(day_root.glob(f"{safe_slug}.*"))
    if exact_matches:
        return exact_matches[-1].relative_to(storage_root).as_posix()

    prefixed_matches = sorted(
        path
        for path in day_root.glob(f"{safe_slug}*")
        if path.is_file() and path.name.startswith(f"{safe_slug}.")
    )
    if prefixed_matches:
        return prefixed_matches[-1].relative_to(storage_root).as_posix()
    return None


def _normalize_platform(value: str | None) -> str:
    lowered = (value or "").lower()
    if lowered in {member.value for member in ContentPlatform}:
        return lowered
    return ContentPlatform.OTHER.value


def _normalize_source_kind(value: str | None) -> str:
    lowered = (value or "").lower()
    if lowered == "press":
        return ContentSourceKind.EXTERNAL.value
    if lowered in {member.value for member in ContentSourceKind}:
        return lowered
    return ContentSourceKind.EXTERNAL.value


def _infer_source_kind(payload: dict[str, Any], *, platform: str) -> str:
    source_url = (payload.get("source_url") or "").lower()
    if "web.archive.org" in source_url:
        return ContentSourceKind.WAYBACK.value
    if platform in {ContentPlatform.INSTAGRAM.value, ContentPlatform.LINKEDIN.value}:
        return ContentSourceKind.SOCIAL.value
    if "ntangible.co" in source_url or "portal.ntangible.co" in source_url:
        return ContentSourceKind.WEBSITE.value
    return ContentSourceKind.EXTERNAL.value


def prepare_target_payload(
    payload: dict[str, Any],
    *,
    seed_target: SourceTarget | None,
) -> dict[str, Any]:
    if seed_target is not None:
        target_metadata = {"notes": seed_target.notes, **seed_target.metadata}
        return {
            "slug": seed_target.slug,
            "display_name": seed_target.display_name,
            "source_kind": _normalize_source_kind(seed_target.source_kind),
            "platform": _normalize_platform(seed_target.platform),
            "url": seed_target.url,
            "parser": seed_target.parser,
            "active": True,
            "target_metadata": target_metadata,
        }

    first_item = (payload.get("items") or [{}])[0]
    platform = _normalize_platform(first_item.get("platform"))
    display_name = first_item.get("title") or payload.get("target_slug", "").replace("_", " ").title()
    return {
        "slug": payload["target_slug"],
        "display_name": display_name,
        "source_kind": _normalize_source_kind(_infer_source_kind(payload, platform=platform)),
        "platform": platform,
        "url": payload.get("source_url"),
        "parser": "db_import_fallback",
        "active": True,
        "target_metadata": {
            "derived": True,
            "item_type": first_item.get("item_type"),
        },
    }


def _infer_snapshot_format(*, storage_path: str | None, content_type: str | None, source_url: str) -> str:
    lowered_type = (content_type or "").lower()
    lowered_url = source_url.lower()
    suffix = Path(storage_path).suffix.lower() if storage_path else ""
    if suffix == ".html" or "html" in lowered_type or lowered_url.endswith((".html", ".htm")):
        return SnapshotFormat.HTML.value
    if suffix == ".xml" or "xml" in lowered_type or lowered_url.endswith(".xml"):
        return SnapshotFormat.XML.value
    if suffix == ".json" or "json" in lowered_type or lowered_url.endswith(".json"):
        return SnapshotFormat.JSON.value
    return SnapshotFormat.TEXT.value


def prepare_snapshot_payload(
    payload: dict[str, Any],
    *,
    storage_root: Path,
    run_result: dict[str, Any] | None,
) -> SnapshotImportPayload:
    fetched_at = datetime.fromisoformat(payload["fetched_at"])
    storage_path = None
    status_code = None
    if run_result:
        storage_path = run_result.get("raw_path")
        status_code = run_result.get("status_code")
    if storage_path is None:
        storage_path = resolve_raw_storage_path(
            storage_root=storage_root,
            target_slug=payload["target_slug"],
            fetched_at=fetched_at,
        )

    return SnapshotImportPayload(
        source_url=payload["source_url"],
        status_code=status_code,
        content_type=payload.get("content_type"),
        snapshot_format=_infer_snapshot_format(
            storage_path=storage_path,
            content_type=payload.get("content_type"),
            source_url=payload["source_url"],
        ),
        storage_path=storage_path,
        body_sha256=payload.get("body_sha256"),
        snapshot_metadata={
            "imported_from_files": True,
            "target_slug": payload["target_slug"],
            "item_count": payload.get("item_count", 0),
        },
        fetched_at=fetched_at,
    )


def _prepare_item_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_key": item["canonical_key"],
        "platform": _normalize_platform(item.get("platform")),
        "item_type": item["item_type"],
        "external_id": item.get("external_id"),
        "url": item["url"],
        "title": item.get("title"),
        "author": item.get("author"),
        "published_at": datetime.fromisoformat(item["published_at"]) if item.get("published_at") else None,
        "body_text": item.get("body_text"),
        "summary": item.get("summary"),
        "item_metadata": item.get("metadata") or {},
        "assets": item.get("assets") or [],
        "metrics": item.get("metrics") or [],
    }


def _upsert_source_target(session: Session, payload: dict[str, Any]) -> tuple[ContentSourceTarget, bool]:
    existing = session.execute(
        select(ContentSourceTarget).where(ContentSourceTarget.slug == payload["slug"])
    ).scalar_one_or_none()
    created = existing is None
    target = existing or ContentSourceTarget(
        slug=payload["slug"],
        display_name=payload["display_name"],
        source_kind=ContentSourceKind(payload["source_kind"]),
        platform=ContentPlatform(payload["platform"]),
        url=payload["url"],
        parser=payload["parser"],
        active=payload["active"],
        target_metadata=payload["target_metadata"],
    )
    if created:
        session.add(target)
    else:
        target.display_name = payload["display_name"]
        target.source_kind = ContentSourceKind(payload["source_kind"])
        target.platform = ContentPlatform(payload["platform"])
        target.url = payload["url"]
        target.parser = payload["parser"]
        target.active = payload["active"]
        target.target_metadata = payload["target_metadata"]
    session.flush()
    return target, created


def _upsert_snapshot(
    session: Session,
    *,
    target: ContentSourceTarget,
    payload: SnapshotImportPayload,
) -> tuple[ContentSourceSnapshot, bool]:
    stmt = select(ContentSourceSnapshot).where(
        ContentSourceSnapshot.target_id == target.id,
        ContentSourceSnapshot.fetched_at == payload.fetched_at,
    )
    if payload.body_sha256:
        stmt = stmt.where(ContentSourceSnapshot.body_sha256 == payload.body_sha256)
    elif payload.storage_path:
        stmt = stmt.where(ContentSourceSnapshot.storage_path == payload.storage_path)
    existing = session.execute(stmt).scalar_one_or_none()
    created = existing is None
    snapshot = existing or ContentSourceSnapshot(
        target_id=target.id,
        source_url=payload.source_url,
        status_code=payload.status_code,
        content_type=payload.content_type,
        snapshot_format=SnapshotFormat(payload.snapshot_format),
        storage_path=payload.storage_path,
        body_sha256=payload.body_sha256,
        snapshot_metadata=payload.snapshot_metadata,
        fetched_at=payload.fetched_at,
    )
    if created:
        session.add(snapshot)
    else:
        snapshot.source_url = payload.source_url
        snapshot.status_code = payload.status_code
        snapshot.content_type = payload.content_type
        snapshot.snapshot_format = SnapshotFormat(payload.snapshot_format)
        snapshot.storage_path = payload.storage_path
        snapshot.body_sha256 = payload.body_sha256
        snapshot.snapshot_metadata = payload.snapshot_metadata
    session.flush()
    return snapshot, created


def _upsert_item(
    session: Session,
    *,
    target: ContentSourceTarget,
    snapshot: ContentSourceSnapshot,
    payload: dict[str, Any],
) -> tuple[ContentBrainItem, bool]:
    existing = session.execute(
        select(ContentBrainItem).where(ContentBrainItem.canonical_key == payload["canonical_key"])
    ).scalar_one_or_none()
    created = existing is None
    item = existing or ContentBrainItem(
        canonical_key=payload["canonical_key"],
        platform=ContentPlatform(payload["platform"]),
        item_type=payload["item_type"],
        external_id=payload["external_id"],
        url=payload["url"],
        title=payload["title"],
        author=payload["author"],
        published_at=payload["published_at"],
        body_text=payload["body_text"],
        summary=payload["summary"],
        item_metadata=payload["item_metadata"],
    )
    if created:
        session.add(item)
    else:
        item.platform = ContentPlatform(payload["platform"])
        item.item_type = payload["item_type"]
        item.external_id = payload["external_id"]
        item.url = payload["url"]
        item.title = payload["title"]
        item.author = payload["author"]
        item.published_at = payload["published_at"]
        item.body_text = payload["body_text"]
        item.summary = payload["summary"]
        item.item_metadata = payload["item_metadata"]
    item.target_id = target.id
    item.snapshot_id = snapshot.id
    session.flush()
    return item, created


def _replace_assets(session: Session, *, item: ContentBrainItem, assets: list[dict[str, Any]]) -> int:
    session.execute(
        delete(ContentBrainAsset).where(ContentBrainAsset.content_item_id == item.id)
    )
    created = 0
    for asset in assets:
        session.add(
            ContentBrainAsset(
                content_item_id=item.id,
                asset_type=asset["asset_type"],
                url=asset["url"],
                asset_metadata=asset.get("metadata") or {},
            )
        )
        created += 1
    return created


def _replace_metrics(session: Session, *, item: ContentBrainItem, metrics: list[dict[str, Any]]) -> int:
    session.execute(
        delete(ContentBrainMetricSnapshot).where(ContentBrainMetricSnapshot.content_item_id == item.id)
    )
    created = 0
    for metric in metrics:
        observed_at = metric.get("observed_at")
        if not observed_at:
            continue
        session.add(
            ContentBrainMetricSnapshot(
                content_item_id=item.id,
                observed_at=datetime.fromisoformat(observed_at),
                source_url=metric.get("source_url"),
                metric_payload=metric.get("payload") or {},
            )
        )
        created += 1
    return created


def content_brain_db_counts(session: Session) -> dict[str, int]:
    return {
        "targets": session.execute(select(func.count()).select_from(ContentSourceTarget)).scalar_one(),
        "snapshots": session.execute(select(func.count()).select_from(ContentSourceSnapshot)).scalar_one(),
        "items": session.execute(select(func.count()).select_from(ContentBrainItem)).scalar_one(),
        "assets": session.execute(select(func.count()).select_from(ContentBrainAsset)).scalar_one(),
        "metric_snapshots": session.execute(
            select(func.count()).select_from(ContentBrainMetricSnapshot)
        ).scalar_one(),
    }


def sync_storage_to_db(session: Session, *, storage_root: Path) -> dict[str, Any]:
    seed_targets = {target.slug: target for target in load_seed_targets()}
    run_index = build_run_result_index(storage_root)
    payloads = _latest_normalized_payloads(storage_root)

    created_targets = 0
    created_snapshots = 0
    created_items = 0
    replaced_assets = 0
    replaced_metrics = 0

    for payload in payloads:
        target_payload = prepare_target_payload(
            payload,
            seed_target=seed_targets.get(payload["target_slug"]),
        )
        target, target_created = _upsert_source_target(session, target_payload)
        created_targets += int(target_created)

        snapshot_payload = prepare_snapshot_payload(
            payload,
            storage_root=storage_root,
            run_result=run_index.get(payload["target_slug"]),
        )
        snapshot, snapshot_created = _upsert_snapshot(
            session,
            target=target,
            payload=snapshot_payload,
        )
        created_snapshots += int(snapshot_created)

        for raw_item in payload.get("items", []):
            item_payload = _prepare_item_payload(raw_item)
            item, item_created = _upsert_item(
                session,
                target=target,
                snapshot=snapshot,
                payload=item_payload,
            )
            created_items += int(item_created)
            replaced_assets += _replace_assets(session, item=item, assets=item_payload["assets"])
            replaced_metrics += _replace_metrics(session, item=item, metrics=item_payload["metrics"])

    session.flush()
    return {
        "payloads": len(payloads),
        "created_targets": created_targets,
        "created_snapshots": created_snapshots,
        "created_items": created_items,
        "replaced_assets": replaced_assets,
        "replaced_metrics": replaced_metrics,
        "db_counts": content_brain_db_counts(session),
    }
