"""
Clean the NTangible Marketing database of all fake/seed data and set up
real production data (workflow configs, sports calendar, revenue playbooks).

Usage:
    uv run python scripts/setup_production.py
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import text

from app.database import SessionLocal
from app.models.analytics import (
    AnalyticsSnapshot,
    DraftAnalyticsSnapshot,
    PublicationRecord,
    WorkflowAnalyticsSnapshot,
    WorkflowMetric,
)
from app.models.memory import MemoryItem
from app.models.review import ContentJob, DraftVariant, ReviewAction
from app.models.revenue import (
    ConversionEvent,
    ConversionGoal,
    RevenueExecution,
    RevenuePlaybook,
    SalesEnablementPackage,
)
from app.models.sports import SportsCalendarWindow, SportsStageRun
from app.models.trigger import CalendarRule, TriggerEvent
from app.models.workflow import Platform, Workflow, WorkflowMode, WorkflowVersion
from app.schemas.workflow_config import WorkflowVersionConfig

NOW = datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────────────
# A) Delete all fake seed data
# ──────────────────────────────────────────────────────────────────────

def clean_seed_data(db):
    """Delete all fake content/analytics rows while preserving real config."""
    print("\n=== Cleaning seed data ===")

    # Order matters: delete children before parents
    deletion_targets = [
        # Analytics
        (AnalyticsSnapshot, "analytics_snapshots"),
        (DraftAnalyticsSnapshot, "draft_analytics_snapshots"),
        (WorkflowAnalyticsSnapshot, "workflow_analytics_snapshots"),
        (WorkflowMetric, "workflow_metrics"),
        (PublicationRecord, "publication_records"),
        # Revenue executions (FK to content_jobs / trigger_events)
        (SalesEnablementPackage, "sales_enablement_packages"),
        (RevenueExecution, "revenue_executions"),
        (ConversionEvent, "conversion_events"),
        # Sports stage runs (FK to content_jobs / trigger_events)
        (SportsStageRun, "sports_stage_runs"),
        # Review
        (ReviewAction, "review_actions"),
        # Memory items that came from seed (draft_variant source or trigger_event source)
        # We delete all memory items that reference draft_variants (those are seed-generated)
        # We keep content_brain and other non-draft memories
    ]

    for model, label in deletion_targets:
        try:
            n = db.query(model).delete()
            if n:
                print(f"  Deleted {n} rows from {label}")
        except Exception as e:
            print(f"  Warning: could not clean {label}: {e}")
            db.rollback()

    # Delete memory items that reference draft variants (seed data)
    n = db.query(MemoryItem).filter(
        MemoryItem.draft_variant_id.isnot(None)
    ).delete(synchronize_session="fetch")
    if n:
        print(f"  Deleted {n} draft-sourced memory_items")

    # Delete memory items with source_kind = 'trigger_event' (seed-generated)
    from app.models.memory import MemorySourceKind
    n = db.query(MemoryItem).filter(
        MemoryItem.source_kind == MemorySourceKind.TRIGGER_EVENT
    ).delete(synchronize_session="fetch")
    if n:
        print(f"  Deleted {n} trigger_event memory_items")

    # Delete seed-generated content_brain memory items (have details.origin == 'content_brain')
    # These were fake; real content_brain items come from the ingest scripts
    n = db.query(MemoryItem).filter(
        MemoryItem.source_kind == MemorySourceKind.CONTENT_BRAIN,
        MemoryItem.details["origin"].astext == "content_brain",
    ).delete(synchronize_session="fetch")
    if n:
        print(f"  Deleted {n} seed content_brain memory_items")

    # Draft variants and content jobs
    n = db.query(DraftVariant).delete()
    if n:
        print(f"  Deleted {n} draft_variants")

    n = db.query(ContentJob).delete()
    if n:
        print(f"  Deleted {n} content_jobs")

    # Trigger events (clear, keep the structure)
    n = db.query(TriggerEvent).delete()
    if n:
        print(f"  Deleted {n} trigger_events")

    db.flush()
    print("  Seed data cleaned.")


# ──────────────────────────────────────────────────────────────────────
# B) Verify and update the 6 workflow version configs
# ──────────────────────────────────────────────────────────────────────

BLUEPRINT_CONFIGS = {
    "tuesday-thought-leadership": WorkflowVersionConfig(
        prompt={
            "system_prompt_additions": (
                "You are the NTangible brand voice on LinkedIn. NTangible builds mental performance "
                "technology for competitive sports -- Clutch Factor is our proprietary cognitive assessment "
                "measuring composure, adaptability, and competitive drive under pressure. Our audience is "
                "D1/D2 coaching staffs, recruiting coordinators, and front offices. Write thought leadership "
                "that positions NTangible as the authority on mental performance in sports. Be opinionated, "
                "data-backed, and contrarian. Sound like a smart person who works in sports, not a brand account."
            ),
            "tone_notes": (
                "Punchy. Contrarian. Sports bar meets data lab. Short direct sentences. Lead with data-backed "
                "claims. Be opinionated and take a position. No passive voice, no exclamation points, no fluffy "
                "motivational language, no corporate buzzwords. Never sound like a press release."
            ),
            "example_angles": [
                "Every coaching staff says they value mental toughness. How many actually measure it?",
                "Personality profiles don't predict performance under pressure. Clutch Factor does.",
                "Film tells you what happened. Not what happens when it counts.",
                "Coach Alignment Index -- the feature nobody else has.",
            ],
        },
        routing={
            "target_content_type": "thought_leadership",
            "target_pillar": "thought_leadership",
            "target_intent": "brand",
            "target_audience_segment": "coaching_staffs",
        },
        formatting={
            "max_hashtags": 5,
            "max_chars": 3000,
        },
        cta={
            "cta_preferences": [
                "Learn how programs are using Clutch Factor data in recruiting",
                "See how mental performance data changes the recruiting conversation",
                "Request a demo to see Clutch Factor in action",
            ],
            "cta_rules": "CTA should be educational, not sales-forward. Invite curiosity, not pressure.",
        },
        retrieval={
            "max_examples": 5,
            "filter_by_pillar": True,
            "include_campaign_context": True,
            "include_revenue_context": False,
            "include_market_signals": True,
        },
        timing={
            "recommended_post_hour_utc": 11,
            "publish_delay_minutes": 0,
        },
        assets={
            "asset_instructions": "",
            "require_image": False,
        },
    ).model_dump(),

    "fss-leaderboard-data-drop": WorkflowVersionConfig(
        prompt={
            "system_prompt_additions": (
                "You are the NTangible brand voice on X (Twitter). NTangible builds mental performance "
                "technology for competitive sports. Clutch Factor is our proprietary cognitive assessment. "
                "This workflow creates data drop posts sharing Future Stars Series leaderboard updates -- "
                "showcase results, Clutch Factor rankings, and standout athlete stats. The audience is "
                "college coaches, recruiting coordinators, club directors, and the softball community. "
                "Be concise, data-forward, and credible. Every post should contain a real stat or ranking angle."
            ),
            "tone_notes": (
                "Data-forward and credible. Concise -- this is X, not LinkedIn. Lead with the most "
                "interesting stat. Sound like a knowledgeable insider sharing fresh data, not a press release. "
                "No superlatives, no hype language. Let the numbers speak."
            ),
            "example_angles": [
                "FSS leaderboard update: 247 athletes across 12 showcases. Top Clutch Factor scores from the Southeast regional.",
                "Mid-week data drop: 62 new Clutch Factor profiles from the Midwest regional.",
                "Showcase season is live. The leaderboard data is now visible to college coaches.",
            ],
        },
        routing={
            "target_content_type": "data_drop",
            "target_pillar": "client_proof",
            "target_intent": "brand",
            "target_audience_segment": "coaches_and_scouts",
        },
        formatting={
            "max_hashtags": 2,
            "max_chars": 280,
        },
        cta={
            "cta_preferences": [
                "Full rankings at [link]",
                "See the full leaderboard",
            ],
            "cta_rules": "Keep CTA short. One line max. Link to leaderboard when available.",
        },
        retrieval={
            "max_examples": 3,
            "filter_by_intent": True,
            "include_campaign_context": True,
            "include_revenue_context": True,
            "include_market_signals": False,
        },
        timing={
            "recommended_post_hour_utc": 16,
            "publish_delay_minutes": 0,
        },
        assets={
            "asset_instructions": "",
            "require_image": False,
        },
    ).model_dump(),

    "athlete-commitment-spotlight": WorkflowVersionConfig(
        prompt={
            "system_prompt_additions": (
                "You are the NTangible brand voice on Instagram. This workflow celebrates athlete commitments -- "
                "when a club/showcase athlete with a Clutch Factor profile commits to a college program. "
                "The tone is celebratory but grounded. Always lead with the athlete, not the product. "
                "Include the athlete's Clutch Factor percentile if available. Tag the partner organization "
                "(Alliance Fastpitch, Future Stars Series, etc.) and the college program. "
                "NTangible builds mental performance technology for competitive sports."
            ),
            "tone_notes": (
                "Celebratory, authentic, athlete-first. Highlight the commitment, mention Clutch Factor "
                "data as supporting context (not the headline). Instagram audience expects warmth and "
                "specificity. No corporate language. Genuine congratulations, then the data angle."
            ),
            "example_angles": [
                "Commitment spotlight: Congrats to [athlete] on committing to [school]. [Clutch Factor stat].",
                "Another [partner] athlete headed to the next level. [School] gets a competitor.",
                "[Athlete] posted a [percentile] Clutch Factor score at [event]. Now committed to [school].",
            ],
        },
        routing={
            "target_content_type": "partner_spotlight",
            "target_pillar": "client_proof",
            "target_intent": "partner",
            "target_audience_segment": "athletes_parents_clubs",
        },
        formatting={
            "max_hashtags": 10,
            "max_chars": 2200,
        },
        cta={
            "cta_preferences": [
                "Get your Clutch Factor score at your next showcase",
                "Link in bio to find upcoming assessment events",
                "Tag an athlete who deserves the spotlight",
            ],
            "cta_rules": "CTA should feel organic to Instagram. Invite engagement, not hard sell.",
        },
        retrieval={
            "max_examples": 5,
            "filter_by_intent": True,
            "include_campaign_context": True,
            "include_revenue_context": False,
            "include_market_signals": False,
        },
        timing={
            "recommended_post_hour_utc": 17,
            "publish_delay_minutes": 0,
        },
        assets={
            "asset_instructions": "Render a commitment graphic using the athlete_spotlight or commitment_post template family. Include athlete name, school logo, Clutch Factor score badge.",
            "require_image": True,
            "image_style_notes": "Bold black/yellow NTangible brand palette. Clean typography. Athlete name prominent.",
        },
    ).model_dump(),

    "weekly-newsletter-digest": WorkflowVersionConfig(
        prompt={
            "system_prompt_additions": (
                "You are writing the NTangible weekly newsletter. The audience is two segments: "
                "(1) coaches and front offices who use or are evaluating Clutch Factor, and "
                "(2) partner organizations (event directors, club directors) who integrate NTangible assessments. "
                "The newsletter should feel like a smart weekly briefing from someone on the inside of sports "
                "mental performance -- not a marketing email. Include a mix of data insights, partner spotlights, "
                "product updates, and industry commentary. 2-4 sections. Subject line under 90 chars."
            ),
            "tone_notes": (
                "Insider briefing tone. Concise, informative, slightly opinionated. Each section should "
                "have a clear hook and a reason to keep reading. No fluff. No 'exciting update' phrasing. "
                "Write like a smart newsletter author (think The Hustle meets sports analytics), not a brand."
            ),
            "example_angles": [
                "This week: new Clutch Factor benchmarks, SEC programs using mental performance data in recruiting, partner spotlight on Alliance Fastpitch.",
                "Portal season data drop, what coaches are asking us about commitment predictions, and a launch date for the portal tracker.",
                "Three things we learned from 500 assessments at FSS regionals.",
            ],
        },
        routing={
            "target_content_type": "newsletter",
            "target_pillar": None,
            "target_intent": "brand",
            "target_audience_segment": "coaches_and_partners",
        },
        formatting={
            "max_hashtags": 0,
            "max_chars": 4000,
            "require_subject_line": True,
            "max_sections": 4,
        },
        cta={
            "cta_preferences": [
                "Reply to this email with your take",
                "Forward this to your recruiting coordinator",
                "Book a 15-minute walkthrough of the new features",
            ],
            "cta_rules": "One CTA per newsletter. Make it conversational. Avoid 'click here' or 'sign up now'.",
        },
        retrieval={
            "max_examples": 5,
            "filter_by_pillar": False,
            "include_campaign_context": True,
            "include_revenue_context": True,
            "include_market_signals": True,
        },
        timing={
            "recommended_post_hour_utc": 13,
            "publish_delay_minutes": 0,
        },
        assets={
            "asset_instructions": "",
            "require_image": False,
        },
    ).model_dump(),

    "transfer-portal-hot-take": WorkflowVersionConfig(
        prompt={
            "system_prompt_additions": (
                "You are the NTangible brand voice on X (Twitter). This workflow covers transfer portal "
                "hot takes -- opinionated, data-backed commentary on portal movement and how mental performance "
                "data changes the evaluation game. The audience is college coaches, recruiting coordinators, "
                "NIL collectives, and the college sports community. Be bold, take a position, back it with data. "
                "NTangible builds mental performance technology; Clutch Factor is our proprietary assessment."
            ),
            "tone_notes": (
                "Hot take energy with data backing. Opinionated, direct, slightly provocative. "
                "This is X -- be concise. One strong point per post. No hedging. No 'we think' -- "
                "state it like a fact backed by evidence. Sound like a sharp analyst, not a brand."
            ),
            "example_angles": [
                "The portal is not broken. Evaluation is broken.",
                "Programs with Clutch Factor data make portal offers 3x faster.",
                "Hot take: most portal busts are evaluation failures, not athlete failures.",
            ],
        },
        routing={
            "target_content_type": "hot_take",
            "target_pillar": "cost_of_guessing",
            "target_intent": "brand",
            "target_audience_segment": "coaching_staffs",
        },
        formatting={
            "max_hashtags": 2,
            "max_chars": 280,
        },
        cta={
            "cta_preferences": [
                "See how Clutch Factor data changes portal decisions",
                "The data is free for programs that ask",
            ],
            "cta_rules": "CTA optional on hot takes. If included, keep it one line. Never overshadow the take.",
        },
        retrieval={
            "max_examples": 3,
            "filter_by_pillar": True,
            "include_campaign_context": True,
            "include_revenue_context": False,
            "include_market_signals": True,
        },
        timing={
            "recommended_post_hour_utc": 15,
            "publish_delay_minutes": 0,
        },
        assets={
            "asset_instructions": "",
            "require_image": False,
        },
    ).model_dump(),

    "partner-roi-summary": WorkflowVersionConfig(
        prompt={
            "system_prompt_additions": (
                "You are the NTangible brand voice on LinkedIn. This workflow creates partner ROI summary "
                "posts -- sharing results and outcomes from NTangible partnerships with organizations like "
                "Alliance Fastpitch, Future Stars Series, and college programs. The audience is prospective "
                "partners, current partners, D1/D2 coaching staffs, and sports business decision-makers. "
                "Lead with measurable outcomes. Use approved claims only. Sound credible and specific."
            ),
            "tone_notes": (
                "Results-driven, specific, credible. LinkedIn professional tone but still NTangible voice -- "
                "direct, no fluff, data-first. This is the proof post: show the ROI, let the numbers make "
                "the case. Avoid vague claims. Every statement should be backed by a specific metric or result."
            ),
            "example_angles": [
                "Alliance Fastpitch year-one results: 12 partner orgs, 340 athletes assessed, 47 commitments with Clutch Factor data attached.",
                "Q1 partner ROI: programs using Clutch Factor saw 28% reduction in early transfer departures.",
                "30,000+ athletes assessed through Alliance Fastpitch. Coaches say the mental performance profile is the first thing they open.",
            ],
        },
        routing={
            "target_content_type": "partner_report",
            "target_pillar": "client_proof",
            "target_intent": "revenue",
            "target_audience_segment": "partners_and_prospects",
        },
        formatting={
            "max_hashtags": 5,
            "max_chars": 3000,
        },
        cta={
            "cta_preferences": [
                "See what a partnership looks like -- request the one-pager",
                "Book a call to discuss partnership ROI for your organization",
                "DM for the full partner outcomes report",
            ],
            "cta_rules": "CTA should invite partnership conversation. Professional but direct. One CTA per post.",
        },
        retrieval={
            "max_examples": 5,
            "filter_by_pillar": True,
            "include_campaign_context": True,
            "include_revenue_context": True,
            "include_market_signals": True,
        },
        timing={
            "recommended_post_hour_utc": 14,
            "publish_delay_minutes": 0,
        },
        assets={
            "asset_instructions": "",
            "require_image": False,
        },
    ).model_dump(),
}


def verify_and_update_workflow_configs(db):
    """Verify the 6 workflows exist and update their active version configs."""
    print("\n=== Verifying workflow configs ===")

    expected_workflows = {
        "tuesday-thought-leadership": {
            "name": "Tuesday Thought Leadership",
            "platform": Platform.LINKEDIN,
            "mode": WorkflowMode.MANUAL,
            "content_type": "thought_leadership",
        },
        "fss-leaderboard-data-drop": {
            "name": "FSS Leaderboard Data Drop",
            "platform": Platform.X,
            "mode": WorkflowMode.AUTOMATIC,
            "content_type": "data_drop",
        },
        "athlete-commitment-spotlight": {
            "name": "Athlete Commitment Spotlight",
            "platform": Platform.INSTAGRAM,
            "mode": WorkflowMode.MANUAL,
            "content_type": "partner_spotlight",
        },
        "weekly-newsletter-digest": {
            "name": "Weekly Newsletter Digest",
            "platform": Platform.NEWSLETTER,
            "mode": WorkflowMode.MANUAL,
            "content_type": "newsletter",
        },
        "transfer-portal-hot-take": {
            "name": "Transfer Portal Hot Take",
            "platform": Platform.X,
            "mode": WorkflowMode.MANUAL,
            "content_type": "hot_take",
        },
        "partner-roi-summary": {
            "name": "Partner ROI Summary",
            "platform": Platform.LINKEDIN,
            "mode": WorkflowMode.AUTOMATIC,
            "content_type": "partner_report",
        },
    }

    for slug, spec in expected_workflows.items():
        wf = db.query(Workflow).filter(Workflow.slug == slug).first()

        if not wf:
            print(f"  MISSING workflow '{slug}' -- creating it")
            wf = Workflow(
                id=uuid.uuid4(),
                name=spec["name"],
                slug=slug,
                description=spec["name"],
                mode=spec["mode"],
                platform=spec["platform"],
                content_type=spec["content_type"],
                enabled=True,
                health_status="healthy",
            )
            db.add(wf)
            db.flush()
        else:
            # Verify platform and mode match
            changed = False
            if wf.platform != spec["platform"]:
                print(f"  Fixing {slug} platform: {wf.platform} -> {spec['platform']}")
                wf.platform = spec["platform"]
                changed = True
            if wf.mode != spec["mode"]:
                print(f"  Fixing {slug} mode: {wf.mode} -> {spec['mode']}")
                wf.mode = spec["mode"]
                changed = True
            if wf.content_type != spec["content_type"]:
                print(f"  Fixing {slug} content_type: {wf.content_type} -> {spec['content_type']}")
                wf.content_type = spec["content_type"]
                changed = True
            # Clear seed-era timestamps
            wf.last_run_at = None
            wf.last_success_at = None
            wf.last_error = None
            wf.health_status = "healthy"
            if not changed:
                print(f"  OK: {slug} ({spec['platform'].value}, {spec['mode'].value})")

        # Now update or create the active WorkflowVersion config
        blueprint_config = BLUEPRINT_CONFIGS.get(slug)
        if not blueprint_config:
            print(f"  WARNING: no Blueprint config for {slug}")
            continue

        active_version = None
        if wf.active_version_id:
            active_version = db.query(WorkflowVersion).filter(
                WorkflowVersion.id == wf.active_version_id
            ).first()

        if active_version:
            # Update the config
            active_version.config = blueprint_config
            active_version.version_note = "Production config from Blueprint"
            print(f"  Updated config for {slug} v{active_version.version_number}")
        else:
            # Create version 1
            v = WorkflowVersion(
                id=uuid.uuid4(),
                workflow_id=wf.id,
                version_number=1,
                config=blueprint_config,
                version_note="Production config from Blueprint",
                author="elliot",
                is_active=True,
            )
            db.add(v)
            db.flush()
            wf.active_version_id = v.id
            print(f"  Created version 1 for {slug}")

    db.flush()


# ──────────────────────────────────────────────────────────────────────
# C) Load sports calendar data
# ──────────────────────────────────────────────────────────────────────

SPORTS_CALENDAR_ENTRIES = [
    {
        "slug": "nfl-draft-2026",
        "title": "2026 NFL Draft",
        "sport": "football",
        "window_type": "draft",
        "start_date": date(2026, 4, 23),
        "end_date": date(2026, 4, 25),
        "content_bucket": "draft_season",
        "template_key": "draft_coverage",
        "default_platforms": ["x", "linkedin"],
        "summary": "2026 NFL Draft. Peak visibility for mental performance in draft evaluation conversation.",
        "stage_angle": "Position NTangible as the mental performance data layer that draft rooms are missing. Emphasize Clutch Factor as the cognitive scouting tool for pressure situations.",
        "metadata_json": {"league": "NFL", "location": "TBD"},
    },
    {
        "slug": "mlb-draft-2026",
        "title": "2026 MLB Draft",
        "sport": "baseball",
        "window_type": "draft",
        "start_date": date(2026, 7, 12),
        "end_date": date(2026, 7, 14),
        "content_bucket": "draft_season",
        "template_key": "draft_coverage",
        "default_platforms": ["x", "linkedin"],
        "summary": "2026 MLB Draft. Opportunity to position Clutch Factor in the baseball draft conversation.",
        "stage_angle": "Mental performance under pressure matters most in baseball -- at-bat composure, mound pressure, defensive focus. Clutch Factor quantifies what scouts call 'makeup'.",
        "metadata_json": {"league": "MLB"},
    },
    {
        "slug": "nba-draft-2026",
        "title": "2026 NBA Draft",
        "sport": "basketball",
        "window_type": "draft",
        "start_date": date(2026, 6, 25),
        "end_date": date(2026, 6, 26),
        "content_bucket": "draft_season",
        "template_key": "draft_coverage",
        "default_platforms": ["x", "linkedin"],
        "summary": "2026 NBA Draft. Mental performance angle in draft coverage.",
        "stage_angle": "The NBA draft bust rate is the most expensive in sports. Clutch Factor measures what combine testing cannot -- decision-making under game pressure.",
        "metadata_json": {"league": "NBA"},
    },
    {
        "slug": "college-transfer-portal-spring-2026",
        "title": "College Transfer Portal -- Spring Window",
        "sport": "multi-sport",
        "window_type": "transfer_portal",
        "start_date": date(2026, 4, 1),
        "end_date": date(2026, 5, 31),
        "content_bucket": "portal_season",
        "template_key": "portal_hot_take",
        "default_platforms": ["x", "linkedin"],
        "summary": "Spring 2026 transfer portal window. Peak portal movement across all sports, especially softball and baseball.",
        "stage_angle": "The portal rewards programs that do their homework. Clutch Factor data gives coaching staffs the mental performance baseline before the first visit. Position NTangible as the evaluation edge in portal decisions.",
        "metadata_json": {"sports": ["softball", "baseball", "basketball"]},
    },
    {
        "slug": "nfl-combine-2026",
        "title": "2026 NFL Scouting Combine",
        "sport": "football",
        "window_type": "combine",
        "start_date": date(2026, 2, 23),
        "end_date": date(2026, 3, 3),
        "content_bucket": "combine_season",
        "template_key": "combine_commentary",
        "default_platforms": ["x", "linkedin"],
        "summary": "2026 NFL Combine. High-visibility moment for the 'what the combine misses' narrative.",
        "stage_angle": "The combine measures the physical. Clutch Factor measures the mental. Every year, combine heroes bust and late-round picks become stars. Mental performance is the missing variable.",
        "metadata_json": {"league": "NFL", "location": "Indianapolis"},
    },
    {
        "slug": "march-madness-2026",
        "title": "2026 March Madness (NCAA Basketball Tournament)",
        "sport": "basketball",
        "window_type": "tournament",
        "start_date": date(2026, 3, 17),
        "end_date": date(2026, 4, 6),
        "content_bucket": "tournament_season",
        "template_key": "tournament_commentary",
        "default_platforms": ["x", "linkedin"],
        "summary": "2026 NCAA March Madness. The biggest stage for pressure performance in college sports.",
        "stage_angle": "March Madness is a natural laboratory for Clutch Factor. Pressure makes or breaks tournament runs. Use real-time examples to illustrate composure, adaptability, and competitive drive under tournament pressure.",
        "metadata_json": {"league": "NCAA", "sport": "basketball"},
    },
    {
        "slug": "college-world-series-2026",
        "title": "2026 College World Series",
        "sport": "baseball",
        "window_type": "tournament",
        "start_date": date(2026, 6, 13),
        "end_date": date(2026, 6, 25),
        "content_bucket": "tournament_season",
        "template_key": "tournament_commentary",
        "default_platforms": ["x", "linkedin"],
        "summary": "2026 College World Series. Peak moment for baseball mental performance conversation.",
        "stage_angle": "Omaha is where pressure separates. Every at-bat is magnified. Clutch Factor measures exactly what shows up on this stage -- composure under elimination-game pressure.",
        "metadata_json": {"league": "NCAA", "sport": "baseball", "location": "Omaha"},
    },
    {
        "slug": "alliance-fastpitch-testing-summer-2026",
        "title": "Alliance Fastpitch Testing Window -- Summer 2026",
        "sport": "softball",
        "window_type": "partner_assessment",
        "start_date": date(2026, 7, 1),
        "end_date": date(2026, 8, 31),
        "content_bucket": "partner_assessment",
        "template_key": "partner_event_spotlight",
        "default_platforms": ["x", "instagram", "linkedin", "newsletter"],
        "summary": "Alliance Fastpitch summer testing window. Peak assessment volume for Clutch Factor across club softball.",
        "stage_angle": "Summer showcase season is assessment season. Alliance Fastpitch athletes getting their Clutch Factor scores before college coaches start fall recruiting. Drive athlete sign-ups and partner org engagement.",
        "metadata_json": {"partner": "Alliance Fastpitch", "assessment_type": "clutch_factor"},
    },
    {
        "slug": "alliance-fastpitch-retest-dec-2026",
        "title": "Alliance Fastpitch Re-test Window -- December 2026",
        "sport": "softball",
        "window_type": "partner_assessment",
        "start_date": date(2026, 12, 1),
        "end_date": date(2026, 12, 31),
        "content_bucket": "partner_assessment",
        "template_key": "partner_event_spotlight",
        "default_platforms": ["x", "instagram", "linkedin", "newsletter"],
        "summary": "Alliance Fastpitch December re-test window. Athletes re-take Clutch Factor to show growth before spring recruiting.",
        "stage_angle": "Growth narrative: athletes who retested and improved their Clutch Factor scores. Demonstrate that mental performance is trainable and measurable. Drive re-test sign-ups.",
        "metadata_json": {"partner": "Alliance Fastpitch", "assessment_type": "clutch_factor_retest"},
    },
    {
        "slug": "fss-southeast-regional-apr-2026",
        "title": "FSS Southeast Regional -- April 2026",
        "sport": "softball",
        "window_type": "partner_event",
        "start_date": date(2026, 4, 11),
        "end_date": date(2026, 4, 13),
        "content_bucket": "partner_event",
        "template_key": "partner_event_spotlight",
        "default_platforms": ["x", "instagram"],
        "summary": "Future Stars Series Southeast Regional. Clutch Factor assessments and leaderboard data drop.",
        "stage_angle": "Live showcase data. Post leaderboard updates, highlight standout Clutch Factor scores, spotlight athletes who stood out under pressure.",
        "metadata_json": {"partner": "Future Stars Series", "region": "Southeast"},
    },
    {
        "slug": "fss-midwest-regional-may-2026",
        "title": "FSS Midwest Regional -- May 2026",
        "sport": "softball",
        "window_type": "partner_event",
        "start_date": date(2026, 5, 16),
        "end_date": date(2026, 5, 18),
        "content_bucket": "partner_event",
        "template_key": "partner_event_spotlight",
        "default_platforms": ["x", "instagram"],
        "summary": "Future Stars Series Midwest Regional. Clutch Factor assessments and leaderboard data drop.",
        "stage_angle": "Live showcase data from the Midwest. Leaderboard updates, standout performers, and Clutch Factor highlights.",
        "metadata_json": {"partner": "Future Stars Series", "region": "Midwest"},
    },
    {
        "slug": "fss-west-regional-jun-2026",
        "title": "FSS West Regional -- June 2026",
        "sport": "softball",
        "window_type": "partner_event",
        "start_date": date(2026, 6, 6),
        "end_date": date(2026, 6, 8),
        "content_bucket": "partner_event",
        "template_key": "partner_event_spotlight",
        "default_platforms": ["x", "instagram"],
        "summary": "Future Stars Series West Regional. Clutch Factor assessments and leaderboard data drop.",
        "stage_angle": "West Coast showcase data. Leaderboard updates and Clutch Factor highlights from the West regional.",
        "metadata_json": {"partner": "Future Stars Series", "region": "West"},
    },
    {
        "slug": "mit-sloan-sports-conference-2026",
        "title": "MIT Sloan Sports Analytics Conference 2026",
        "sport": "multi-sport",
        "window_type": "conference",
        "start_date": date(2026, 3, 6),
        "end_date": date(2026, 3, 7),
        "content_bucket": "industry_event",
        "template_key": "conference_commentary",
        "default_platforms": ["x", "linkedin"],
        "summary": "MIT Sloan Sports Analytics Conference. Premier sports analytics gathering -- NTangible thought leadership moment.",
        "stage_angle": "Position NTangible in the analytics conversation. Mental performance is the next frontier in sports analytics. Engage with conference themes and position Clutch Factor as science-backed, not survey-based.",
        "metadata_json": {"event": "MIT Sloan", "location": "Boston"},
    },
    {
        "slug": "web-summit-2026",
        "title": "Web Summit 2026",
        "sport": "multi-sport",
        "window_type": "conference",
        "start_date": date(2026, 11, 2),
        "end_date": date(2026, 11, 5),
        "content_bucket": "industry_event",
        "template_key": "conference_commentary",
        "default_platforms": ["x", "linkedin"],
        "summary": "Web Summit 2026. Global tech conference -- opportunity to position NTangible in the sports-tech conversation.",
        "stage_angle": "NTangible at Web Summit: sports-tech, cognitive assessment, and the future of athlete evaluation. Position as a deep-tech sports company, not just an analytics dashboard.",
        "metadata_json": {"event": "Web Summit", "location": "Lisbon"},
    },
]


def load_sports_calendar(db):
    """Insert sports calendar windows, upserting by slug."""
    print("\n=== Loading sports calendar ===")

    created = 0
    updated = 0
    for entry in SPORTS_CALENDAR_ENTRIES:
        existing = db.query(SportsCalendarWindow).filter(
            SportsCalendarWindow.slug == entry["slug"]
        ).first()

        if existing:
            for key, val in entry.items():
                setattr(existing, key, val)
            updated += 1
        else:
            obj = SportsCalendarWindow(id=uuid.uuid4(), **entry)
            db.add(obj)
            created += 1

    db.flush()
    print(f"  Created {created} sports calendar windows, updated {updated}")


# ──────────────────────────────────────────────────────────────────────
# D) Ensure revenue playbooks exist
# ──────────────────────────────────────────────────────────────────────

REVENUE_PLAYBOOKS = [
    {
        "slug": "demo-request-thought-leadership",
        "name": "Demo Request via Thought Leadership",
        "description": "Drive demo requests from coaching staffs through LinkedIn thought leadership content that establishes NTangible as the authority on mental performance measurement.",
        "playbook_type": "inbound_demo",
        "workflow_slug": "tuesday-thought-leadership",
        "target_output": "demo_request",
        "persona": "D1/D2 Head Coach or Recruiting Coordinator",
        "offer": "See how Clutch Factor data changes your recruiting conversations. 15-minute walkthrough.",
        "cta": "Request a demo to see Clutch Factor in action",
        "default_audience": "D1/D2 coaching staffs, recruiting coordinators evaluating mental performance tools",
        "default_proof_points": [
            "73% of athletes scoring above 800 CF were named All-American",
            "6,000+ assessments. 1M+ data points. 7 sports.",
            "Programs using Clutch Factor make portal offers 3x faster",
        ],
    },
    {
        "slug": "partner-expansion-roi",
        "name": "Partner Expansion via ROI Evidence",
        "description": "Expand partnerships by sharing measurable ROI data from existing NTangible partnerships with organizations like Alliance Fastpitch and Future Stars Series.",
        "playbook_type": "partner_expansion",
        "workflow_slug": "partner-roi-summary",
        "target_output": "partnership_conversation",
        "persona": "Club Director or Event Organizer",
        "offer": "See what a partnership looks like. Real outcomes from organizations like yours.",
        "cta": "Request the partner outcomes one-pager",
        "default_audience": "Club directors, showcase organizers, league administrators considering Clutch Factor integration",
        "default_proof_points": [
            "30,000+ athletes assessed through Alliance Fastpitch",
            "28% reduction in early transfer departures for partner programs",
            "47 college commitments with Clutch Factor data attached in year one",
        ],
    },
    {
        "slug": "athlete-assessment-signup",
        "name": "Athlete Assessment Sign-up via Spotlights",
        "description": "Drive athlete assessment sign-ups through commitment spotlight posts that show the value of having a Clutch Factor score on your recruiting profile.",
        "playbook_type": "athlete_acquisition",
        "workflow_slug": "athlete-commitment-spotlight",
        "target_output": "assessment_signup",
        "persona": "High School Athlete or Club Softball Parent",
        "offer": "Get your Clutch Factor score at your next showcase. Coaches are looking at it.",
        "cta": "Find upcoming assessment events at your next showcase",
        "default_audience": "High school athletes, club athletes, parents researching recruiting advantages",
        "default_proof_points": [
            "College coaches say the mental performance profile is the first thing they open",
            "Athletes with Clutch Factor data receive first contact 3.2x faster",
            "6,000+ assessments across 7 sports",
        ],
    },
    {
        "slug": "portal-evaluation-tool",
        "name": "Portal Evaluation Tool Adoption",
        "description": "Drive adoption of NTangible as the evaluation tool for transfer portal decisions through hot take content that highlights the cost of guessing.",
        "playbook_type": "product_adoption",
        "workflow_slug": "transfer-portal-hot-take",
        "target_output": "product_trial",
        "persona": "D1 Recruiting Coordinator or NIL Collective Analyst",
        "offer": "Clutch Factor data on portal entrants -- free for programs that ask.",
        "cta": "Access portal athlete Clutch Factor profiles",
        "default_audience": "D1/D2 recruiting coordinators, NIL collectives, coaching staffs active in the portal",
        "default_proof_points": [
            "The average failed D1 transfer costs $150K",
            "Programs using Clutch Factor retain 34% more transfers past year one",
            "Portal athletes with published CF data get contacted 3x faster",
        ],
    },
    {
        "slug": "newsletter-nurture-pipeline",
        "name": "Newsletter Nurture to Demo Pipeline",
        "description": "Nurture newsletter subscribers toward demo requests and partner conversations through consistent, high-value weekly content.",
        "playbook_type": "nurture_pipeline",
        "workflow_slug": "weekly-newsletter-digest",
        "target_output": "demo_request",
        "persona": "Coach or Partner Decision-Maker on the Fence",
        "offer": "Weekly insider briefing on mental performance in sports. No fluff, just data and insight.",
        "cta": "Reply to this email or book a 15-minute walkthrough",
        "default_audience": "Newsletter subscribers -- mix of coaches, front offices, and partner decision-makers",
        "default_proof_points": [
            "6,000+ assessments. 1M+ data points. 7 sports.",
            "Used by verified programs including Michigan State, Hofstra, Boston College",
            "Alliance Fastpitch and Future Stars Series run on Clutch Factor",
        ],
    },
]


def ensure_revenue_playbooks(db):
    """Create or update revenue playbooks, linking to workflow IDs."""
    print("\n=== Ensuring revenue playbooks ===")

    # Build slug -> workflow_id lookup
    workflows = {w.slug: w for w in db.query(Workflow).all()}

    created = 0
    updated = 0
    for spec in REVENUE_PLAYBOOKS:
        wf_slug = spec.pop("workflow_slug", None)
        workflow_id = workflows[wf_slug].id if wf_slug and wf_slug in workflows else None

        existing = db.query(RevenuePlaybook).filter(
            RevenuePlaybook.slug == spec["slug"]
        ).first()

        if existing:
            for key, val in spec.items():
                setattr(existing, key, val)
            existing.workflow_id = workflow_id
            updated += 1
        else:
            obj = RevenuePlaybook(
                id=uuid.uuid4(),
                workflow_id=workflow_id,
                **spec,
            )
            db.add(obj)
            created += 1

    db.flush()
    print(f"  Created {created} revenue playbooks, updated {updated}")


# ──────────────────────────────────────────────────────────────────────
# E) Print summary
# ──────────────────────────────────────────────────────────────────────

def print_summary(db):
    """Print a summary of what is in the database after cleanup."""
    print("\n" + "=" * 60)
    print("DATABASE SUMMARY AFTER PRODUCTION SETUP")
    print("=" * 60)

    wf_count = db.query(Workflow).count()
    wv_count = db.query(WorkflowVersion).count()
    cr_count = db.query(CalendarRule).count()
    te_count = db.query(TriggerEvent).count()
    cj_count = db.query(ContentJob).count()
    dv_count = db.query(DraftVariant).count()
    ra_count = db.query(ReviewAction).count()
    mi_count = db.query(MemoryItem).count()
    sc_count = db.query(SportsCalendarWindow).count()
    rp_count = db.query(RevenuePlaybook).count()

    from app.models.trigger import PartnerSource
    ps_count = db.query(PartnerSource).count()

    print(f"\n  Workflows:              {wf_count}")
    print(f"  Workflow Versions:      {wv_count}")
    print(f"  Calendar Rules:         {cr_count}")
    print(f"  Partner Sources:        {ps_count}")
    print(f"  Trigger Events:         {te_count}  (should be 0 -- cleaned)")
    print(f"  Content Jobs:           {cj_count}  (should be 0 -- cleaned)")
    print(f"  Draft Variants:         {dv_count}  (should be 0 -- cleaned)")
    print(f"  Review Actions:         {ra_count}  (should be 0 -- cleaned)")
    print(f"  Memory Items:           {mi_count}  (content brain items preserved)")
    print(f"  Sports Calendar:        {sc_count}")
    print(f"  Revenue Playbooks:      {rp_count}")

    # List workflows with their configs
    print("\n  Workflows:")
    for wf in db.query(Workflow).order_by(Workflow.slug).all():
        mode_str = wf.mode.value if wf.mode else "?"
        plat_str = wf.platform.value if wf.platform else "?"
        ver_str = "no active version"
        if wf.active_version_id:
            v = db.query(WorkflowVersion).filter(WorkflowVersion.id == wf.active_version_id).first()
            if v:
                ver_str = f"v{v.version_number}"
        enabled_str = "enabled" if wf.enabled else "DISABLED"
        print(f"    [{plat_str:10}] {wf.slug:40} {mode_str:10} {ver_str:5} {enabled_str}")

    # List sports calendar
    print("\n  Sports Calendar Windows:")
    for sc in db.query(SportsCalendarWindow).order_by(SportsCalendarWindow.start_date).all():
        active_str = "active" if sc.active else "inactive"
        print(f"    {sc.start_date} - {sc.end_date}  {sc.title:55} [{sc.sport}] {active_str}")

    # List revenue playbooks
    print("\n  Revenue Playbooks:")
    for rp in db.query(RevenuePlaybook).order_by(RevenuePlaybook.slug).all():
        active_str = "active" if rp.active else "inactive"
        print(f"    {rp.slug:45} {rp.playbook_type:20} {active_str}")

    print("\n" + "=" * 60)
    print("Production setup complete.")
    print("=" * 60)


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main():
    db = SessionLocal()
    try:
        # A) Clean seed data
        clean_seed_data(db)

        # B) Verify and update workflow configs
        verify_and_update_workflow_configs(db)

        # C) Load sports calendar
        load_sports_calendar(db)

        # D) Revenue playbooks
        ensure_revenue_playbooks(db)

        # Commit everything
        db.commit()

        # E) Print summary
        print_summary(db)

    except Exception as e:
        db.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
