import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.brain import EntityNode
from app.models.partner import PartnerDeliveryBundle, PartnerEventRecord
from app.models.review import ContentJob, DraftVariant


class PartnerDeliveryService:
    def __init__(self, db: Session):
        self.db = db

    def build_bundle(
        self,
        partner: EntityNode,
        event_record: PartnerEventRecord,
        draft: DraftVariant,
        *,
        asset_ids: list[uuid.UUID] | None = None,
        usage_notes: str | None = None,
    ) -> PartnerDeliveryBundle:
        partner_name = getattr(partner, "canonical_name", None) or getattr(partner, "display_name", "")
        bundle = PartnerDeliveryBundle(
            id=uuid.uuid4(),
            partner_account_id=partner.id,
            partner_event_record_id=event_record.id,
            draft_variant_id=draft.id,
            platform=getattr(draft.platform, "value", draft.platform),
            status="needs_review",
            caption=draft.content,
            hashtags=list(draft.hashtags or []),
            asset_ids=list(asset_ids or []),
            delivery_payload={
                "partner_slug": partner.slug,
                "partner_name": partner_name,
                "event_type": event_record.event_type,
                "platform": getattr(draft.platform, "value", draft.platform),
            },
            usage_notes=usage_notes,
        )
        self.db.add(bundle)
        self.db.flush()
        return bundle

    def create_bundles_for_event(self, partner: EntityNode, event_record: PartnerEventRecord) -> list[PartnerDeliveryBundle]:
        bundles: list[PartnerDeliveryBundle] = []
        trigger_ids = list(event_record.trigger_event_ids or [])
        if not trigger_ids:
            return bundles

        jobs = (
            self.db.query(ContentJob)
            .filter(ContentJob.trigger_event_id.in_(trigger_ids))
            .all()
        )
        if not jobs:
            return bundles

        job_ids = [job.id for job in jobs]
        drafts = (
            self.db.query(DraftVariant)
            .filter(DraftVariant.content_job_id.in_(job_ids))
            .all()
        )
        existing_by_draft = {
            bundle.draft_variant_id
            for bundle in self.db.query(PartnerDeliveryBundle)
            .filter(PartnerDeliveryBundle.partner_event_record_id == event_record.id)
            .all()
        }
        for draft in drafts:
            if draft.id in existing_by_draft:
                continue
            asset_ids = [
                asset.id
                for asset in self.db.query(Asset).filter(Asset.draft_variant_id == draft.id).all()
            ]
            bundles.append(self.build_bundle(partner, event_record, draft, asset_ids=asset_ids))
        return bundles

    def list_bundles(self, partner_slug: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query = self.db.query(PartnerDeliveryBundle, PartnerEventRecord).join(
            PartnerEventRecord,
            PartnerEventRecord.id == PartnerDeliveryBundle.partner_event_record_id,
        )
        rows = query.order_by(PartnerDeliveryBundle.created_at.desc()).limit(limit).all()

        result = []
        for bundle, event in rows:
            payload = bundle.delivery_payload or {}
            p_slug = payload.get("partner_slug", "")
            p_name = payload.get("partner_name", "")
            if partner_slug and p_slug != partner_slug:
                continue
            result.append(
                {
                    "id": str(bundle.id),
                    "partner_slug": p_slug,
                    "partner_name": p_name,
                    "event_type": event.event_type,
                    "platform": bundle.platform,
                    "status": bundle.status,
                    "caption": bundle.caption,
                    "hashtags": bundle.hashtags or [],
                    "asset_ids": [str(asset_id) for asset_id in (bundle.asset_ids or [])],
                    "usage_notes": bundle.usage_notes,
                    "delivered_at": bundle.delivered_at.isoformat() if bundle.delivered_at else None,
                }
            )
        return result

    def update_bundle_status(self, bundle_id: uuid.UUID, status: str) -> dict[str, Any]:
        bundle = self.db.query(PartnerDeliveryBundle).filter(PartnerDeliveryBundle.id == bundle_id).first()
        if bundle is None:
            raise ValueError(f"Partner delivery bundle not found: {bundle_id}")
        bundle.status = status
        if status == "delivered":
            bundle.delivered_at = datetime.now(timezone.utc)
        self.db.flush()
        return {
            "bundle_id": str(bundle.id),
            "status": bundle.status,
            "message": "Bundle marked delivered." if status == "delivered" else f"Bundle marked {status}.",
        }
