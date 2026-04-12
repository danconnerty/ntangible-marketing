"""Seed the brain knowledge graph with NTangible's full knowledge base.

Sources:
  - app/config_data/brand_voice.yaml
  - app/config_data/content_pillars.yaml
  - app/config_data/approved_claims.yaml
  - app/config_data/canva_templates.yaml
  - app/config_data/platforms/*.yaml
  - app/config_data/content_brain/public_sources.yaml
  - agent-engine brain architecture
"""

import uuid
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.brain import EntityEdge, EntityNode, KnowledgeEdge, KnowledgeNode

TOPIC = "marketing"
NOW = datetime.now(timezone.utc)


def _entity(entity_type, name, slug, description=None, metadata=None):
    return EntityNode(
        id=uuid.uuid4(),
        entity_type=entity_type,
        canonical_name=name,
        slug=slug,
        description=description,
        status="active",
        primary_topic_key=TOPIC,
        metadata_=metadata or {},
    )


def _knowledge(kind, title, content=None, status="active", confidence=0.8, trust=0.8, metadata=None):
    return KnowledgeNode(
        id=uuid.uuid4(),
        kind=kind,
        title=title,
        content=content,
        status=status,
        primary_topic_key=TOPIC,
        confidence=confidence,
        trust_score=trust,
        metadata_=metadata or {},
    )


def _entity_edge(source, target, relation, source_type="entity", target_type="entity", confidence=None):
    return EntityEdge(
        id=uuid.uuid4(),
        source_id=source.id,
        target_id=target.id,
        source_type=source_type,
        target_type=target_type,
        relation=relation,
        confidence=confidence,
    )


def _knowledge_edge(source, target, relation, confidence=None):
    return KnowledgeEdge(
        id=uuid.uuid4(),
        source_id=source.id,
        target_id=target.id,
        relation=relation,
        confidence=confidence,
    )


