"""Seed expansion modules with real content via the existing service layer.

Calls Claude API through the workflow engine to generate:
- 2 science credibility records (advisor spotlights)
- 1 blog article (SEO content)
- 2 UGC testimonial requests (for high-scoring athletes)
- 1 repurposing fan-out (from best existing draft)

Revenue defaults (playbooks, goals) auto-create on first dashboard load.

Usage:
    python scripts/seed_expansion.py
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.science_credibility_service import ScienceCredibilityService
from app.services.blog_service import BlogService
from app.services.ugc_service import UGCService
from app.services.repurposing_service import RepurposingService
from app.services.revenue_service import RevenueService


def seed_revenue(db):
    """Trigger revenue defaults (playbooks + conversion goals)."""
    print("\n=== Revenue Defaults ===")
    svc = RevenueService(db)
    dashboard = svc.list_dashboard()
    print(f"  Playbooks: {len(dashboard['playbooks'])}")
    print(f"  Conversion goals: {len(dashboard['conversion_goals'])}")
    for pb in dashboard["playbooks"]:
        print(f"    - {pb['name']} ({pb['playbook_type']}, {pb['persona']})")
    db.commit()


def seed_science(db):
    """Generate advisor spotlight posts for the named science team."""
    print("\n=== Science Credibility ===")
    svc = ScienceCredibilityService(db)

    advisors = [
        {
            "advisor_name": "Dr. Ed Levine",
            "topic": "The Godfather of U.S. I/O Psychology designed the Clutch Factor framework",
            "source_focus": "Dr. Ed Levine's credentials and role in designing the Clutch Factor methodology",
            "source_notes": [
                "Dr. Ed Levine is known as the 'Godfather' of U.S. I/O Psychology",
                "He designed the Clutch Factor framework used by NTangible",
                "His methodology is validated, not self-reported like competitor assessments",
            ],
        },
        {
            "advisor_name": "Dr. Jacob Hyde",
            "topic": "Navy SEALs performance protocols applied to athlete assessment",
            "source_focus": "Dr. Jacob Hyde's military performance background and its application to sports",
            "source_notes": [
                "Dr. Jacob Hyde developed performance protocols for Navy SEALs",
                "His work bridges military pressure performance and athletic clutch moments",
                "NTangible's assessment draws from validated high-stakes performance research",
            ],
        },
    ]

    for advisor in advisors:
        print(f"  Generating spotlight: {advisor['advisor_name']}...")
        try:
            result = svc.generate_science_content(
                "advisor_spotlight",
                platform="linkedin",
                actor="science",
                topic=advisor["topic"],
                audience="coaches, front offices, and investors",
                source_focus=advisor["source_focus"],
                source_notes=advisor["source_notes"],
                advisor_name=advisor["advisor_name"],
            )
            db.commit()
            print(f"    Created: {result['title']} (status: {result['status']})")
        except Exception as e:
            db.rollback()
            print(f"    Failed: {e}")


def seed_blog(db):
    """Generate an SEO blog article targeting key search terms."""
    print("\n=== Blog & SEO ===")
    svc = BlogService(db)

    print("  Generating blog article: transfer portal mental performance...")
    try:
        result = svc.generate_draft(
            topic="Why Transfer Portal Failures Are Mental Performance Failures",
            audience="D1 college coaches and recruiting coordinators",
            target_keywords=[
                "transfer portal failure rate",
                "college recruiting mental evaluation",
                "pressure performance assessment",
                "clutch factor sports",
            ],
            angle="Data shows most transfer busts aren't talent misses — they're pressure misses. Programs that measure mental performance before recruiting see significantly better retention.",
            source_notes=[
                "73% of athletes scoring above 800 CF were named All-American",
                "Failed D1 transfer costs approximately $150K",
                "NTangible's Clutch Factor measures performance under pressure, not personality traits",
                "Michigan State, Hofstra, and Boston College use Clutch Factor data in recruiting decisions",
            ],
        )
        db.commit()
        print(f"    Created: {result.get('title', 'untitled')} (status: {result.get('status', 'unknown')})")
    except Exception as e:
        db.rollback()
        print(f"    Failed: {e}")


def seed_ugc(db):
    """Create UGC testimonial requests for high-scoring athletes."""
    print("\n=== UGC & Testimonials ===")
    svc = UGCService(db)

    athletes = [
        {
            "athlete_name": "Sarah Mitchell",
            "score": 865,
            "athlete_email": "s.mitchell@example.com",
            "parent_name": "Jennifer Mitchell",
            "parent_email": "j.mitchell@example.com",
            "athlete_age": 17,
            "sport": "fastpitch",
            "context": "Alliance Fastpitch July testing window — top 5% Clutch Factor score",
            "source_partner": "alliance_fastpitch",
        },
        {
            "athlete_name": "Marcus Rivera",
            "score": 912,
            "athlete_email": "m.rivera@example.com",
            "parent_name": "Carlos Rivera",
            "parent_email": "c.rivera@example.com",
            "athlete_age": 16,
            "sport": "baseball",
            "context": "FSS Southeast Regional — highest Clutch Factor score of the event",
            "source_partner": "future_stars_series",
        },
    ]

    for athlete in athletes:
        print(f"  Creating testimonial request: {athlete['athlete_name']} (CF: {athlete['score']})...")
        try:
            result = svc.create_testimonial_request(**athlete)
            db.commit()
            print(f"    Created: {result['athlete_name']} — tier: {result['score_tier']}, status: {result['status']}")
        except Exception as e:
            db.rollback()
            print(f"    Failed: {e}")


def seed_repurposing(db):
    """Take the best existing draft and fan it out across platforms."""
    print("\n=== Content Repurposing ===")
    svc = RepurposingService(db)

    # Find the best published draft to repurpose
    from app.models.review import DraftVariant
    from app.models.workflow import DraftState
    draft = (
        db.query(DraftVariant)
        .filter(DraftVariant.state == DraftState.PUBLISHED)
        .order_by(DraftVariant.created_at.desc())
        .first()
    )

    if draft is None:
        # Fall back to any manual_ready draft
        draft = (
            db.query(DraftVariant)
            .filter(DraftVariant.state == DraftState.MANUAL_READY)
            .order_by(DraftVariant.created_at.desc())
            .first()
        )

    if draft is None:
        print("  No existing drafts to repurpose. Skipping.")
        return

    print(f"  Repurposing draft: {draft.content[:80]}...")
    # Only fan out to platforms the source isn't already on
    source_platform = draft.platform.value if hasattr(draft.platform, "value") else str(draft.platform)
    target_channels = [ch for ch in ["linkedin", "instagram", "newsletter"] if ch != source_platform]

    try:
        result = svc.repurpose_draft(
            str(draft.id),
            target_platforms=target_channels,
        )
        db.commit()
        print(f"    Source: {result[0].get('title', 'unknown') if result else 'no derivatives'}")
        print(f"    Derivatives created: {len(result)}")
        for d in result:
            print(f"      - {d.get('channel', '?')}: {d.get('title', 'untitled')}")
    except Exception as e:
        db.rollback()
        print(f"    Failed: {e}")


def main():
    print("NTangible Marketing Engine — Expansion Seed")
    print("=" * 50)

    db = SessionLocal()
    try:
        seed_revenue(db)
        seed_science(db)
        seed_blog(db)
        seed_ugc(db)
        seed_repurposing(db)

        print("\n" + "=" * 50)
        print("Seed complete. Check /control-room/expansion and /control-room/revenue")
    finally:
        db.close()


if __name__ == "__main__":
    main()
