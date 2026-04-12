"""
Seed the NTangible Marketing database with realistic demo data.

Usage:
    uv run python scripts/seed_demo.py
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.analytics import AnalyticsSnapshot, PublicationRecord
from app.models.campaign import Campaign, CampaignStatus
from app.models.competitor import CompetitorObservation, CompetitorSignal, CompetitorSource
from app.models.lead import LeadAccount, LeadContact
from app.models.memory import MemoryBucket, MemoryItem, MemorySourceKind
from app.models.review import ContentJob, DraftVariant, ReviewAction, ReviewActionType
from app.models.trigger import (
    CalendarRule,
    PartnerSource,
    PartnerSourceType,
    TriggerEvent,
    TriggerProcessingStatus,
    TriggerType,
)
from app.models.workflow import DraftState, Platform, Workflow, WorkflowMode, WorkflowVersion
from app.schemas.workflow_config import WorkflowVersionConfig

NOW = datetime.now(timezone.utc)


def ago(**kw):
    return NOW - timedelta(**kw)


def future(**kw):
    return NOW + timedelta(**kw)


def clear_all(db):
    """Delete all rows from seeded tables in dependency order."""
    for model in [
        AnalyticsSnapshot,
        PublicationRecord,
        ReviewAction,
        MemoryItem,
        DraftVariant,
        ContentJob,
        TriggerEvent,
        CalendarRule,
        CompetitorSignal,
        CompetitorObservation,
        CompetitorSource,
        LeadContact,
        LeadAccount,
        Campaign,
    ]:
        n = db.query(model).delete()
        if n:
            print(f"  deleted {n} {model.__tablename__}")
    # Clear FK refs before deleting versions/workflows
    db.query(Workflow).update({Workflow.active_version_id: None})
    db.flush()
    for model in [WorkflowVersion, Workflow, PartnerSource]:
        n = db.query(model).delete()
        if n:
            print(f"  deleted {n} {model.__tablename__}")
    db.flush()


def seed():
    db = SessionLocal()
    try:
        print("Clearing existing data...")
        clear_all(db)

        config = WorkflowVersionConfig().model_dump()

        # ==================================================================
        # Partner sources
        # ==================================================================
        ps_alliance = PartnerSource(
            id=uuid.uuid4(),
            slug="alliance-fastpitch",
            display_name="Alliance Fastpitch",
            source_type=PartnerSourceType.WEBHOOK,
            config={"sport": "softball", "events": ["leaderboard_update", "commitment"]},
        )
        ps_fss = PartnerSource(
            id=uuid.uuid4(),
            slug="future-stars-series",
            display_name="Future Stars Series",
            source_type=PartnerSourceType.WEBHOOK,
            config={"sport": "softball", "events": ["leaderboard_update", "showcase_result"]},
        )
        db.add_all([ps_alliance, ps_fss])
        db.flush()
        print("Created 2 partner sources")

        # ==================================================================
        # Workflows (6)
        # ==================================================================
        workflow_specs = [
            ("Tuesday Thought Leadership", "tuesday-thought-leadership", Platform.LINKEDIN, WorkflowMode.MANUAL, "thought_leadership"),
            ("FSS Leaderboard Data Drop", "fss-leaderboard-data-drop", Platform.X, WorkflowMode.AUTOMATIC, "data_drop"),
            ("Athlete Commitment Spotlight", "athlete-commitment-spotlight", Platform.INSTAGRAM, WorkflowMode.MANUAL, "partner_spotlight"),
            ("Weekly Newsletter Digest", "weekly-newsletter-digest", Platform.NEWSLETTER, WorkflowMode.MANUAL, "newsletter"),
            ("Transfer Portal Hot Take", "transfer-portal-hot-take", Platform.X, WorkflowMode.MANUAL, "hot_take"),
            ("Partner ROI Summary", "partner-roi-summary", Platform.LINKEDIN, WorkflowMode.AUTOMATIC, "partner_report"),
        ]

        workflows = {}
        versions = {}
        for name, slug, platform, mode, ct in workflow_specs:
            wf = Workflow(
                id=uuid.uuid4(),
                name=name,
                slug=slug,
                description=f"Auto-seeded: {name}",
                mode=mode,
                platform=platform,
                content_type=ct,
                enabled=True,
                health_status="healthy",
                last_run_at=ago(hours=3),
                last_success_at=ago(hours=3),
            )
            db.add(wf)
            db.flush()

            v1 = WorkflowVersion(
                id=uuid.uuid4(),
                workflow_id=wf.id,
                version_number=1,
                config=config,
                version_note="Initial version",
                author="elliot",
                is_active=True,
            )
            db.add(v1)
            db.flush()
            wf.active_version_id = v1.id
            workflows[slug] = wf
            versions[slug] = [v1]

        # Add v2 to a couple workflows
        for slug in ["tuesday-thought-leadership", "fss-leaderboard-data-drop"]:
            wf = workflows[slug]
            v2 = WorkflowVersion(
                id=uuid.uuid4(),
                workflow_id=wf.id,
                version_number=2,
                config=config,
                version_note="Tuned prompt tone and hashtag strategy",
                author="elliot",
                is_active=True,
            )
            db.add(v2)
            db.flush()
            wf.active_version_id = v2.id
            versions[slug].append(v2)

        print(f"Created {len(workflows)} workflows with versions")

        # ==================================================================
        # Calendar rules (3)
        # ==================================================================
        cal_objs = {}

        cr1 = CalendarRule(
            id=uuid.uuid4(),
            workflow_id=workflows["tuesday-thought-leadership"].id,
            cron_expression="0 7 * * 2",
            timezone="America/New_York",
            publish_hour_local=7,
            publish_minute_local=0,
            next_fire_at=future(days=2),
            last_fired_at=ago(days=5),
        )
        cal_objs["tuesday-thought-leadership"] = cr1

        cr2 = CalendarRule(
            id=uuid.uuid4(),
            workflow_id=workflows["fss-leaderboard-data-drop"].id,
            cron_expression="0 12 * * 5",
            timezone="America/New_York",
            publish_hour_local=12,
            publish_minute_local=0,
            next_fire_at=future(days=3),
            last_fired_at=ago(days=4),
        )
        cal_objs["fss-leaderboard-data-drop"] = cr2

        cr3 = CalendarRule(
            id=uuid.uuid4(),
            workflow_id=workflows["weekly-newsletter-digest"].id,
            cron_expression="0 9 * * 1",
            timezone="America/New_York",
            publish_hour_local=9,
            publish_minute_local=0,
            next_fire_at=future(days=1),
            last_fired_at=ago(days=6),
        )
        cal_objs["weekly-newsletter-digest"] = cr3

        db.add_all([cr1, cr2, cr3])
        db.flush()
        print(f"Created {len(cal_objs)} calendar rules")

        # ==================================================================
        # Helper: create trigger -> job -> draft (+ optional review action)
        # ==================================================================
        all_drafts = []
        all_jobs = []
        all_triggers = []
        published_tuples = []  # (trigger, job, draft) for published drafts

        def make_draft(
            wf_slug,
            content,
            state,
            hashtags,
            *,
            trigger_type=TriggerType.CALENDAR,
            partner_source=None,
            partner_slug=None,
            partner_name=None,
            days_ago=0,
            hours_ago=0,
            scheduled_in_hours=None,
            published_at_delta=None,
            failure_reason=None,
            rejection_note=None,
            intent="brand",
        ):
            wf = workflows[wf_slug]
            ver = versions[wf_slug][-1]
            created = ago(days=days_ago, hours=hours_ago)

            trigger = TriggerEvent(
                id=uuid.uuid4(),
                trigger_type=trigger_type,
                workflow_id=wf.id,
                calendar_rule_id=cal_objs[wf_slug].id if trigger_type == TriggerType.CALENDAR and wf_slug in cal_objs else None,
                partner_source_id=partner_source.id if partner_source else None,
                external_event_type="partner_webhook" if partner_source else None,
                processing_status=TriggerProcessingStatus.PROCESSED,
                source_payload={"seeded": True},
                created_at=created,
            )
            db.add(trigger)
            db.flush()
            all_triggers.append(trigger)

            job = ContentJob(
                id=uuid.uuid4(),
                workflow_id=wf.id,
                workflow_version_id=ver.id,
                trigger_event_id=trigger.id,
                status="completed",
                created_at=created,
            )
            db.add(job)
            db.flush()
            all_jobs.append(job)

            pub_at = ago(**published_at_delta) if published_at_delta else None
            draft = DraftVariant(
                id=uuid.uuid4(),
                content_job_id=job.id,
                platform=wf.platform,
                intent=intent,
                partner_slug=partner_slug,
                partner_name=partner_name,
                content=content,
                hashtags=hashtags,
                state=state,
                timezone="America/New_York",
                recommended_publish_at=created + timedelta(hours=2),
                scheduled_publish_at=future(hours=scheduled_in_hours) if scheduled_in_hours else None,
                expires_at=future(hours=48) if state in (DraftState.MANUAL_READY, DraftState.AUTOMATIC_READY) else None,
                published_at=pub_at,
                published_via="api" if pub_at else None,
                platform_post_id=f"post_{uuid.uuid4().hex[:12]}" if pub_at else None,
                post_url=f"https://x.com/ntangible/status/{uuid.uuid4().hex[:18]}" if pub_at and wf.platform == Platform.X else None,
                compliance_result={"passed": True, "checks_run": ["trademarks", "claims", "tone"]},
                failure_reason=failure_reason,
                created_at=created,
            )
            db.add(draft)
            db.flush()
            all_drafts.append(draft)

            # Auto-create review actions based on state
            if state == DraftState.PUBLISHED and pub_at:
                ra = ReviewAction(
                    id=uuid.uuid4(),
                    draft_variant_id=draft.id,
                    action=ReviewActionType.POST_NOW,
                    actor="elliot",
                    created_at=pub_at - timedelta(minutes=5),
                )
                db.add(ra)
                published_tuples.append((trigger, job, draft))
            elif state == DraftState.REJECTED and rejection_note:
                ra = ReviewAction(
                    id=uuid.uuid4(),
                    draft_variant_id=draft.id,
                    action=ReviewActionType.REJECT,
                    actor="elliot",
                    notes=rejection_note,
                    created_at=created + timedelta(hours=1),
                )
                db.add(ra)
            elif state == DraftState.EXPIRED:
                ra = ReviewAction(
                    id=uuid.uuid4(),
                    draft_variant_id=draft.id,
                    action=ReviewActionType.EXPIRE,
                    actor="system",
                    notes="Expired: publish window passed without action.",
                    created_at=created + timedelta(days=2),
                )
                db.add(ra)

            return trigger, job, draft

        # ==================================================================
        # MANUAL_READY drafts (Needs Review) - 3
        # ==================================================================
        make_draft(
            "tuesday-thought-leadership",
            "Every coaching staff says they value mental toughness. But how many actually measure it? Clutch Factor gives programs a language for pressure — backed by data, not guesswork. The programs that quantify mental performance today will own the recruiting conversations of tomorrow.",
            DraftState.MANUAL_READY,
            ["#MentalPerformance", "#ClutchFactor", "#Recruiting"],
            hours_ago=2,
        )
        make_draft(
            "weekly-newsletter-digest",
            "This week in NTangible: new Clutch Factor benchmarks for 2026 showcase season, a deep dive into how three SEC programs use mental performance data in their recruiting workflows, and a partner spotlight on Alliance Fastpitch leaderboard integrations. Plus: the launch date for our portal commitment tracker.",
            DraftState.MANUAL_READY,
            ["#NTangible", "#Newsletter"],
            hours_ago=1,
        )
        make_draft(
            "transfer-portal-hot-take",
            "Portal update: 14 new entries this week with Clutch Factor profiles attached. Programs with NTangible data are making offers 3x faster because they already know the mental performance baseline. The portal is a race — data is the starting gun.",
            DraftState.MANUAL_READY,
            ["#TransferPortal", "#ClutchFactor", "#CollegeSoftball"],
            trigger_type=TriggerType.EXTERNAL,
            hours_ago=3,
        )

        # ==================================================================
        # AUTOMATIC_READY drafts (Scheduled & Automatic) - 3
        # ==================================================================
        make_draft(
            "fss-leaderboard-data-drop",
            "Future Stars Series leaderboard update: 247 athletes assessed across 12 showcases this month. Top Clutch Factor scores came from the Southeast regional — three pitchers posting 90th-percentile composure under live at-bat pressure. Full rankings drop Friday.",
            DraftState.AUTOMATIC_READY,
            ["#FSS", "#ClutchFactor", "#Softball", "#Showcase"],
            trigger_type=TriggerType.EXTERNAL,
            partner_source=ps_fss,
            partner_slug="future-stars-series",
            partner_name="Future Stars Series",
            scheduled_in_hours=4,
            hours_ago=1,
        )
        make_draft(
            "fss-leaderboard-data-drop",
            "Mid-week data drop: Future Stars Series added 62 new Clutch Factor profiles from the Midwest regional. Standout stat — catchers at this event posted the highest average composure scores we have seen all season. Pitchers, take note.",
            DraftState.AUTOMATIC_READY,
            ["#FSS", "#DataDrop", "#Softball"],
            trigger_type=TriggerType.EXTERNAL,
            partner_source=ps_fss,
            partner_slug="future-stars-series",
            partner_name="Future Stars Series",
            scheduled_in_hours=8,
            hours_ago=2,
        )
        make_draft(
            "partner-roi-summary",
            "Q1 partner ROI snapshot: Alliance Fastpitch programs using Clutch Factor saw a 28% reduction in early transfer departures and a 41% increase in recruiting conversion rates compared to non-NTangible programs. Data-driven culture building is not a nice-to-have — it is a competitive edge.",
            DraftState.AUTOMATIC_READY,
            ["#PartnerROI", "#AllianceFastpitch", "#ClutchFactor"],
            trigger_type=TriggerType.CALENDAR,
            scheduled_in_hours=20,
        )

        # ==================================================================
        # PUBLISHED drafts (History) - 5
        # ==================================================================
        pub_specs = [
            ("fss-leaderboard-data-drop",
             "Showcase season is here and the Clutch Factor leaderboard is live. 189 athletes across 8 Future Stars Series events now have mental performance profiles visible to college coaches. The game just changed for data-driven recruiting.",
             ["#FSS", "#ClutchFactor", "#Recruiting"], 5, TriggerType.EXTERNAL, ps_fss, "future-stars-series", "Future Stars Series"),
            ("tuesday-thought-leadership",
             "Mental toughness is not a cliche — it is measurable. Programs that treat it like a skill, not a trait, are separating themselves in recruiting. Clutch Factor gives coaches the same precision for mental performance that launch angle gave hitting coaches a decade ago.",
             ["#MentalPerformance", "#ClutchFactor", "#Softball"], 4, TriggerType.CALENDAR, None, None, None),
            ("transfer-portal-hot-take",
             "Hot take: the transfer portal is not broken. Evaluation is broken. Programs making portal decisions with Clutch Factor data are retaining 34% more transfers past year one. The portal rewards programs that do their homework.",
             ["#TransferPortal", "#ClutchFactor"], 3, TriggerType.EXTERNAL, None, None, None),
            ("athlete-commitment-spotlight",
             "Commitment spotlight: Congrats to Alliance Fastpitch 2026 pitcher Mia Torres on her commitment to Oklahoma State. Mia posted a 94th-percentile Clutch Factor score at the Texas showcase — composure, adaptability, and competitive drive off the charts.",
             ["#Committed", "#AllianceFastpitch", "#OKState", "#ClutchFactor"], 2, TriggerType.EXTERNAL, ps_alliance, "alliance-fastpitch", "Alliance Fastpitch"),
            ("partner-roi-summary",
             "Alliance Fastpitch year-one results: 12 partner organizations, 340 athletes assessed, 47 college commitments with Clutch Factor data attached. Coaches are telling us the mental performance profile is now the first thing they open. That is the ROI.",
             ["#PartnerROI", "#AllianceFastpitch", "#Results"], 1, TriggerType.CALENDAR, None, None, None),
        ]

        for slug, content, tags, days, tt, ps, p_slug, p_name in pub_specs:
            make_draft(
                slug, content, DraftState.PUBLISHED, tags,
                trigger_type=tt,
                partner_source=ps,
                partner_slug=p_slug,
                partner_name=p_name,
                days_ago=days,
                published_at_delta={"days": days, "hours": -1},
            )

        # ==================================================================
        # REJECTED drafts - 2
        # ==================================================================
        make_draft(
            "fss-leaderboard-data-drop",
            "FSS leaderboard just dropped and the numbers are INSANE. These kids are absolutely crushing it under pressure. NTangible basically invented mental performance assessment.",
            DraftState.REJECTED,
            ["#FSS", "#GOAT"],
            trigger_type=TriggerType.EXTERNAL,
            partner_source=ps_fss,
            days_ago=6,
            rejection_note="Tone too aggressive — avoid superlatives and unsubstantiated claims. Rewrite with factual framing.",
        )
        make_draft(
            "tuesday-thought-leadership",
            "If your program is not using Clutch Factor you are already behind. Every single coach we talk to says the same thing — they wish they had started sooner. Do not be the last staff to figure this out.",
            DraftState.REJECTED,
            ["#ClutchFactor", "#FOMO"],
            days_ago=5,
            rejection_note="Doesn't match brand voice — too sales-forward for thought leadership. Needs educational tone, not pressure tactics.",
        )

        # ==================================================================
        # EXPIRED drafts - 2
        # ==================================================================
        make_draft(
            "transfer-portal-hot-take",
            "Breaking: 6 new portal entries today with NTangible profiles. The Tuesday wave is real — coaches are moving fast on athletes with verified Clutch Factor data.",
            DraftState.EXPIRED,
            ["#TransferPortal", "#Breaking"],
            trigger_type=TriggerType.EXTERNAL,
            days_ago=7,
        )
        make_draft(
            "athlete-commitment-spotlight",
            "Commitment alert: Congrats to FSS 2027 outfielder Jada Williams on her commitment to Florida. Jada's 91st-percentile Clutch Factor score turned heads at the Southeast showcase.",
            DraftState.EXPIRED,
            ["#Committed", "#FSS", "#GoGators"],
            trigger_type=TriggerType.EXTERNAL,
            partner_source=ps_fss,
            days_ago=6,
        )

        db.flush()

        # ==================================================================
        # Publication records + analytics snapshots for published drafts
        # ==================================================================
        pub_records = []
        for trigger, job, draft in published_tuples:
            pr = PublicationRecord(
                id=uuid.uuid4(),
                draft_variant_id=draft.id,
                content_job_id=job.id,
                workflow_id=job.workflow_id,
                workflow_version_id=job.workflow_version_id,
                trigger_event_id=trigger.id,
                platform=draft.platform,
                platform_post_id=draft.platform_post_id,
                post_url=draft.post_url,
                published_at=draft.published_at,
                publish_result={"status": "success"},
            )
            db.add(pr)
            pub_records.append(pr)
        db.flush()

        for pr in pub_records:
            snap = AnalyticsSnapshot(
                id=uuid.uuid4(),
                publication_record_id=pr.id,
                metrics={
                    "impressions": 800 + (uuid.uuid4().int % 4200),
                    "engagements": 40 + (uuid.uuid4().int % 260),
                    "clicks": 10 + (uuid.uuid4().int % 90),
                    "shares": 2 + (uuid.uuid4().int % 30),
                },
                captured_at=pr.published_at + timedelta(hours=24),
            )
            db.add(snap)
        db.flush()
        print(f"Created {len(pub_records)} publication records with analytics snapshots")

        # ==================================================================
        # Memory items (10+)
        # ==================================================================
        memory_items = []

        # Approved memories (from published drafts)
        for i, (trigger, job, draft) in enumerate(published_tuples):
            mi = MemoryItem(
                id=uuid.uuid4(),
                source_kind=MemorySourceKind.DRAFT_VARIANT,
                source_id=str(draft.id),
                bucket=MemoryBucket.APPROVED,
                platform=draft.platform,
                workflow_id=job.workflow_id,
                workflow_slug=[s for s, w in workflows.items() if w.id == job.workflow_id][0],
                draft_variant_id=draft.id,
                trigger_event_id=trigger.id,
                title=f"Published: {draft.content[:60]}...",
                content=draft.content,
                search_text=f"{draft.content} {' '.join(draft.hashtags)}",
                details={"state": "published", "hashtags": draft.hashtags},
                recorded_at=draft.published_at,
            )
            db.add(mi)
            memory_items.append(mi)

        # Rejected memories
        rejected_drafts = [d for d in all_drafts if d.state == DraftState.REJECTED]
        for draft in rejected_drafts:
            job = next(j for j in all_jobs if j.id == draft.content_job_id)
            mi = MemoryItem(
                id=uuid.uuid4(),
                source_kind=MemorySourceKind.DRAFT_VARIANT,
                source_id=str(draft.id),
                bucket=MemoryBucket.REJECTED,
                platform=draft.platform,
                workflow_id=job.workflow_id,
                workflow_slug=[s for s, w in workflows.items() if w.id == job.workflow_id][0],
                draft_variant_id=draft.id,
                title=f"Rejected: {draft.content[:60]}...",
                content=draft.content,
                search_text=f"{draft.content} {' '.join(draft.hashtags)}",
                details={"state": "rejected", "hashtags": draft.hashtags},
                recorded_at=draft.created_at + timedelta(hours=1),
            )
            db.add(mi)
            memory_items.append(mi)

        # Expired memories
        expired_drafts = [d for d in all_drafts if d.state == DraftState.EXPIRED]
        for draft in expired_drafts:
            job = next(j for j in all_jobs if j.id == draft.content_job_id)
            mi = MemoryItem(
                id=uuid.uuid4(),
                source_kind=MemorySourceKind.DRAFT_VARIANT,
                source_id=str(draft.id),
                bucket=MemoryBucket.EXPIRED,
                platform=draft.platform,
                workflow_id=job.workflow_id,
                workflow_slug=[s for s, w in workflows.items() if w.id == job.workflow_id][0],
                draft_variant_id=draft.id,
                title=f"Expired: {draft.content[:60]}...",
                content=draft.content,
                search_text=f"{draft.content} {' '.join(draft.hashtags)}",
                details={"state": "expired", "hashtags": draft.hashtags},
                recorded_at=draft.created_at + timedelta(days=2),
            )
            db.add(mi)
            memory_items.append(mi)

        # Source memories (content brain / trigger event based)
        source_memories = [
            ("Clutch Factor science overview", "Clutch Factor is a proprietary mental performance assessment measuring composure, adaptability, and competitive drive under pressure. Validated across 4,000+ collegiate and club athletes.", "content_brain"),
            ("Coach Alignment Index explainer", "The Coach Alignment Index quantifies how well an athlete's mental performance profile matches a program's coaching style and culture expectations. Higher alignment correlates with longer retention.", "content_brain"),
            ("Transfer portal timing data", "Analysis of 2025 portal entries shows athletes with published Clutch Factor data receive first contact from programs 3.2x faster than those without mental performance profiles.", "trigger_event"),
        ]
        for title, content, kind_str in source_memories:
            kind = MemorySourceKind.CONTENT_BRAIN if kind_str == "content_brain" else MemorySourceKind.TRIGGER_EVENT
            mi = MemoryItem(
                id=uuid.uuid4(),
                source_kind=kind,
                source_id=str(uuid.uuid4()),
                bucket=MemoryBucket.SOURCE,
                platform=None,
                title=title,
                content=content,
                search_text=f"{title} {content}",
                details={"origin": kind_str},
                recorded_at=ago(days=5),
            )
            db.add(mi)
            memory_items.append(mi)

        db.flush()
        print(f"Created {len(memory_items)} memory items")

        # ==================================================================
        # Campaigns (2)
        # ==================================================================
        campaigns = [
            Campaign(
                id=uuid.uuid4(),
                name="Transfer Portal Week",
                slug="transfer-portal-week",
                objective="Dominate transfer portal conversation with Clutch Factor data angles during peak spring portal window.",
                audience="D1/D2 coaching staffs, recruiting coordinators, NIL collectives",
                theme="Data-driven portal evaluation with mental performance profiles",
                status=CampaignStatus.ACTIVE,
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 14),
            ),
            Campaign(
                id=uuid.uuid4(),
                name="Assessment Season Push",
                slug="assessment-season-push",
                objective="Drive showcase and club organization sign-ups for Clutch Factor assessments during peak evaluation season.",
                audience="Club directors, showcase organizers, high school athletes and parents",
                theme="Showcase season is assessment season — get your Clutch Factor score",
                status=CampaignStatus.ACTIVE,
                start_date=date(2026, 3, 15),
                end_date=date(2026, 6, 30),
            ),
        ]
        db.add_all(campaigns)
        db.flush()
        print(f"Created {len(campaigns)} campaigns")

        # ==================================================================
        # Competitor sources + observations + signals
        # ==================================================================
        cs1 = CompetitorSource(
            id=uuid.uuid4(), slug="scorability", display_name="Scorability",
            source_url="https://www.scorability.com", platform="web",
        )
        cs2 = CompetitorSource(
            id=uuid.uuid4(), slug="the-playbook", display_name="The Playbook",
            source_url="https://www.theplaybook.com", platform="web",
        )
        cs3 = CompetitorSource(
            id=uuid.uuid4(), slug="s2-cognition", display_name="S2 Cognition",
            source_url="https://www.s2cognition.com", platform="x",
        )
        db.add_all([cs1, cs2, cs3])
        db.flush()

        obs1 = CompetitorObservation(
            id=uuid.uuid4(), source_id=cs1.id,
            headline="Scorability announces Series B funding round",
            summary="Scorability closed a Series B to expand their recruiting analytics platform into mental performance metrics. Direct overlap with Clutch Factor positioning.",
            url="https://scorability.com/series-b",
            observed_at=ago(days=4), raw_payload={},
        )
        obs2 = CompetitorObservation(
            id=uuid.uuid4(), source_id=cs3.id,
            headline="S2 Cognition partners with three Power 5 football programs",
            summary="S2 expanding cognitive testing into football recruiting. Different sport but similar 'science-backed assessment' positioning.",
            url="https://s2cognition.com/power5",
            observed_at=ago(days=2), raw_payload={},
        )
        db.add_all([obs1, obs2])
        db.flush()

        signals = [
            CompetitorSignal(
                id=uuid.uuid4(), source_id=cs1.id, observation_id=obs1.id,
                signal_type="funding",
                summary="Scorability announced Series B — expanding into mental performance metrics that overlap directly with Clutch Factor's core positioning.",
                severity="high",
                reaction_angle="Emphasize science credibility and validated methodology. Scorability is analytics-first, NTangible is science-first.",
                status="open", raw_payload={},
            ),
            CompetitorSignal(
                id=uuid.uuid4(), source_id=cs2.id,
                signal_type="content",
                summary="The Playbook publishing thought leadership on 'data-driven recruiting' — similar language to NTangible marketing.",
                severity="low",
                reaction_angle="Own the mental performance category specifically. The Playbook is broad recruiting content, NTangible is specialized.",
                status="acknowledged", raw_payload={},
            ),
            CompetitorSignal(
                id=uuid.uuid4(), source_id=cs3.id, observation_id=obs2.id,
                signal_type="partnership",
                summary="S2 Cognition expanding into Power 5 football with cognitive testing. Adjacent market but validates the 'science-backed assessment' category NTangible owns in softball.",
                severity="medium",
                reaction_angle="Use S2's football traction as social proof that cognitive/mental assessment is mainstream. Then differentiate on sport-specific methodology.",
                status="open", raw_payload={},
            ),
        ]
        db.add_all(signals)
        db.flush()
        print(f"Created 3 competitor sources, 2 observations, {len(signals)} signals")

        # ==================================================================
        # Lead accounts + contacts
        # ==================================================================
        leads = [
            LeadAccount(
                id=uuid.uuid4(), name="Michigan State Softball",
                stage="qualified", source="conference_event", priority="high", owner="elliot",
                metadata_json={"conference": "Big Ten", "division": "D1", "sport": "softball"},
                last_contacted_at=ago(days=2), next_due_at=future(days=3),
            ),
            LeadAccount(
                id=uuid.uuid4(), name="Hofstra Softball",
                stage="demo_scheduled", source="inbound", priority="normal", owner="elliot",
                metadata_json={"conference": "CAA", "division": "D1", "sport": "softball"},
                last_contacted_at=ago(days=4), next_due_at=future(days=1),
            ),
            LeadAccount(
                id=uuid.uuid4(), name="Boston College Softball",
                stage="new", source="partner_referral", priority="high", owner="elliot",
                metadata_json={"conference": "ACC", "division": "D1", "sport": "softball"},
                next_due_at=future(days=5),
            ),
        ]
        db.add_all(leads)
        db.flush()

        contacts = [
            LeadContact(id=uuid.uuid4(), lead_account_id=leads[0].id, name="Demo Head Coach", email="head-coach@example.edu", role="Head Coach"),
            LeadContact(id=uuid.uuid4(), lead_account_id=leads[0].id, name="Demo Recruiting Coordinator", email="recruiting@example.edu", role="Recruiting Coordinator"),
            LeadContact(id=uuid.uuid4(), lead_account_id=leads[1].id, name="Demo Head Coach 2", email="head-coach-2@example.edu", role="Head Coach"),
            LeadContact(id=uuid.uuid4(), lead_account_id=leads[2].id, name="Demo Head Coach 3", email="head-coach-3@example.edu", role="Head Coach"),
        ]
        db.add_all(contacts)
        db.flush()
        print(f"Created {len(leads)} lead accounts, {len(contacts)} contacts")

        # ==================================================================
        # Commit and summarize
        # ==================================================================
        db.commit()

        print("\n--- Seed complete ---")
        print(f"  {len(workflows)} workflows")
        print(f"  {sum(len(v) for v in versions.values())} workflow versions")
        print(f"  {len(cal_objs)} calendar rules")
        print(f"  2 partner sources")
        print(f"  {len(all_triggers)} trigger events")
        print(f"  {len(all_jobs)} content jobs")
        print(f"  {len(all_drafts)} draft variants")
        mr = sum(1 for d in all_drafts if d.state == DraftState.MANUAL_READY)
        ar = sum(1 for d in all_drafts if d.state == DraftState.AUTOMATIC_READY)
        pub = sum(1 for d in all_drafts if d.state == DraftState.PUBLISHED)
        rej = sum(1 for d in all_drafts if d.state == DraftState.REJECTED)
        exp = sum(1 for d in all_drafts if d.state == DraftState.EXPIRED)
        print(f"    manual_ready={mr}  automatic_ready={ar}  published={pub}  rejected={rej}  expired={exp}")
        print(f"  {len(pub_records)} publication records + analytics snapshots")
        print(f"  {len(memory_items)} memory items")
        print(f"  {len(campaigns)} campaigns")
        print(f"  3 competitor sources, {len(signals)} signals")
        print(f"  {len(leads)} lead accounts, {len(contacts)} contacts")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
