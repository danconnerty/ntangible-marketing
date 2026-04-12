# Multi-Client Connected Publishing Design

**Date:** 2026-04-08  
**Status:** Approved for implementation  
**Scope:** Multi-client workspaces with client-owned connected accounts, manual publishing, scheduling, and automatic posting

---

## Goal

Evolve the NTangible Marketing Engine from a single-installation operator tool with global environment-based credentials into a multi-client product where each client:

- signs into their own isolated workspace
- connects their own publishing accounts
- publishes content with a button click
- schedules future publishing
- enables automatic posting when their connections are healthy

The target experience is plug-and-play for major social platforms and configurable for newsletter, blog, and long-tail external providers.

---

## Product Outcome

The product becomes a tenant-aware control room with per-client connected channels.

Each workspace has:

1. **Its own login**
   Phase 1 supports a single owner login per workspace.

2. **Its own connected accounts**
   LinkedIn, Instagram, X, newsletter, and blog connections belong to the workspace, not the installation.

3. **Its own content queue**
   Drafts, schedules, assets, and publish history are scoped to one workspace only.

4. **Its own automation state**
   Automatic workflows run only when the workspace has healthy channel connections.

5. **Its own settings and recovery path**
   When tokens expire or configuration breaks, only that workspace is affected.

---

## In Scope

### Workspace model

- isolated client workspaces
- one owner login per workspace in phase 1
- workspace-scoped content, workflows, schedules, assets, and publish history

### Connected publishing

- native connected-account flows for:
  - LinkedIn
  - Instagram
  - X
- configurable provider model for:
  - newsletter tools
  - blog/CMS tools
  - custom HTTP or webhook-based providers

### Publish capabilities

- publish now from workspace UI
- schedule future publishing
- automatic posting through existing scheduler patterns
- per-workspace connection health checks

### Operational behavior

- encrypted credential storage
- per-connection status tracking
- preflight validation before publish
- workspace-scoped failure handling and pause behavior

---

## Out Of Scope

- multi-user workspace collaboration beyond one owner login
- agency-wide cross-client admin access
- billing and subscription management
- third-party marketplace of prebuilt connectors
- true no-config support for every possible external provider
- browser automation as a primary publishing mechanism

The phrase "works with any provider" is implemented here as a configurable connector model for non-native systems, not as a promise that every social platform can be connected through one identical flow.

---

## Decision Summary

### Recommended architecture

Adopt a hybrid connection model:

- **Native connectors** for LinkedIn, Instagram, and X
- **Universal connectors** for newsletter, blog, and long-tail providers

### Why this is the right design

- It preserves the best client UX for the most important channels.
- It fits the existing publisher-adapter structure already present in the repo.
- It supports "configurable" integrations without forcing every platform into the same weak abstraction.
- It allows scheduling and automatic posting to remain reliable because the system can validate connection health before publish time.

### Rejected approaches

#### Native-only everywhere

Pros:
- best UX and reliability for supported platforms

Cons:
- fails the user's requirement for broad provider support
- creates permanent engineering drag for every new provider

#### Browser automation as the integration strategy

Pros:
- appears broad at first

Cons:
- unreliable for scheduled publishing
- poor security and support characteristics
- more re-logins, MFA interruptions, breakage, and ambiguous failures

---

## Current-State Gaps In The Repo

Today the system is still installation-scoped rather than workspace-scoped:

- channel credentials are read from `.env` in [app/config.py](/Users/elliot18/Desktop/Home/Projects/ntangible_marketing/app/config.py)
- auth in [app/auth.py](/Users/elliot18/Desktop/Home/Projects/ntangible_marketing/app/auth.py) is app-level, not tenant-aware
- publishers such as LinkedIn, Instagram, X, blog, and newsletter adapters currently assume one server-side credential set
- the scheduler and review queue assume drafts can be published without resolving a workspace connection record

The existing modular monolith is still a good foundation. The required change is not a rewrite of the workflow engine or scheduler; it is a tenancy and connection-layer refactor around them.

---

## Architecture

The system should remain a modular monolith and extend the existing control-room pipeline:

```text
workspace user
-> workspace auth/session
-> workspace-scoped control room
-> draft action (publish now / schedule / automatic)
-> connection resolver
-> publish preflight
-> native or universal publisher adapter
-> provider response
-> workspace publish log + draft state update
```

### Existing systems reused

- `Workflow` / `WorkflowVersion`
- `TriggerEvent`
- `ContentJob`
- `DraftVariant`
- `ReviewQueue`
- `SchedulerService`
- `Asset`
- analytics ingestion

### New subsystem boundary

Add a tenant connection subsystem responsible for:

- workspace identity
- workspace-scoped auth
- workspace membership
- channel connection storage
- token refresh / credential validation
- connection status and capability reporting
- adapter resolution for publish operations

---

## Data Model

### Workspace

Represents a single client's isolated tenant.

Fields:

- id
- slug
- display_name
- status
- timezone
- created_at
- updated_at

### WorkspaceUser

Phase 1 supports one owner, but the model should not hard-code single-user forever.

Fields:

- id
- email or username
- password_hash or external auth subject
- status
- created_at
- updated_at

