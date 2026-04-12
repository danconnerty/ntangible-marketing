import hashlib
import inspect
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.brain import EntityNode
from app.models.partner import PartnerEventRecord
from app.services.brain_query import BrainQuery
from app.services.partner_delivery_service import PartnerDeliveryService
from app.services.trigger_engine import TriggerEngine
from app.triggers.partner_events import build_trigger_requests, normalize_partner_event


DEFAULT_PARTNERS = {
    "alliance_fastpitch": {
        "display_name": "Alliance Fastpitch",
        "portal_username": "alliance",
        "portal_password": "alliance",
        "webhook_secret": "alliance-secret",
    },
    "fss": {
        "display_name": "Future Stars Series",
        "portal_username": "fss",
        "portal_password": "fss",
        "webhook_secret": "fss-secret",
    },
}


def hash_partner_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class PartnerIntakeService:
    def __init__(self, db: Session):
        self.db = db
        self.bq = BrainQuery(db)
        self.trigger_engine = TriggerEngine(db)
        self.delivery_service = PartnerDeliveryService(db)

    def ingest_webhook(self, partner_slug: str, payload: dict[str, Any]) -> dict[str, Any]:
        partner = self._resolve_partner(partner_slug)
        normalized = normalize_partner_event(partner.slug, payload)
        event_record = self._create_event_record(partner, "webhook", normalized, payload)
        results = self._run_execute_requests(partner, normalized, event_record, "webhook")
        self.db.flush()
        return {
            "partner_slug": partner.slug,
            "event_record_id": str(event_record.id),
            "results": results,
        }

    def ingest_portal(self, partner_slug: str, payload: dict[str, Any]) -> dict[str, Any]:
        partner = self._resolve_partner(partner_slug)
        normalized = normalize_partner_event(partner.slug, payload)
        event_record = self._create_event_record(partner, "portal", normalized, payload)
        results = self._run_execute_requests(partner, normalized, event_record, "portal")
        self.db.flush()
        return {
            "partner_slug": partner.slug,
            "event_record_id": str(event_record.id),
            "results": results,
        }

    def list_partners(self) -> list[dict[str, Any]]:
        self._ensure_default_partners()
        partners = self.bq.list_entities_by_type("partner_source")
        return [
            {
                "id": str(partner.id),
                "slug": partner.slug,
                "display_name": partner.canonical_name,
                "portal_username": partner.metadata_.get("portal_username", ""),
                "supported_event_types": partner.metadata_.get("supported_event_types") or [],
            }
            for partner in sorted(partners, key=lambda p: p.canonical_name)
        ]

    def list_events(self, partner_slug: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query = self.db.query(PartnerEventRecord)
        if partner_slug:
            partner = self.bq.get_entity_by_slug("partner_source", partner_slug)
            if partner:
                query = query.filter(PartnerEventRecord.partner_account_id == partner.id)
        rows = query.order_by(PartnerEventRecord.created_at.desc()).limit(limit).all()

        # Build a lookup of entity IDs to slugs/names for enrichment
        partner_lookup: dict[uuid.UUID, EntityNode] = {}
        for event in rows:
            if event.partner_account_id not in partner_lookup:
                entity = self.bq.get_entity(event.partner_account_id)
                if entity:
                    partner_lookup[event.partner_account_id] = entity

        return [
            {
                "id": str(event.id),
                "partner_slug": partner_lookup.get(event.partner_account_id, _stub_entity(event.partner_account_id)).slug,
                "partner_name": partner_lookup.get(event.partner_account_id, _stub_entity(event.partner_account_id)).canonical_name,
                "event_type": event.event_type,
                "external_event_id": event.external_event_id,
                "intake_source": event.intake_source,
                "processing_status": event.processing_status,
                "trigger_event_ids": [str(item) for item in (event.trigger_event_ids or [])],
                "failure_reason": event.failure_reason,
            }
            for event in rows
        ]

    def authenticate_portal_user(self, username: str, password: str) -> dict[str, Any] | None:
        self._ensure_default_partners()
        partners = self.bq.list_entities_by_type("partner_source")
        partner = next(
            (p for p in partners if p.metadata_.get("portal_username") == username),
            None,
        )
        if partner is None:
            return None
        stored_hash = partner.metadata_.get("portal_password_hash", "")
        if stored_hash != hash_partner_password(password):
            return None
        return {
            "slug": partner.slug,
            "display_name": partner.canonical_name,
        }

    def _ensure_default_partners(self) -> None:
        for slug, config in DEFAULT_PARTNERS.items():
            existing = self.bq.get_entity_by_slug("partner_source", slug)
            if existing:
                continue
            self.bq.create_entity(
                entity_type="partner_source",
                canonical_name=config["display_name"],
                slug=slug,
                metadata={
                    "portal_username": config["portal_username"],
                    "portal_password_hash": hash_partner_password(config["portal_password"]),
                    "webhook_secret": config["webhook_secret"],
                    "supported_event_types": [
                        "assessment_completed",
                        "leaderboard_published",
                        "commitment_update",
                        "offer_update",
                        "milestone_reached",
                        "registration_push",
                        "event_promotion",
                    ],
                    "routing_config": {},
                    "delivery_defaults": {},
                },
            )

    def _resolve_partner(self, slug: str) -> EntityNode:
        self._ensure_default_partners()
        partner = self.bq.get_entity_by_slug("partner_source", slug)
        if partner is None:
            raise ValueError(f"Partner account not found: {slug}")
        return partner

    def _create_event_record(
        self,
        partner: EntityNode,
        source: str,
        normalized,
        raw_payload: dict[str, Any],
    ) -> PartnerEventRecord:
        existing = (
            self.db.query(PartnerEventRecord)
            .filter(
                PartnerEventRecord.partner_account_id == partner.id,
                PartnerEventRecord.event_type == normalized.event_type,
                PartnerEventRecord.external_event_id == normalized.external_event_id,
            )
            .first()
        )
        if existing:
            existing.raw_payload = raw_payload
            existing.normalized_payload = normalized.payload
            existing.processing_status = "received"
            existing.failure_reason = None
            self.db.flush()
            return existing

        record = PartnerEventRecord(
            id=uuid.uuid4(),
            partner_account_id=partner.id,
            intake_source=source,
            event_type=normalized.event_type,
            external_event_id=normalized.external_event_id,
            raw_payload=raw_payload,
            normalized_payload=normalized.payload,
            processing_status="received",
            trigger_event_ids=[],
        )
        self.db.add(record)
        self.db.flush()
        return record

    def _run_execute_requests(
        self,
        partner: EntityNode,
        normalized,
        event_record: PartnerEventRecord,
        intake_source: str,
    ) -> list[dict[str, Any]]:
        execute_requests = self._execute_requests
        parameter_count = len(inspect.signature(execute_requests).parameters)
        if parameter_count <= 3:
            return execute_requests(partner, normalized, event_record)
        return execute_requests(partner, normalized, event_record, intake_source)

    def _execute_requests(
        self,
        partner: EntityNode,
        normalized,
        event_record: PartnerEventRecord,
        intake_source: str = "webhook",
    ) -> list[dict[str, Any]]:
        requests = build_trigger_requests(normalized)
        partner_source = self.trigger_engine.ensure_partner_source(partner.slug)
        results: list[dict[str, Any]] = []
        trigger_ids: list[uuid.UUID] = []
        for request in requests:
            summary = self.trigger_engine.execute_partner_request(
                partner_source,
                normalized,
                request,
                intake_source=intake_source,
            )
            if summary.get("trigger_event_id"):
                trigger_ids.append(uuid.UUID(summary["trigger_event_id"]))
            results.append(summary)

        event_record.trigger_event_ids = trigger_ids
        if any(result.get("status") == "failed" for result in results):
            event_record.processing_status = "failed"
            event_record.failure_reason = next(
                (result.get("error") for result in results if result.get("error")),
                None,
            )
        else:
            event_record.processing_status = "processed"
            event_record.failure_reason = None

        self.delivery_service.create_bundles_for_event(partner, event_record)
        self.db.flush()
        return results


class _StubEntity:
    """Minimal stand-in when an entity ID cannot be resolved during list_events."""

    def __init__(self, entity_id: uuid.UUID) -> None:
        self.slug = str(entity_id)
        self.canonical_name = "Unknown partner"


def _stub_entity(entity_id: uuid.UUID) -> _StubEntity:
    return _StubEntity(entity_id)
