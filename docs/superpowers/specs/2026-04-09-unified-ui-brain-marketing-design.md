# Unified UI: Brain + Marketing with Agent-Engine Design System

**Date:** 2026-04-09
**Status:** Approved

## Summary

Port the agent-engine's visual design system to the ntangible_marketing FastAPI/Jinja2 app. Replace the topbar navigation with a collapsible sidebar containing a Brain/Marketing toggle pill. Add new Brain pages. Restyle all existing Marketing pages with the agent-engine's design language. Support light (default) and dark mode with a toggle.

## Layout

### Sidebar (replaces topbar)
- Width: 224px expanded, 64px collapsed
- Collapsible via toggle button
- Smooth 200ms transition
- Position: fixed left, full height

### Sidebar Structure (top to bottom)
1. **Brand header**: Green dot + "NTangible" text
2. **Mode toggle pill**: Segmented control — "Brain" | "Marketing"
   - Active segment: filled background, white text
   - Inactive segment: muted text
   - Clicking swaps the nav items below
3. **Nav items**: Icon + label, one active state at a time
   - Active: accent background, foreground text
   - Inactive: muted-foreground, hover reveals accent/50
4. **Footer**: Theme toggle (sun/moon icon + label)

### Nav Items by Mode

**Brain:**
| Label | Icon | Route |
|-------|------|-------|
| Overview | Home | /control-room/brain/ |
| Graph | Network | /control-room/brain/graph |
| Knowledge | Brain | /control-room/brain/knowledge |
| Review | CheckCircle2 | /control-room/brain/review |
| Sources | Database | /control-room/brain/sources |
| Topics | Layers | /control-room/brain/topics |

**Marketing:**
| Label | Icon | Route |
|-------|------|-------|
| Dashboard | LayoutDashboard | /control-room/ |
| Activity | Activity | /control-room/activity |
| Workflows | GitBranch | /control-room/workflows |
| Analytics | BarChart3 | /control-room/analytics |
| Calendar | Calendar | /control-room/calendar |
| Expansion | Rocket | /control-room/expansion |
| Revenue | DollarSign | /control-room/revenue |
| Status | Signal | /control-room/status |

### Main Content Area
- `flex: 1`, scrollable vertically
- Padding: 24px (desktop), 16px (mobile)
- Max content width: none (fluid within remaining space)

## Design System

### Typography
- **Primary font**: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif
- **Mono font**: "SFMono-Regular", "Menlo", "Monaco", monospace
- **Base size**: 14px, line-height 1.5
- **Scale**: text-xs (12px), text-sm (14px), text-base (16px), text-lg (18px), text-xl (20px), text-2xl (24px)

### Color Tokens (CSS custom properties, oklch)

**Light mode (default):**
```
--background: oklch(0.985 0 0)
--foreground: oklch(0.145 0 0)
--card: oklch(1 0 0)
--card-foreground: oklch(0.145 0 0)
--primary: oklch(0.205 0 0)
--primary-foreground: oklch(0.985 0 0)
--secondary: oklch(0.97 0 0)
--secondary-foreground: oklch(0.205 0 0)
--muted: oklch(0.97 0 0)
--muted-foreground: oklch(0.45 0 0)
--accent: oklch(0.95 0 0)
--accent-foreground: oklch(0.145 0 0)
--border: oklch(0.9 0 0)
--input: oklch(0.9 0 0)
--ring: oklch(0.708 0 0)
--destructive: oklch(0.704 0.191 22.216)
--success: oklch(0.627 0.194 149.214)
--warning: oklch(0.769 0.188 70.08)
--sidebar: oklch(0.97 0 0)
--sidebar-foreground: oklch(0.145 0 0)
--sidebar-accent: oklch(0.92 0 0)
--sidebar-accent-foreground: oklch(0.145 0 0)
--sidebar-border: oklch(0.9 0 0)
```

**Dark mode (`.dark` class on `<html>`):**
```
--background: oklch(0.145 0 0)
--foreground: oklch(0.985 0 0)
--card: oklch(0.205 0 0)
--card-foreground: oklch(0.985 0 0)
--primary: oklch(0.922 0 0)
--primary-foreground: oklch(0.205 0 0)
--secondary: oklch(0.269 0 0)
--secondary-foreground: oklch(0.985 0 0)
--muted: oklch(0.269 0 0)
--muted-foreground: oklch(0.708 0 0)
--accent: oklch(0.269 0 0)
--accent-foreground: oklch(0.985 0 0)
--border: oklch(1 0 0 / 10%)
--input: oklch(1 0 0 / 15%)
--ring: oklch(0.556 0 0)
--sidebar: oklch(0.17 0 0)
--sidebar-foreground: oklch(0.985 0 0)
--sidebar-accent: oklch(0.227 0 0)
--sidebar-accent-foreground: oklch(0.985 0 0)
--sidebar-border: oklch(1 0 0 / 10%)
```

### Chart Colors
```
--chart-1: oklch(0.646 0.222 41.116)   /* orange */
--chart-2: oklch(0.6 0.118 184.714)    /* teal */
--chart-3: oklch(0.398 0.07 227.392)   /* indigo */
--chart-4: oklch(0.828 0.189 84.429)   /* lime */
--chart-5: oklch(0.769 0.188 70.08)    /* amber */
```