### WorkspaceMembership

Joins users to workspaces.

Fields:

- id
- workspace_id
- user_id
- role
- created_at

For phase 1, allowed role can be just `owner`.

### AppConnection

Canonical record for a connected or configured channel.

Fields:

- id
- workspace_id
- channel
  - `linkedin`
  - `instagram`
  - `x`
  - `newsletter`
  - `blog`
- connector_kind
  - `native_oauth`
  - `api_key`
  - `custom_api`
  - `custom_webhook`
- provider_key
  - examples: `linkedin`, `instagram_graph`, `x_api`, `mailchimp`, `wordpress`, `custom`
- status
  - `not_connected`
  - `connected`
  - `expired`
  - `action_required`
  - `failed`
  - `disabled`
- account_label
- external_account_id
- scopes
- capabilities
- encrypted_credentials
- refresh_metadata
- config_json
- last_validated_at
- last_success_at
- last_error
- created_at
- updated_at

### ConnectionAuditLog

Tracks connect, refresh, validate, disconnect, and failure events.

Fields:

- id
- app_connection_id
- event_type
- event_payload
- status
- created_at

### PublishAttempt

Tracks all outbound publish attempts using workspace connections.

Fields:

- id
- workspace_id
- draft_variant_id
- app_connection_id
- scheduled_by
- execution_mode
  - `manual`
  - `scheduled_manual`
  - `automatic`
- preflight_status
- provider_request_payload
- provider_response_payload
- publish_status
  - `succeeded`
  - `failed`
  - `ambiguous`
- external_post_id
- external_url
- error_code
- error_message
- started_at
- completed_at

---

## Multi-Tenant Scoping Rules

All canonical records that can surface to a client must be tenant-scoped.

At minimum, add `workspace_id` to:

- `workflows`
- `workflow_versions` if versions are tenant-specific
- `calendar_rules`
- `trigger_events`
- `content_jobs`
- `draft_variants`
- `assets`
- analytics snapshots
- blog/newsletter/provider-specific records where relevant

Rules:

- no workspace can query another workspace's drafts, schedules, assets, publish history, or connections
- all control-room views must filter by workspace
- scheduler ticks must operate per workspace connection state
- legacy routes should either become workspace-aware or be restricted to internal/admin use

---

## Connection Model

### Native connectors

Required for:

- LinkedIn
- Instagram
- X

Behavior:

- user clicks `Connect`
- user completes provider-specific auth
- system stores workspace-scoped account identity, token material, scopes, capabilities, and expiry metadata
- connection is periodically or opportunistically revalidated

Why native connectors are required:

- these platforms have distinct auth rules
- they have channel-specific posting rules
- scheduling and publishing reliability depends on platform-specific validation
- a generic connector cannot deliver a comparable UX here

### Universal connectors

Required for:

- newsletter tools
- blog/CMS tools
- long-tail provider integrations

Supported connection modes:

- API key
- OAuth when the provider supports it
- custom HTTP API definition
- webhook delivery definition

Universal connector config should support:

- base URL
- auth scheme
- secret fields
- request method
- request path
- headers
- payload template
- field mapping from canonical draft data
- validation request
- publish success extraction

This model is the correct implementation of the user's "configurable" requirement. It broadens support, but it is not the same UX as a first-class native connector.

---

## Client-Facing UX

### Workspace onboarding

On first login, the client should land on a dedicated workspace onboarding path:

1. workspace created
2. owner signs in
3. `Connect your channels` screen appears
4. each supported channel is shown with:
   - status
   - connect/configure action
   - connected account label if present
   - last validation state

### Control room UX

Every control-room page becomes workspace-scoped.

Draft cards must show:

- target channel
- connected account label
- connection health
- whether `Publish now` is available
- whether scheduling is available

Buttons:

- `Publish now`
- `Schedule`
- `Reconnect` or `Fix connection` when applicable

### Settings UX

Each connection page should show:

- channel
- provider/connector type
- connected account name
- last successful validation
- current status
- detected capabilities
- last error
- reconnect action
- disconnect action
- test connection action

### UX guardrails

- do not allow a late failure when the system already knows the connection is invalid
- disable publish/schedule actions when preflight cannot pass
- show actionable error states in settings rather than generic failures in the draft queue

---

## Publish Flow

### Manual publish

1. user clicks `Publish now`
2. system loads draft + workspace + target connection
3. system runs preflight validation
4. if preflight passes, system invokes the matching adapter
5. publish result is written to `PublishAttempt`
6. draft state updates to `published`, `failed`, or `publishing_unknown`

### Scheduled publish

1. user clicks `Schedule`
2. system persists scheduled time on the draft
3. scheduler resolves the workspace connection at execution time
4. scheduler runs the same preflight validation
5. publish result is recorded exactly as in manual publish

### Automatic publish

1. workflow runs in automatic mode
2. generated drafts enter automatic-ready state
3. scheduler attempts publish only if connection status is healthy
4. if the connection is invalid, pause or demote the workflow for that workspace

---

## Preflight Validation

Every publish path must use a shared preflight layer.

Checks:

