import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.compliance import run_compliance_checks
from app.agents.content_writer import generate_tweets
from app.api.schemas import GenerateRequest, ResolveRequest
from app.database import get_db
from app.main import verify_api_key
from app.models.content import ContentQueue, ContentType, GenerationLog, Intent, Pillar, Status
from app.publishers import get_publisher


router = APIRouter()

CONTENT_TYPE_MAP = {
    "hot_take": ContentType.HOT_TAKE,
    "data_drop": ContentType.DATA_DROP,
    "trend_jack": ContentType.TREND_JACK,
}
PILLAR_MAP = {
    "blind_spot": Pillar.BLIND_SPOT,
    "cost_of_guessing": Pillar.COST_OF_GUESSING,
    "client_proof": Pillar.CLIENT_PROOF,
    "thought_leadership": Pillar.THOUGHT_LEADERSHIP,
    "product": Pillar.PRODUCT,
}
INTENT_MAP = {
    "brand": Intent.BRAND,
    "partner": Intent.PARTNER,
    "revenue": Intent.REVENUE,
}
TREND_JACK_EXPIRY_MINUTES = 60


@router.post("/content/generate", dependencies=[Depends(verify_api_key)])
def generate_content(req: GenerateRequest, db: Session = Depends(get_db)):
    if req.content_type not in CONTENT_TYPE_MAP:
        raise HTTPException(status_code=400, detail=f"Invalid content_type: {req.content_type}")
    if req.pillar not in PILLAR_MAP:
        raise HTTPException(status_code=400, detail=f"Invalid pillar: {req.pillar}")

    variations, log_data = generate_tweets(
        content_type=req.content_type,
        pillar=req.pillar,
        claims=req.claims,
        context=req.context,
    )
    if not variations:
        raise HTTPException(status_code=500, detail="No valid variations generated")

    variant_group = uuid.uuid4()
    request_payload = req.model_dump()
    now = datetime.now(timezone.utc)
    expires_at = (
        now + timedelta(minutes=TREND_JACK_EXPIRY_MINUTES)
        if req.content_type == "trend_jack"
        else None
    )

    drafts: list[ContentQueue] = []
    for variation in variations:
        compliance_result = run_compliance_checks(
            draft=variation,
            requested_claims=req.claims,
        )
        if not compliance_result.passed:
            continue

        item = ContentQueue(
            id=uuid.uuid4(),
            content=compliance_result.corrected_content or variation["content"],
            content_type=CONTENT_TYPE_MAP[req.content_type],
            pillar=PILLAR_MAP[req.pillar],
            intent=INTENT_MAP.get(variation.get("intent", "brand"), Intent.BRAND),
            hashtags=compliance_result.corrected_hashtags,
            status=Status.DRAFT,
            variant_group=variant_group,
            request_payload=request_payload,
            expires_at=expires_at,
            compliance_result={
                "passed": compliance_result.passed,
                "checks_run": compliance_result.checks_run,
            },
        )
        db.add(item)
        drafts.append(item)

    db.add(
        GenerationLog(
            id=uuid.uuid4(),
            content_queue_id=drafts[0].id if drafts else None,
            prompt_snapshot=log_data["prompt_snapshot"],
            response=log_data["response"],
            model=log_data["model"],
            tokens_in=log_data["tokens_in"],
            tokens_out=log_data["tokens_out"],
            cost_estimate=log_data["cost_estimate"],
            duration_ms=log_data["duration_ms"],
        )
    )
    db.commit()

    return {
        "variant_group": str(variant_group),
        "drafts": [
            {
                "id": str(draft.id),
                "content": draft.content,
                "hashtags": draft.hashtags,
                "intent": draft.intent.value,
                "compliance": draft.compliance_result,
            }
            for draft in drafts
        ],
        "total_generated": len(variations),
        "total_passed": len(drafts),
    }


@router.get("/content/drafts", dependencies=[Depends(verify_api_key)])
def list_drafts(db: Session = Depends(get_db)):
    drafts = (
        db.query(ContentQueue)
        .filter(ContentQueue.status == Status.DRAFT)
        .order_by(ContentQueue.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(draft.id),
            "content": draft.content,
            "content_type": draft.content_type.value,
            "pillar": draft.pillar.value,
            "intent": draft.intent.value,
            "hashtags": draft.hashtags,
            "variant_group": str(draft.variant_group),
            "expires_at": draft.expires_at.isoformat() if draft.expires_at else None,
            "created_at": draft.created_at.isoformat() if draft.created_at else None,
        }
        for draft in drafts
    ]


@router.get("/content/published", dependencies=[Depends(verify_api_key)])
def list_published(db: Session = Depends(get_db)):
    items = (
        db.query(ContentQueue)
        .filter(ContentQueue.status == Status.PUBLISHED)
        .order_by(ContentQueue.published_at.desc())
        .all()
    )
    return [
        {
            "id": str(item.id),
            "content": item.content,
            "post_url": item.post_url,
            "tweet_id": item.tweet_id,
            "published_at": item.published_at.isoformat() if item.published_at else None,
        }
        for item in items
    ]