### Border Radius
- `--radius`: 0.625rem (10px)
- sm: calc(var(--radius) * 0.6)
- md: calc(var(--radius) * 0.8)
- lg: var(--radius)
- xl: calc(var(--radius) * 1.4)
- 2xl: calc(var(--radius) * 1.8)

### Icons
- **Library**: Lucide icons via CDN (https://unpkg.com/lucide-static@latest/icons/)
- **Delivery**: Inline SVG in Jinja2 macros or `<img>` tags referencing CDN SVGs
- **Size**: 16px (nav items), 20px (page headers), 14px (inline)
- **Color**: `currentColor` — inherits from parent text color

### Component Classes

**Card:**
- Background: var(--card), border: 1px solid var(--border)
- Border-radius: var(--radius-xl)
- Padding: 16px (default), 12px (sm variant)

**Badge:**
- Pill-shaped (border-radius: 9999px), height: 20px
- Variants: default (primary bg), secondary, destructive, outline, ghost
- Status colors: green (published/active), amber (review/pending), red (rejected/failed), blue (scheduled)

**Button:**
- Height: 32px (default), 28px (sm), 36px (lg)
- Variants: default (primary bg), outline, secondary, ghost, destructive
- Border-radius: var(--radius-lg)
- Focus: ring-3 ring-ring/50

**Table:**
- Full width, horizontal scroll on overflow
- Header: text-muted-foreground, font-medium
- Rows: hover bg-muted/50
- Borders: bottom border on rows

**Input/Textarea:**
- Height: 32px (input), min-height 64px (textarea)
- Border: 1px solid var(--input), rounded-lg
- Focus: border-ring, ring-3 ring-ring/50

### Transitions
- All elements: 200ms ease for background-color, color, border-color
- Sidebar collapse: 200ms ease width transition

### Scrollbar
- Width: 6px
- Track: transparent
- Thumb: oklch(0.5 0 0 / 20%), hover darker
- Border-radius: 3px

## Brain Pages (New)

### Overview (`/control-room/brain/`)
- 4 stat cards in a row: Entities, Knowledge, Edges, Sources
  - Each with colored icon badge (blue, emerald, violet, amber)
  - Shows count + label
- Recent Knowledge section: last 8 knowledge nodes, card list with kind badge + title + confidence
- Topic profiles section: each topic with entity/knowledge counts

### Graph (`/control-room/brain/graph`)
- Existing D3 force-directed graph — already implemented
- Move from `/control-room/graph` to `/control-room/brain/graph`
- Keep dark background container regardless of theme

### Knowledge (`/control-room/brain/knowledge`)
- Filter bar: kind dropdown, status dropdown, search text input
- Table view: title, kind (badge), status (badge), confidence (colored), created_at
- Click row to expand details in drawer

### Review (`/control-room/brain/review`)
- Cards for drafts in `review_required` status
- Each card: title, platform badge, pillar, content preview
- Actions: Approve (post now), Schedule (date picker), Reject

### Sources (`/control-room/brain/sources`)
- Table of content brain sources
- Columns: name, source_kind (badge), URL, last snapshot date

### Topics (`/control-room/brain/topics`)
- Card per TopicProfile
- Shows: display_name, description, entity count, knowledge count
- Feature flags: context_enabled, intelligence_enabled, memory_enabled as toggle indicators

## Marketing Pages (Restyled)

All existing marketing pages keep their routes, logic, htmx interactions, and Alpine.js behavior. Only the visual wrapper changes:

- `base.html` → new sidebar layout
- CSS classes updated to use new design tokens
- Cards, badges, tables, buttons use new component classes
- Icons switch from text/emoji to Lucide SVGs
- Same content, same interactions, new look

### Existing pages (routes unchanged):
- Dashboard: `/control-room/`
- Activity: `/control-room/activity`
- Workflows: `/control-room/workflows`
- Analytics: `/control-room/analytics`
- Calendar: `/control-room/calendar`
- Expansion: `/control-room/expansion`
- Revenue: `/control-room/revenue`
- Status: `/control-room/status`

### Sub-pages (routes unchanged):
- Manual/Automatic/Rejected/Expired review views
- Workflow detail
- Platform detail
- Partners, Leads, Competitors, Campaigns
- Blog, Video, UGC, Science, Sports, Repurposing
- Settings, Trigger Feed

## Theme System

- Default: light mode
- Toggle in sidebar footer switches `.dark` class on `<html>`
- Persisted to `localStorage` key `ntangible-theme`
- On page load: check localStorage, apply before render (inline script in `<head>` to prevent flash)
- System preference fallback: `prefers-color-scheme: dark` if no stored preference

## Tech Stack (unchanged)

- FastAPI + Jinja2 templates
- htmx for partial page updates
- Alpine.js for client-side interactivity
- Plain CSS with custom properties (no Tailwind, no build step)
- Lucide icons via CDN
- D3.js for graph visualization

## File Changes

### New files:
- `app/static/css/control_room.css` — complete rewrite with agent-engine design system
- `app/web/templates/base.html` — new sidebar layout
- `app/web/templates/brain_overview.html`
- `app/web/templates/brain_knowledge.html`
- `app/web/templates/brain_review.html`
- `app/web/templates/brain_sources.html`
- `app/web/templates/brain_topics.html`

### Modified files:
- `app/web/routes.py` — add brain page routes, move graph route
- All existing templates — update class names to new design system

### Preserved:
- All existing route logic and template functionality
- htmx/Alpine.js interactions
- Backend services, models, database