- workspace exists and is active
- draft belongs to workspace
- matching connection exists
- connection status is publishable
- token/credential has not expired
- required scopes or capabilities are present
- required provider config fields exist
- asset/media requirements are satisfied
- scheduled or automatic mode is permitted for that connector

Preflight outcomes:

- `pass`
- `retryable_failure`
- `action_required`
- `hard_failure`

---

## Failure Handling

### Connection failure

If auth or credential validation fails:

- mark connection `expired` or `action_required`
- block future publish attempts for that connection
- show reconnect action in workspace settings

### Payload failure

If provider rejects the content payload:

- keep connection healthy
- mark draft failed
- store provider error in publish attempt and draft failure reason

### Ambiguous publish result

If the provider response is unclear:

- set draft state to `publishing_unknown`
- preserve request/response metadata
- surface manual follow-up in the workspace UI

### Automatic mode safety

If automatic posting fails because the workspace connection is broken:

- pause only that workspace's affected workflow
- do not affect other workspaces
- do not disable unrelated channels

---

## Security

### Credential storage

- never store raw tenant credentials in plaintext
- encrypt connection secrets at rest
- separate application-level secrets from tenant-level credentials

### Environment variables

`.env` should remain only for:

- database and infrastructure settings
- encryption keys
- platform-level OAuth client ids and secrets
- internal service settings

`.env` should no longer be the source of truth for client-owned publish credentials.

### Access control

- workspace session must determine workspace scope on every control-room request
- publish APIs must reject cross-workspace draft and connection access
- audit logs must exist for connect, reconnect, disconnect, and publish actions

---

## Impact On Existing Code

### Keep and extend

- `SchedulerService`
- `WorkflowEngine`
- `ReviewQueue`
- existing publisher base classes and channel-specific publish logic

### Refactor

- [app/config.py](/Users/elliot18/Desktop/Home/Projects/ntangible_marketing/app/config.py)
  - keep infrastructure settings
  - stop using tenant channel credentials as global config

- [app/auth.py](/Users/elliot18/Desktop/Home/Projects/ntangible_marketing/app/auth.py)
  - replace app-wide control-room login with workspace-aware auth

- publisher factories in `app/publishers/`
  - resolve publishers from workspace connection records rather than only `.env`

- [app/services/review_queue.py](/Users/elliot18/Desktop/Home/Projects/ntangible_marketing/app/services/review_queue.py)
  - publish through connection-aware adapter resolution

- [app/services/scheduler.py](/Users/elliot18/Desktop/Home/Projects/ntangible_marketing/app/services/scheduler.py)
  - validate workspace connection health before scheduled/automatic publish

- web routes in [app/web/routes.py](/Users/elliot18/Desktop/Home/Projects/ntangible_marketing/app/web/routes.py)
  - filter all pages by workspace
  - add connection settings surfaces

### New services

- `WorkspaceService`
- `WorkspaceAuthService`
- `ConnectionService`
- `ConnectionEncryptionService`
- `ConnectionValidationService`
- `ConnectionResolver`
- `PublishAttemptService`
- `UniversalConnectorService`

---

## Migration Strategy

### Phase 1

- add workspace, user, membership, connection, and publish-attempt tables
- make existing data model workspace-aware
- add single-owner workspace auth
- implement connection settings UI and APIs

### Phase 2

- migrate native publishers to load credentials from workspace connections
- preserve current `.env` publishers only for internal fallback or bootstrap paths

### Phase 3

- add universal connector framework for newsletter/blog/custom systems
- add validation and test-connection UX

### Phase 4

- enforce automatic workflow safety based on workspace connection health
- expand analytics and history views to include connection-level publish outcomes

---

## Testing Strategy

### Model and migration tests

- workspace isolation
- required foreign keys and indexes
- tenant-scoped queries

### Connection tests

- connect
- refresh
- validate
- expire
- reconnect
- disconnect

### Publish tests

- native publish success/failure per platform
- universal connector success/failure
- preflight rejection paths
- ambiguous result handling

### Scheduler tests

- scheduled publish with healthy connection
- scheduled publish with expired connection
- automatic workflow pause on connection failure

### End-to-end tests

- workspace owner login -> connect channel -> publish now
- workspace owner login -> connect channel -> schedule publish -> scheduler executes
- broken connection -> UI blocks publish and shows reconnect state

---

## Success Criteria

Phase 1 is successful when:

- a client can sign into a workspace that only exposes their data
- the client can connect LinkedIn, Instagram, and X accounts through native flows
- the client can configure newsletter and blog providers without editing server `.env`
- `Publish now` works using the client's connected accounts
- scheduled and automatic publishing use workspace-scoped connections safely
- connection failures are surfaced clearly and isolated to the affected workspace

---

## Final Recommendation

Implement a hybrid multi-tenant publishing architecture:

- isolated client workspaces
- one owner login per workspace in phase 1
- native connectors for major social platforms
- configurable universal connectors for newsletter, blog, and long-tail providers
- shared preflight validation for manual, scheduled, and automatic publishing

This design delivers the requested product direction without over-promising a fake universal connector for every platform, and it fits the repo's existing workflow engine, scheduler, and publisher adapter structure.
