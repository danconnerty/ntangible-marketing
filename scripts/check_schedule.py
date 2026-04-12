"""Quick check: what's on today's marketing schedule."""

from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.review import DraftVariant
from app.models.trigger import CalendarRule
from app.models.workflow import DraftState, Workflow

db = SessionLocal()

rules = (
    db.query(CalendarRule)
    .join(Workflow)
    .filter(
        CalendarRule.enabled == True,
        Workflow.enabled == True,
        Workflow.paused_at.is_(None),
    )
    .all()
)
print("=== Active Calendar Rules ===")
for r in rules:
    w = db.get(Workflow, r.workflow_id)
    print(f"  {w.slug}: cron={r.cron_expression} tz={r.timezone} next_fire={r.next_fire_at}")

today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
today_end = today_start + timedelta(days=1)
drafts = (
    db.query(DraftVariant)
    .filter(
        DraftVariant.scheduled_publish_at.between(today_start, today_end),
        DraftVariant.state.in_([DraftState.AUTOMATIC_READY, DraftState.SCHEDULED_MANUAL]),
    )
    .all()
)
print()
print(f"=== Drafts Scheduled Today ({today_start.strftime('%Y-%m-%d')}) ===")
for d in drafts:
    print(f"  draft={d.id} platform={d.platform.value} state={d.state.value} publish_at={d.scheduled_publish_at}")
if not drafts:
    print("  (none)")

db.close()
