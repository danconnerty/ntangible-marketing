# Single-Tenant Connected Publishing Design

**Date:** 2026-04-09  
**Status:** Approved for implementation  
**Scope:** One NTangible dashboard with persisted connected accounts, editable publishing destinations, and publish-time destination selection

---

## Goal

Replace `.env`-only publishing credentials with in-app connected account management for a single NTangible installation.

The dashboard should let operators:

- connect publish providers in settings
- persist provider credentials and configuration inside the app
- add, remove, and switch social media pages/accounts/destinations
- publish drafts with one button through the selected destination
- keep scheduled and automatic publishing aligned with the selected destination

This design explicitly ignores SaaS tenancy and per-client workspace isolation.

---

## Product Outcome

The app remains one control room, but its publishing settings become runtime-configurable instead of deploy-time-configurable.

There is:

- one installation
- one settings surface for connections
- one set of connected channels
- many editable destinations under those channels

Examples:

- LinkedIn connection with multiple organization pages, one active
- Instagram connection with multiple business destinations, one active
- X connection with one or more accounts, one active
- newsletter/blog providers configured in-app rather than via `.env`

---

## In Scope

- single-tenant connection model
- persisted app connections for X, LinkedIn, Instagram, newsletter, and blog
- persisted publishing destinations/pages/accounts under those connections
- active destination switching
- add/remove destination management
- settings UI for connection summary and destination editing
- publish-path integration so existing draft publish actions use the active destination

---

## Out Of Scope

- multi-client workspaces
- user/team auth redesign
- billing
- universal connector marketplace
- full provider coverage for every possible app

---

## Architecture

```text
settings page
-> app connection record
-> destination records
-> active destination selection
-> publish action
-> destination-aware publisher factory
-> provider API
```

The app will introduce a connection subsystem but continue reusing:

- existing control-room UI
- scheduler
- review queue
- draft models
- channel-specific publisher adapters

---

## Data Model

### AppConnection

Represents one configured channel/provider for the installation.

Fields:

- id
- channel (`x`, `linkedin`, `instagram`, `newsletter`, `blog`)
- provider_key
- auth_mode
- status
- connection_label
- config_json
- credential_json
- last_validated_at
- last_error
- created_at
- updated_at

### PublishingDestination

Represents a concrete post target under a connection.

Fields:

- id
- app_connection_id
- external_id
- destination_type
- label
- config_json
- is_active
- created_at
- updated_at

Examples:

- LinkedIn organization URN
- Instagram business account id
- X account id/screen name
- Mailchimp audience/segment target
- Blog site or publication target

---

## UX

The existing `/control-room/settings` page becomes the connection manager.

Operators should be able to:

- see current channel connection status
- add/update a connection
- add a destination/page/account
- remove a destination/page/account
- switch the active destination for a channel

The control room should show which destination is currently active for each channel.

---

## Publish Behavior

When a draft is published:

1. resolve the channel
2. load the matching app connection
3. load the active destination for that channel
4. build the publisher with connection credentials plus destination-specific config
5. publish using the selected destination

Scheduled and automatic publishing should resolve the same active destination at runtime.

---

## Compatibility

Environment-based configuration remains as a fallback for legacy or unconfigured channels.

Priority order:

1. active in-app connection + destination
2. legacy `.env` configuration

This keeps the app usable while connected publishing is rolled out incrementally.

---

## Recommendation

Implement this in two slices:

1. Add persistent connection and destination records, settings UI, and active-destination switching.
2. Refactor publish paths to use the selected destination before falling back to `.env`.

That delivers the requested behavior without forcing the repo into a SaaS model it does not need.
