# NTangible Control Room Operator Guide

## Daily workflow

1. Open `/control-room/`.
2. Check `Manual` first. Every draft there was generated today and requires a decision before end of day.
3. Use:
   - `Post Now` for immediate publishing
   - `Schedule` for a manual post that should go out later today
   - `Reject` when the draft is wrong
   - `Why This Draft?` to inspect the trigger, compliance, prompt context, and assets
   - `Improve Workflow` when the recipe needs to change for future drafts
4. Check `Automatic` for timed workflows that are allowed to publish on their own.
5. Review `Trigger Feed` for partner and external events.
6. Use `Brain / History` to find past approved or rejected examples.
7. Use `Analytics` to judge which workflows are earning trust and which still need manual review.
8. Use `Campaigns`, `Competitors`, and `Leads` for the Phase 11 go-to-market workflows:
   - `Campaigns` runs mapped workflow sets through the canonical trigger path.
   - `Competitors` captures market signals and creates response drafts.
   - `Leads` suggests nurture follow-ups and creates manual-first sales content drafts.

## Manual queue rules

- Manual drafts live in the all-day queue.
- If no action is taken by end of day, the draft moves to `Expired`.
- `Rejected` and `Expired` are read-only history.
- Rejected drafts are feedback for the workflow. They are not hand-edited back into the queue.

## Workflow improvement

Use `Improve Workflow` when a draft is systematically wrong. Good examples:

- "Too corporate. Use more hard data and shorter paragraphs."
- "This should feel more athlete-facing."
- "Stop using generic hooks."

The system creates a new workflow version first. Review that proposal, then activate it.

## Automatic mode

- Automatic workflows still generate canonical drafts.
- The scheduler publishes `Automatic` drafts at their configured time.
- `Pause` or `Move to Manual` if trust drops.

## Trigger types

- `Calendar Trigger`: recurring rule fired on schedule.
- `External Trigger`: partner or webhook event arrived.
- `Manual Request`: operator requested a draft directly.

## Access

- If control-room auth is enabled, operators sign in at `/control-room/login`.
- The app stores an internal session cookie for the control-room UI only.
