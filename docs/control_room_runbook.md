# NTangible Control Room Runbook

## If drafts stop appearing

1. Check the API logs for workflow execution errors.
2. Verify `workflows.enabled = true`.
3. Verify the workflow has an active version.
4. Check `trigger_events.processing_status` and `content_jobs.error_message`.
5. Search `Brain / History` to confirm memory sync is still running.

## If automatic posts stop publishing

1. Confirm the scheduler process is running.
2. Check `draft_variants` where `state in ('automatic_ready', 'scheduled_manual')`.
3. Verify `scheduled_publish_at` is populated and in UTC.
4. Check publisher credentials and outbound platform errors in `failure_reason`.

## If manual drafts are disappearing

- Manual drafts expire at end of day by design.
- Review `Expired` history to confirm timeout rather than rejection or failure.

## If workflow improvements are not changing results

1. Confirm a new `workflow_versions` row was created.
2. Confirm the new version is active.
3. Check `prompt_snapshot` on later `content_jobs`.
4. Check the `retrieved_memory_ids` on the job to verify the brain is feeding the right examples.

## If competitor signals are not creating drafts

1. Confirm the signal appears in `competitor_signals`.
2. Confirm the response workflow exists for the requested platform, for example `competitor-response-linkedin`.
3. Check `trigger_events` for `event_type = competitor_signal`.
4. Review `content_jobs.error_message` if the workflow run failed.

## If lead nurture drafts are not appearing

1. Confirm the lead exists in `lead_accounts`.
2. Check whether a row was created in `lead_nurture_tasks`.
3. Confirm the `lead-nurture-*` workflow exists and has an active version.
4. Check `trigger_events.source_payload` for the embedded lead context.

## Safe recovery actions

- Move an automatic workflow back to manual.
- Pause publishing on individual automatic drafts.
- Re-run seed/demo data in a local environment only.
- Rebuild analytics snapshots from canonical records.
