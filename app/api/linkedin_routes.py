from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.linkedin_schemas import LinkedInGenerateRequest, LinkedInReviewRequest
from app.auth import verify_api_key
from app.database import get_db
from app.models.linkedin import LinkedInPost, LinkedInStatus
from app.services.linkedin_pipeline import (
    approve_linkedin_item,
    generate_linkedin_item,
    publish_linkedin_item,
    reject_linkedin_item,
)


router = APIRouter(prefix="/linkedin", tags=["linkedin"])


@router.post("/generate", dependencies=[Depends(verify_api_key)])
def generate_linkedin(req: LinkedInGenerateRequest, db: Session = Depends(get_db)):
    try:
        post = generate_linkedin_item(req.model_dump(), db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": str(post.id),
        "status": post.status.value,
        "approval_tier": post.approval_tier.value,
        "content": post.content,
        "hashtags": post.hashtags,
        "post_url": post.post_url,
    }


@router.get("/review", dependencies=[Depends(verify_api_key)])
def list_review_queue(db: Session = Depends(get_db)):
    posts = (
        db.query(LinkedInPost)
        .filter(
            LinkedInPost.status.in_(
                [LinkedInStatus.DRAFT, LinkedInStatus.NEEDS_REVIEW, LinkedInStatus.APPROVED]
            )
        )
        .order_by(LinkedInPost.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(post.id),
            "status": post.status.value,
            "approval_tier": post.approval_tier.value,
            "content": post.content,
        }
        for post in posts
    ]


@router.get("/published", dependencies=[Depends(verify_api_key)])
def list_linkedin_published(db: Session = Depends(get_db)):
    posts = db.query(LinkedInPost).filter(LinkedInPost.status == LinkedInStatus.PUBLISHED).all()
    return [
        {
            "id": str(post.id),
            "content": post.content,
            "post_url": post.post_url,
            "linkedin_post_id": post.linkedin_post_id,
        }
        for post in posts
    ]


@router.get("/{post_id}", dependencies=[Depends(verify_api_key)])
def get_linkedin_post(post_id: str, db: Session = Depends(get_db)):
    post = db.query(LinkedInPost).filter(LinkedInPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="LinkedIn post not found")
    return {
        "id": str(post.id),
        "status": post.status.value,
        "approval_tier": post.approval_tier.value,
        "content": post.content,
        "post_url": post.post_url,
        "failure_reason": post.failure_reason,
    }


@router.post("/{post_id}/approve", dependencies=[Depends(verify_api_key)])
def approve_linkedin(post_id: str, db: Session = Depends(get_db)):
    post = db.query(LinkedInPost).filter(LinkedInPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="LinkedIn post not found")
    if post.status != LinkedInStatus.NEEDS_REVIEW:
        raise HTTPException(status_code=409, detail=f"Cannot approve from '{post.status.value}'")
    post = approve_linkedin_item(post, db)
    return {"id": str(post.id), "status": post.status.value}


@router.post("/{post_id}/reject", dependencies=[Depends(verify_api_key)])
def reject_linkedin(post_id: str, req: LinkedInReviewRequest, db: Session = Depends(get_db)):
    post = db.query(LinkedInPost).filter(LinkedInPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="LinkedIn post not found")
    if post.status not in {LinkedInStatus.NEEDS_REVIEW, LinkedInStatus.APPROVED}:
        raise HTTPException(status_code=409, detail=f"Cannot reject from '{post.status.value}'")
    post = reject_linkedin_item(post, req.notes, db)
    return {"id": str(post.id), "status": post.status.value}


@router.post("/{post_id}/publish", dependencies=[Depends(verify_api_key)])
def publish_linkedin(post_id: str, db: Session = Depends(get_db)):
    try:
        post = publish_linkedin_item(post_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "id": str(post.id),
        "status": post.status.value,
        "post_url": post.post_url,
        "linkedin_post_id": post.linkedin_post_id,
    }
