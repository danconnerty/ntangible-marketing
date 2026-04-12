# NTangible Marketing Engine

## Quick Commands

### "What's on today's schedule?" / "What marketing is scheduled?"
When the user asks about the schedule, immediately run the script — don't explain the architecture or ask permission:

```bash
python3 scripts/check_schedule.py
```

Then summarize the results in plain language. Don't ask the user if they want you to run it — just run it.

## Development

- Python 3.13, use `python3` (not `python`)
- Database: SQLAlchemy + Alembic migrations
- Scheduler: `app/services/scheduler.py` — polls every 15s, fires CalendarRules (cron) and publishes due DraftVariants
- Tests: `pytest`