@router.get("/system/status", dependencies=[Depends(verify_api_key)])
def system_status(db: Session = Depends(get_db)):
    total = db.query(ContentQueue).count()
    drafts = db.query(ContentQueue).filter(ContentQueue.status == Status.DRAFT).count()
    published = db.query(ContentQueue).filter(ContentQueue.status == Status.PUBLISHED).count()
    failed = db.query(ContentQueue).filter(ContentQueue.status == Status.FAILED).count()
    unknown = db.query(ContentQueue).filter(ContentQueue.status == Status.PUBLISHING_UNKNOWN).count()
    return {
        "status": "active",
        "counts": {
            "total": total,
            "drafts": drafts,
            "published": published,
            "failed": failed,
            "publishing_unknown": unknown,
        },
    }


@router.get("/content/{content_id}", dependencies=[Depends(verify_api_key)])
def get_content(content_id: str, db: Session = Depends(get_db)):
    item = db.query(ContentQueue).filter(ContentQueue.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    return {
        "id": str(item.id),
        "content": item.content,
        "content_type": item.content_type.value,
        "pillar": item.pillar.value,
        "intent": item.intent.value,
        "hashtags": item.hashtags,
        "status": item.status.value,
        "variant_group": str(item.variant_group),
        "post_url": item.post_url,
        "tweet_id": item.tweet_id,
        "compliance_result": item.compliance_result,
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.post("/content/{content_id}/publish", dependencies=[Depends(verify_api_key)])
def publish_content(content_id: str, db: Session = Depends(get_db)):
    item = db.query(ContentQueue).filter(ContentQueue.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    if item.expires_at and datetime.now(timezone.utc) > item.expires_at:
        raise HTTPException(status_code=410, detail="Draft has expired (trend_jack freshness)")

    result = db.execute(
        text(
            """
            UPDATE content_queue
            SET status = CASE
                    WHEN id = :target_id THEN 'publishing'
                    ELSE 'rejected'
                END,
                updated_at = now()
            WHERE variant_group = (SELECT variant_group FROM content_queue WHERE id = :target_id)
              AND status = 'draft'
            RETURNING id, status
            """
        ),
        {"target_id": content_id},
    )
    rows = result.fetchall()
    db.commit()

    target_claimed = any(str(row[0]) == content_id and row[1] == "publishing" for row in rows)
    if not target_claimed:
        raise HTTPException(
            status_code=409,
            detail="Draft already claimed, rejected, or not in draft status",
        )

    db.refresh(item)
    post_result = get_publisher().post_tweet(item.content)

    if post_result.success:
        item.status = Status.PUBLISHED
        item.tweet_id = post_result.tweet_id
        item.post_url = post_result.tweet_url
        item.published_at = datetime.now(timezone.utc)
    elif post_result.error and post_result.error.startswith("unknown:"):
        item.status = Status.PUBLISHING_UNKNOWN
        item.failure_reason = post_result.error
    else:
        item.status = Status.FAILED
        item.failure_reason = post_result.error

    db.commit()
    db.refresh(item)
    return {
        "id": str(item.id),
        "status": item.status.value,
        "post_url": item.post_url,
        "tweet_id": item.tweet_id,
        "failure_reason": item.failure_reason,
    }


@router.delete("/content/{content_id}", dependencies=[Depends(verify_api_key)])
def delete_content(content_id: str, db: Session = Depends(get_db)):
    item = db.query(ContentQueue).filter(ContentQueue.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    if item.status not in (Status.DRAFT, Status.FAILED):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete content in '{item.status.value}' status",
        )

    db.delete(item)
    db.commit()
    return {"deleted": True}


@router.post("/content/{content_id}/regenerate", dependencies=[Depends(verify_api_key)])
def regenerate_content(content_id: str, db: Session = Depends(get_db)):
    item = db.query(ContentQueue).filter(ContentQueue.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    if item.status not in (Status.DRAFT, Status.FAILED):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot regenerate from '{item.status.value}' status",
        )

    request_payload = dict(item.request_payload)
    variant_group = item.variant_group
    db.query(ContentQueue).filter(ContentQueue.variant_group == variant_group).delete()
    db.commit()

    return generate_content(GenerateRequest(**request_payload), db)


@router.post("/content/{content_id}/resolve", dependencies=[Depends(verify_api_key)])
def resolve_content(content_id: str, req: ResolveRequest, db: Session = Depends(get_db)):
    item = db.query(ContentQueue).filter(ContentQueue.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    if item.status != Status.PUBLISHING_UNKNOWN:
        raise HTTPException(
            status_code=409,
            detail=f"Can only resolve 'publishing_unknown' status, got '{item.status.value}'",
        )

    if req.outcome == "published":
        item.status = Status.PUBLISHED
        item.published_at = datetime.now(timezone.utc)
        if req.tweet_url:
            item.post_url = req.tweet_url
        if req.tweet_id:
            item.tweet_id = req.tweet_id
    elif req.outcome == "failed":
        item.status = Status.FAILED
        item.failure_reason = "Manually resolved as failed"
    else:
        raise HTTPException(status_code=400, detail="outcome must be 'published' or 'failed'")

    db.commit()
    return {"id": str(item.id), "status": item.status.value}