def seed():
    db = SessionLocal()
    all_objects = []

    # ── 1. Publishing Channels (EntityNodes) ───────────────────────────
    ch_x = _entity("publishing_channel", "X (Twitter)", "x", "Primary short-form platform", {
        "max_chars": 280, "max_hashtags": 2,
    })
    ch_linkedin = _entity("publishing_channel", "LinkedIn", "linkedin", "B2B thought leadership", {
        "max_chars": 3000, "max_hashtags": 5,
        "content_types": {"thought_leadership": {"min": 1200, "max": 1500}, "data_insight": {"min": 600, "max": 800}},
    })
    ch_instagram = _entity("publishing_channel", "Instagram", "instagram", "Visual-first engagement", {
        "max_caption_chars": 2200, "min_hashtags": 6, "max_hashtags": 10,
        "posting_windows_et": ["Tue-Fri 11:00-13:00", "Tue-Fri 19:00-21:00"],
    })
    ch_newsletter = _entity("publishing_channel", "Newsletter", "newsletter", "Email digest", {
        "subject_max_chars": 90, "preview_max_chars": 140, "max_body_chars": 4000, "max_sections": 4,
        "segments": ["coaches_front_offices", "partners_event_directors"],
    })
    channels = [ch_x, ch_linkedin, ch_instagram, ch_newsletter]
    all_objects.extend(channels)

    # ── 2. Workflows (EntityNodes) ─────────────────────────────────────
    wf_thought = _entity("workflow", "Tuesday Thought Leadership", "tuesday-thought-leadership",
        "Weekly LinkedIn thought piece on mental performance")
    wf_fss = _entity("workflow", "FSS Leaderboard Data Drop", "fss-leaderboard-data-drop",
        "Post-event performance leaderboard for Future Stars Series")
    wf_commit = _entity("workflow", "Athlete Commitment Spotlight", "athlete-commitment-spotlight",
        "Celebrate athlete commitments with Clutch Factor data")
    wf_newsletter = _entity("workflow", "Weekly Newsletter", "weekly-newsletter",
        "Curated weekly digest for coaches and partners")
    wf_transfer = _entity("workflow", "Transfer Portal Hot Take", "transfer-portal-hot-take",
        "Data-driven transfer portal commentary for X")
    wf_partner_roi = _entity("workflow", "Partner ROI Summary", "partner-roi-summary",
        "Monthly ROI recap for partner organizations")
    workflows = [wf_thought, wf_fss, wf_commit, wf_newsletter, wf_transfer, wf_partner_roi]
    all_objects.extend(workflows)

    # ── 3. Partners (EntityNodes) ──────────────────────────────────────
    p_alliance = _entity("partner", "Alliance Fastpitch", "alliance-fastpitch",
        "Softball organization — 30,000+ athletes assessed", {"sport": "softball", "tier": "flagship"})
    p_fss = _entity("partner", "Future Stars Series", "future-stars-series",
        "Showcase event series", {"sport": "baseball", "tier": "flagship"})
    p_hlt = _entity("partner", "High Level Throwing", "high-level-throwing",
        "Elite throwing training program", {"sport": "baseball", "tier": "partner"})
    p_rfk = _entity("partner", "RFK Racing", "rfk-racing",
        "NASCAR team using NTangible for driver performance", {"sport": "motorsports", "tier": "partner"})
    partners = [p_alliance, p_fss, p_hlt, p_rfk]
    all_objects.extend(partners)

    # ── 4. Verified Clients (EntityNodes) ──────────────────────────────
    cl_msu = _entity("client", "Michigan State", "michigan-state",
        "D1 program using NTangible assessments", {"division": "D1", "sport": "multi"})
    cl_hofstra = _entity("client", "Hofstra", "hofstra",
        "D1 program", {"division": "D1"})
    cl_bc = _entity("client", "Boston College", "boston-college",
        "D1 program", {"division": "D1"})
    clients = [cl_msu, cl_hofstra, cl_bc]
    all_objects.extend(clients)

    # ── 5. Competitors (EntityNodes) ───────────────────────────────────
    comp_scorability = _entity("competitor", "Scorability", "scorability",
        "Athletic recruiting technology", {"focus": "recruiting"})
    comp_playbook = _entity("competitor", "The Playbook", "the-playbook",
        "Sports analytics platform", {"focus": "analytics"})
    comp_s2 = _entity("competitor", "S2 Cognition", "s2-cognition",
        "Cognitive assessment for athletes", {"focus": "cognitive"})
    competitors = [comp_scorability, comp_playbook, comp_s2]
    all_objects.extend(competitors)

    # ── 6. Content Pillars (EntityNodes) ───────────────────────────────
    pil_blind = _entity("content_pillar", "Blind Spot", "blind-spot",
        "You're evaluating half the picture")
    pil_cost = _entity("content_pillar", "Cost of Guessing", "cost-of-guessing",
        "The financial cost of not measuring mental performance")
    pil_proof = _entity("content_pillar", "Client Proof", "client-proof",
        "Real programs using NTangible, real results")
    pil_thought = _entity("content_pillar", "Thought Leadership", "thought-leadership",
        "NTangible's position in the mental performance conversation")
    pil_product = _entity("content_pillar", "Product", "product",
        "What NTangible does and how it works")
    pillars = [pil_blind, pil_cost, pil_proof, pil_thought, pil_product]
    all_objects.extend(pillars)

    # ── 7. Brand Voice (KnowledgeNode) ─────────────────────────────────
    kn_voice = _knowledge("reference_content", "Brand Voice Guidelines",
        "Punchy. Contrarian. Sports bar meets data lab.", confidence=1.0, trust=1.0,
        metadata={
            "do": [
                "Sound like a smart person who works in sports, not a brand account",
                "Use short, direct sentences",
                "Lead with data-backed claims",
                "Be opinionated — take a position",
            ],
            "dont": [
                "No passive voice",
                "No exclamation points",
                "No fluffy motivational language",
                "No corporate buzzwords",
                "Never sound like a press release",
            ],
            "banned_phrases": ["unlock insights", "leverage data", "empower your team", "game-changing", "cutting-edge"],
            "trademarks": {"Clutch Factor™": True, "NTangible Score": True, "The Pressure Test": True},
        })
    all_objects.append(kn_voice)

    # ── 8. Approved Claims (KnowledgeNodes) ────────────────────────────
    claim_cf = _knowledge("approved_claim",
        "73% of athletes scoring above 800 CF were named All-American",
        "73% of athletes scoring above 800 Clutch Factor were named All-American",
        confidence=0.95, trust=1.0,
        metadata={"source": "NTangible internal dataset", "verified_date": "2026-03-01", "key": "cf_all_american"})

    claim_transfer = _knowledge("approved_claim",
        "Average failed D1 transfer costs $150K",
        "The average failed D1 transfer costs $150K in wasted scholarships and resources",
        confidence=0.85, trust=0.9,
        metadata={"source": "Industry research", "verified_date": "2026-01-15", "key": "failed_transfer_cost"})

    claim_bust = _knowledge("approved_claim",
        "Average 1st round draft bust: -$3.5M",
        "Average 1st round draft bust costs organizations $3.5M",
        confidence=0.85, trust=0.9,
        metadata={"source": "Industry research", "verified_date": "2026-01-15", "key": "draft_bust_cost"})

    claim_churn = _knowledge("approved_claim",
        "Youth churn: -$50K lifetime value",
        "Youth athlete churn costs organizations $50K in lifetime value per athlete",
        confidence=0.80, trust=0.85,
        metadata={"source": "NTangible internal estimate", "verified_date": "2026-02-01", "key": "youth_churn_cost"})

    claim_assess = _knowledge("approved_claim",
        "6,000+ assessments. 1M+ data points. 7 sports.",
        "NTangible has conducted over 6,000 assessments generating more than 1 million data points across 7 sports",
        confidence=0.95, trust=1.0,
        metadata={"source": "NTangible platform metrics", "verified_date": "2026-03-15", "key": "assessment_count"})

    claim_alliance = _knowledge("approved_claim",
        "30,000+ athletes assessed through Alliance Fastpitch",
        "Over 30,000 athletes have been assessed through the Alliance Fastpitch partnership",
        confidence=0.95, trust=1.0,
        metadata={"source": "Alliance Fastpitch partnership", "verified_date": "2026-03-01", "key": "alliance_athlete_count"})

    claims = [claim_cf, claim_transfer, claim_bust, claim_churn, claim_assess, claim_alliance]
    all_objects.extend(claims)

    # ── 9. Schedule Rules (KnowledgeNodes) ─────────────────────────────
    sr_tue = _knowledge("schedule_rule", "Tuesday Thought Leadership Drop",
        "Fire thought leadership workflow every Tuesday at 10:00 ET",
        metadata={"cron": "0 14 * * 2", "workflow_slug": "tuesday-thought-leadership", "timezone": "America/New_York"})

    sr_fss = _knowledge("schedule_rule", "FSS Post-Event Leaderboard",
        "Fire leaderboard drop after Future Stars Series events",
        metadata={"cron": "0 16 * * 1", "workflow_slug": "fss-leaderboard-data-drop", "timezone": "America/New_York"})

    sr_newsletter = _knowledge("schedule_rule", "Weekly Newsletter",
        "Send weekly newsletter every Thursday at 9:00 ET",
        metadata={"cron": "0 13 * * 4", "workflow_slug": "weekly-newsletter", "timezone": "America/New_York"})

    rules = [sr_tue, sr_fss, sr_newsletter]
    all_objects.extend(rules)

    # ── 10. Sample Drafts (KnowledgeNodes) ─────────────────────────────
    d1 = _knowledge("draft",
        "The Blind Spot in Your Recruiting Process",
        "You measure arm strength, 40 time, GPA. You break down film until 2am. But you're still guessing on half the equation.\n\nClutch Factor™ measures what happens when it counts. 73% of athletes above 800 CF were named All-American. That's not a coincidence — it's a signal you're ignoring.",
        status="published", confidence=0.9, trust=0.95,
        metadata={"platform": "linkedin", "intent": "thought_leadership", "pillar": "blind_spot", "mode": "automatic", "hashtags": ["#MentalPerformance", "#Recruiting", "#ClutchFactor"]})

    d2 = _knowledge("draft",
        "Transfer Portal Math",
        "Average failed D1 transfer: $150K gone.\n\nMost programs evaluate transfers the same way they evaluate recruits — film, stats, maybe a campus visit.\n\nWhat if you could measure how they perform under pressure before the scholarship clears?",
        status="published", confidence=0.85, trust=0.9,
        metadata={"platform": "x", "intent": "brand", "pillar": "cost_of_guessing", "mode": "automatic", "hashtags": ["#TransferPortal", "#Data"]})

    d3 = _knowledge("draft",
        "Alliance Fastpitch: 30K Athletes Assessed",
        "30,000+ athletes assessed through @AllianceFP. That's not a pilot program — that's proof of concept at scale.\n\n6,000+ individual assessments. 1M+ data points. 7 sports and counting.",
        status="published", confidence=0.95, trust=1.0,
        metadata={"platform": "x", "intent": "brand", "pillar": "client_proof", "mode": "manual", "hashtags": ["#AllianceFastpitch", "#NTangible"]})

    d4 = _knowledge("draft",
        "What Separates Good from Great Under Pressure",
        "Personality tests tell you who someone is at rest. We measure who they are when it matters.\n\nCoach Alignment Index shows you how an athlete's mental performance profile maps to your program's needs. Not a personality match — a performance prediction.",
        status="review_required", confidence=0.8, trust=0.85,
        metadata={"platform": "linkedin", "intent": "thought_leadership", "pillar": "thought_leadership", "mode": "automatic", "hashtags": ["#SportScience", "#Recruiting"]})

    d5 = _knowledge("draft",
        "FSS Dallas Leaderboard: Top Clutch Factor Scores",
        "Future Stars Series — Dallas 2026\n\nTop Clutch Factor™ Scores:\n1. 892 — Infielder, Class of 2028\n2. 867 — RHP, Class of 2027\n3. 854 — OF, Class of 2028\n\nThese aren't just athletic tools. This is how they compete when it counts.",
        status="scheduled", confidence=0.9, trust=0.95,
        metadata={"platform": "instagram", "intent": "brand", "pillar": "client_proof", "mode": "automatic",
                  "hashtags": ["#FutureStarsSeries", "#ClutchFactor", "#Baseball", "#Recruiting", "#MentalPerformance", "#Dallas2026"]})

    d6 = _knowledge("draft",
        "Not a Survey. A Validated Cognitive Assessment.",
        "\"It's just another personality test.\"\n\nNo. The NTangible Assessment is a validated cognitive measure of decision-making under pressure. Not self-reported. Not a survey. Objective data.\n\n6,000+ assessments across 7 sports. The results speak.",
        status="review_required", confidence=0.85, trust=0.9,
        metadata={"platform": "linkedin", "intent": "brand", "pillar": "product", "mode": "manual", "hashtags": ["#SportsTech", "#Assessment"]})

    drafts = [d1, d2, d3, d4, d5, d6]
    all_objects.extend(drafts)

    # ── 11. Competitor Observations (KnowledgeNodes) ───────────────────
    obs1 = _knowledge("observation",
        "Scorability expanding into mental metrics",
        "Scorability has started marketing 'mental readiness scores' as part of their recruiting platform. Unclear methodology — appears survey-based.",
        confidence=0.6, trust=0.7,
        metadata={"competitor_slug": "scorability", "observed_date": "2026-03-20"})

    obs2 = _knowledge("observation",
        "S2 Cognition partnered with NFL combine",
        "S2 Cognition announced partnership with NFL Scouting Combine for cognitive testing. Different methodology (reaction time based) than NTangible's pressure-based approach.",
        confidence=0.8, trust=0.9,
        metadata={"competitor_slug": "s2-cognition", "observed_date": "2026-02-15"})

    observations = [obs1, obs2]
    all_objects.extend(observations)

    # ── 12. Content Sources (KnowledgeNodes) ───────────────────────────
    sources_data = [
        ("NTangible Homepage", "https://ntangible.com", "website"),
        ("NTangible Team Page", "https://ntangible.com/team", "website"),
        ("NTangible Research", "https://ntangible.com/research", "website"),
        ("NTangible Partners", "https://ntangible.com/partners", "website"),
        ("NTangible Instagram", "https://instagram.com/ntangible", "social"),
        ("NTangible LinkedIn", "https://linkedin.com/company/ntangible", "social"),
        ("NTangible YouTube", "https://youtube.com/@ntangible", "social"),
        ("Alliance Fastpitch Page", "https://ntangible.com/alliance", "partner_page"),
        ("Future Stars Series Page", "https://ntangible.com/future-stars-series", "partner_page"),
        ("FoundersPress Coverage", "https://founderspress.com", "press"),
        ("Youth Sports Business Report", "https://youthsportsbiz.com", "press"),
        ("MotorsportsNews Coverage", "https://motorsportsnews.com", "press"),
    ]
    content_sources = []
    for name, url, kind in sources_data:
        slug = name.lower().replace(" ", "-").replace(".", "-")
        node = _knowledge("reference_content", name, url, confidence=0.7, trust=0.8,
            metadata={"source_kind": kind, "url": url, "slug": slug})
        content_sources.append(node)
    all_objects.extend(content_sources)

    # ── 13. Template Configs (KnowledgeNodes) ──────────────────────────
    templates_data = [
        ("Instagram: Athlete Spotlight", "instagram", "athlete_spotlight", ["athlete_name", "sport", "cf_score", "school", "event_name"]),
        ("Instagram: Commitment Post", "instagram", "commitment_post", ["athlete_name", "sport", "cf_score", "school", "committed_to"]),
        ("Instagram: Clutch Certified", "instagram", "clutch_certified", ["athlete_name", "cf_score", "tier_label"]),
        ("Instagram: Event Leaderboard", "instagram", "event_leaderboard", ["event_name", "top_athletes", "date"]),
        ("Instagram: Bold Statement", "instagram", "bold_statement", ["quote_text", "attribution"]),
        ("X: Stat Card", "x", "stat_card", ["headline", "stat_value", "stat_label", "context"]),
        ("X: Quote Graphic", "x", "quote_graphic", ["quote_text", "attribution"]),
        ("LinkedIn: Thought Leadership Header", "linkedin", "thought_leadership_header", ["headline", "subtitle"]),
        ("LinkedIn: Partner Announcement", "linkedin", "partner_announcement", ["partner_name", "partner_logo_url", "headline"]),
        ("Shareable: Athlete Score Graphic", "shareable", "athlete_score_graphic", ["athlete_name", "score_tier", "sport"]),
    ]
    templates = []
    for name, platform, template_type, fields in templates_data:
        node = _knowledge("reference_content", name, f"Canva template: {name}",
            metadata={"template_type": template_type, "platform": platform, "data_fields": fields, "template_id": "pending_setup"})
        templates.append(node)
    all_objects.extend(templates)

    # ── Add everything to session ──────────────────────────────────────
    db.add_all(all_objects)
    db.flush()

    # ── 14. Entity Edges ───────────────────────────────────────────────
    edges = []

    # Workflows → Channels (publishes_to)
    edges.append(_entity_edge(wf_thought, ch_linkedin, "publishes_to"))
    edges.append(_entity_edge(wf_fss, ch_instagram, "publishes_to"))
    edges.append(_entity_edge(wf_fss, ch_x, "publishes_to"))
    edges.append(_entity_edge(wf_commit, ch_instagram, "publishes_to"))
    edges.append(_entity_edge(wf_commit, ch_x, "publishes_to"))
    edges.append(_entity_edge(wf_newsletter, ch_newsletter, "publishes_to"))
    edges.append(_entity_edge(wf_transfer, ch_x, "publishes_to"))
    edges.append(_entity_edge(wf_partner_roi, ch_linkedin, "publishes_to"))

    # Workflows → Pillars (uses_pillar)
    edges.append(_entity_edge(wf_thought, pil_thought, "uses_pillar"))
    edges.append(_entity_edge(wf_fss, pil_proof, "uses_pillar"))
    edges.append(_entity_edge(wf_commit, pil_proof, "uses_pillar"))
    edges.append(_entity_edge(wf_transfer, pil_cost, "uses_pillar"))
    edges.append(_entity_edge(wf_partner_roi, pil_proof, "uses_pillar"))

    # Partners → Workflows (triggers)
    edges.append(_entity_edge(p_fss, wf_fss, "triggers"))
    edges.append(_entity_edge(p_alliance, wf_commit, "triggers"))

    # Workflows → Drafts (produced) — entity→knowledge edges
    edges.append(_entity_edge(wf_thought, d1, "produced", source_type="entity", target_type="knowledge"))
    edges.append(_entity_edge(wf_transfer, d2, "produced", source_type="entity", target_type="knowledge"))
    edges.append(_entity_edge(wf_commit, d3, "produced", source_type="entity", target_type="knowledge"))
    edges.append(_entity_edge(wf_thought, d4, "produced", source_type="entity", target_type="knowledge"))
    edges.append(_entity_edge(wf_fss, d5, "produced", source_type="entity", target_type="knowledge"))
    edges.append(_entity_edge(wf_thought, d6, "produced", source_type="entity", target_type="knowledge"))

    # Clients → Competitors (competes_with via NTangible context)
    edges.append(_entity_edge(comp_s2, comp_scorability, "competes_with"))

    db.add_all(edges)
    db.flush()

    # ── 15. Knowledge Edges ────────────────────────────────────────────
    k_edges = []

    # Claims support drafts
    k_edges.append(_knowledge_edge(claim_cf, d1, "supports", confidence=0.95))
    k_edges.append(_knowledge_edge(claim_transfer, d2, "supports", confidence=0.9))
    k_edges.append(_knowledge_edge(claim_alliance, d3, "supports", confidence=0.95))
    k_edges.append(_knowledge_edge(claim_assess, d3, "supports", confidence=0.9))
    k_edges.append(_knowledge_edge(claim_assess, d6, "supports", confidence=0.9))

    # Voice guides drafts
    k_edges.append(_knowledge_edge(kn_voice, d1, "governs"))
    k_edges.append(_knowledge_edge(kn_voice, d2, "governs"))
    k_edges.append(_knowledge_edge(kn_voice, d4, "governs"))

    # Observations relate to competitors (via competitor slug in metadata)
    k_edges.append(_knowledge_edge(obs1, claim_assess, "challenges", confidence=0.4))
    k_edges.append(_knowledge_edge(obs2, claim_cf, "validates", confidence=0.6))

    # Schedule rules → drafts they produced
    k_edges.append(_knowledge_edge(sr_tue, d1, "triggered"))
    k_edges.append(_knowledge_edge(sr_tue, d4, "triggered"))
    k_edges.append(_knowledge_edge(sr_fss, d5, "triggered"))

    db.add_all(k_edges)
    db.commit()

    # ── Summary ────────────────────────────────────────────────────────
    entity_count = len(channels) + len(workflows) + len(partners) + len(clients) + len(competitors) + len(pillars)
    knowledge_count = 1 + len(claims) + len(rules) + len(drafts) + len(observations) + len(content_sources) + len(templates)
    print(f"Seeded {entity_count} entity nodes")
    print(f"Seeded {knowledge_count} knowledge nodes")
    print(f"Seeded {len(edges)} entity edges")
    print(f"Seeded {len(k_edges)} knowledge edges")
    print("Done.")

    db.close()


if __name__ == "__main__":
    seed()
