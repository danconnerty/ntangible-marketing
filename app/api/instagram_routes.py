from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.instagram_schemas import InstagramGenerateRequest
from app.auth import verify_api_key
from app.database import get_db
from app.models.asset import Asset
from app.models.instagram import PartnerDeliveryPackage
from app.models.review import DraftVariant
from app.models.workflow import DraftState, Platform
from app.services.instagram_pipeline import generate_instagram_item, publish_instagram_variant


router = APIRouter(prefix="/instagram", tags=["instagram"])


def _serialize_asset(asset: Asset) -> dict:
    return {
        "id": str(getattr(asset, "id")),
        "asset_role": getattr(asset, "asset_role", None),
        "url": getattr(asset, "url", None),
        "storage_path": getattr(asset, "storage_path", None),
    }


def _serialize_package(package: PartnerDeliveryPackage | None) -> dict | None:
    if package is None:
        return None
    return {
        "id": str(getattr(package, "id")),
        "partner_name": getattr(package, "partner_name", None),
        "status": getattr(getattr(package, "status", None), "value", getattr(package, "status", None)),
        "delivery_channel": getattr(getattr(package, "delivery_channel", None), "value", None),
    }


def _serialize_draft(draft: DraftVariant, assets: list[Asset] | None = None, package: PartnerDeliveryPackage | None = None) -> dict:
    compliance = draft.compliance_result or {}
    return {
        "id": str(draft.id),
        "status": draft.state.value,
        "approval_tier": compliance.get("approval_tier"),
        "content": draft.content,
        "hashtags": draft.hashtags,
        "template_family": compliance.get("template_family"),
        "publish_mode": compliance.get("publish_mode"),
        "platform_post_id": draft.platform_post_id,
        "post_url": draft.post_url,
        "failure_reason": draft.failure_reason,
        "assets": [_serialize_asset(asset) for asset in assets or []],
        "package": _serialize_package(package),
    }


@router.post("/generate", dependencies=[Depends(verify_api_key)])
def generate_instagram(req: InstagramGenerateRequest, db: Session = Depends(get_db)):
    try:
        result = generate_instagram_item(req.model_dump(), db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_draft(result["draft"], result["assets"], result["package"])


@router.get("/review", dependencies=[Depends(verify_api_key)])
def list_instagram_review(db: Session = Depends(get_db)):
    drafts = (
        db.query(DraftVariant)
        .filter(
            DraftVariant.platform == Platform.INSTAGRAM,
            DraftVariant.state.in_([DraftState.MANUAL_READY, DraftState.NEEDS_DESIGN_REVIEW]),
        )
        .order_by(DraftVariant.created_at.desc())
        .all()
    )
    return [_serialize_draft(draft) for draft in drafts]


@router.get("/published", dependencies=[Depends(verify_api_key)])
def list_instagram_published(db: Session = Depends(get_db)):
    drafts = (
        db.query(DraftVariant)
        .filter(DraftVariant.platform == Platform.INSTAGRAM, DraftVariant.state == DraftState.PUBLISHED)
        .order_by(DraftVariant.published_at.desc())
        .all()
    )
    return [_serialize_draft(draft) for draft in drafts]


@router.get("/packages", dependencies=[Depends(verify_api_key)])
def list_partner_packages(db: Session = Depends(get_db)):
    packages = db.query(PartnerDeliveryPackage).order_by(PartnerDeliveryPackage.created_at.desc()).all()
    return [_serialize_package(package) for package in packages]


@router.post("/{draft_id}/publish", dependencies=[Depends(verify_api_key)])
def publish_instagram(draft_id: str, db: Session = Depends(get_db)):
    try:
        draft = publish_instagram_variant(draft_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    assets = (
        db.query(Asset)
        .filter(Asset.draft_variant_id == draft.id)
        .order_by(Asset.sort_order.asc())
        .all()
    )
    package = db.query(PartnerDeliveryPackage).filter(PartnerDeliveryPackage.draft_variant_id == draft.id).first()
    return _serialize_draft(draft, assets, package)
