# Unified UI: Brain + Marketing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the agent-engine's dark/light design system to ntangible_marketing, add a sidebar with Brain/Marketing toggle, create 6 Brain pages, restyle existing Marketing pages.

**Architecture:** Replace the topbar with a collapsible sidebar containing a segmented Brain/Marketing toggle pill. CSS custom properties swap between light/dark mode via `.dark` class on `<html>`. Existing class names (`.card`, `.badge`, `.btn`, `.table`) are preserved so most templates only need base.html changes, not class renames. New Brain pages use the same BrainQuery service already in the codebase.

**Tech Stack:** FastAPI, Jinja2, plain CSS (oklch tokens), Alpine.js, htmx, Lucide icons via CDN, D3.js

**Spec:** `docs/superpowers/specs/2026-04-09-unified-ui-brain-marketing-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `app/static/css/control_room.css` | Rewrite | Full design system: tokens, sidebar, components |
| `app/web/templates/base.html` | Rewrite | Sidebar layout, toggle pill, theme toggle, icon macros |
| `app/web/routes.py` | Modify | Add 6 brain routes, update graph route |
| `app/web/templates/brain_overview.html` | Create | Stats cards, recent knowledge, topic summary |
| `app/web/templates/brain_knowledge.html` | Create | Filterable knowledge node table |
| `app/web/templates/brain_review.html` | Create | Review queue for drafts |
| `app/web/templates/brain_sources.html` | Create | Content brain sources table |
| `app/web/templates/brain_topics.html` | Create | Topic profile cards |
| `app/web/templates/graph.html` | Modify | Update to work under brain namespace |
| `app/web/templates/home.html` | Modify | Remove topbar refs, verify sidebar compat |
| `app/static/js/control_room.js` | Modify | Add theme toggle logic |

All existing marketing templates (`activity.html`, `workflows.html`, `analytics.html`, `calendar.html`, `expansion.html`, `revenue.html`, `status.html`, and sub-pages) inherit from `base.html` via `{% extends "base.html" %}` and use `.card`, `.badge`, `.btn`, `.table` classes — these class names are preserved in the CSS rewrite so they automatically pick up the new design tokens without template changes.

---

### Task 1: CSS Design System Rewrite

**Files:**
- Rewrite: `app/static/css/control_room.css`

This is the foundation. Replace all custom properties with oklch tokens, add dark mode, replace `.topbar` with `.sidebar`, keep all existing component class names but restyle them.

- [ ] **Step 1: Back up existing CSS**

```bash
cp app/static/css/control_room.css app/static/css/control_room.css.bak
```

- [ ] **Step 2: Write new CSS — Design Tokens section**

Replace the `:root` block with oklch light-mode tokens. Add `.dark` class with dark-mode tokens. Add sidebar dimension variables.

```css
:root {
  --background: oklch(0.985 0 0);
  --foreground: oklch(0.145 0 0);
  --card: oklch(1 0 0);
  --card-foreground: oklch(0.145 0 0);
  --primary: oklch(0.205 0 0);
  --primary-foreground: oklch(0.985 0 0);
  --secondary: oklch(0.97 0 0);
  --muted: oklch(0.97 0 0);
  --muted-foreground: oklch(0.45 0 0);
  --accent: oklch(0.95 0 0);
  --accent-foreground: oklch(0.145 0 0);
  --border: oklch(0.9 0 0);
  --input: oklch(0.9 0 0);
  --ring: oklch(0.708 0 0);
  --destructive: oklch(0.704 0.191 22.216);
  --success: oklch(0.627 0.194 149.214);
  --warning: oklch(0.769 0.188 70.08);
  --info: oklch(0.6 0.118 184.714);
  --sidebar-w: 224px;
  --sidebar-w-collapsed: 64px;
  --sidebar-bg: oklch(0.97 0 0);
  --sidebar-fg: oklch(0.145 0 0);
  --sidebar-accent: oklch(0.92 0 0);
  --sidebar-border: oklch(0.9 0 0);
  --radius: 0.625rem;
  --radius-sm: calc(var(--radius) * 0.6);
  --radius-md: calc(var(--radius) * 0.8);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) * 1.4);
  --font: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
  --font-mono: "SFMono-Regular", "Menlo", "Monaco", monospace;
  /* Platform colors (unchanged) */
  --platform-linkedin: #2563eb;
  --platform-instagram: #e1306c;
  --platform-x: oklch(0.205 0 0);
  --platform-newsletter: oklch(0.627 0.194 149.214);
  /* Chart colors */
  --chart-1: oklch(0.646 0.222 41.116);
  --chart-2: oklch(0.6 0.118 184.714);
  --chart-3: oklch(0.398 0.07 227.392);
  --chart-4: oklch(0.828 0.189 84.429);
  --chart-5: oklch(0.769 0.188 70.08);
}

.dark {
  --background: oklch(0.145 0 0);
  --foreground: oklch(0.985 0 0);
  --card: oklch(0.205 0 0);
  --card-foreground: oklch(0.985 0 0);
  --primary: oklch(0.922 0 0);
  --primary-foreground: oklch(0.205 0 0);
  --secondary: oklch(0.269 0 0);
  --muted: oklch(0.269 0 0);
  --muted-foreground: oklch(0.708 0 0);
  --accent: oklch(0.269 0 0);
  --accent-foreground: oklch(0.985 0 0);
  --border: oklch(1 0 0 / 10%);
  --input: oklch(1 0 0 / 15%);
  --ring: oklch(0.556 0 0);
  --sidebar-bg: oklch(0.17 0 0);
  --sidebar-fg: oklch(0.985 0 0);
  --sidebar-accent: oklch(0.227 0 0);
  --sidebar-border: oklch(1 0 0 / 10%);
  --platform-x: oklch(0.985 0 0);
}
```

- [ ] **Step 3: Write new CSS — Reset, Base, Transitions, Scrollbar**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { font-family: var(--font); color-scheme: light; }
.dark { color-scheme: dark; }

body {
  font-family: var(--font);
  font-size: 14px;
  line-height: 1.5;
  color: var(--foreground);
  background: var(--background);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
  transition: background-color 200ms ease, color 200ms ease;
}

a { color: var(--foreground); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Thin scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: oklch(0.5 0 0 / 20%); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: oklch(0.5 0 0 / 40%); }
```

- [ ] **Step 4: Write new CSS — Sidebar**

Replace all `.topbar*` classes with `.sidebar*` classes:

```css
.app-layout { display: flex; min-height: 100vh; }

.sidebar {
  position: fixed;
  top: 0; left: 0; bottom: 0;
  width: var(--sidebar-w);
  background: var(--sidebar-bg);
  border-right: 1px solid var(--sidebar-border);
  display: flex;
  flex-direction: column;
  padding: 16px 12px;
  z-index: 100;
  transition: width 200ms ease;
  overflow: hidden;
}

.sidebar.collapsed { width: var(--sidebar-w-collapsed); }

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  margin-bottom: 8px;
}

.sidebar-brand-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--success);
  flex-shrink: 0;
}

.sidebar-brand-text {
  font-weight: 600;
  font-size: 14px;
  color: var(--sidebar-fg);
  white-space: nowrap;
}
.sidebar.collapsed .sidebar-brand-text { display: none; }

/* Toggle pill */
.mode-toggle {
  display: flex;
  background: var(--accent);
  border-radius: var(--radius-lg);
  padding: 3px;
  gap: 2px;
  margin: 0 4px 12px;
}

.mode-toggle-btn {
  flex: 1;
  text-align: center;
  padding: 6px 0;
  border-radius: calc(var(--radius-lg) - 2px);
  font-size: 12px;
  font-weight: 500;
  color: var(--muted-foreground);
  cursor: pointer;
  border: none;
  background: transparent;
  transition: background 150ms, color 150ms;
}

.mode-toggle-btn.active {
  background: var(--card);
  color: var(--foreground);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0,0,0,0.06);
}

.sidebar.collapsed .mode-toggle { display: none; }

/* Nav items */
.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.sidebar-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--muted-foreground);
  text-decoration: none;
  transition: background 150ms, color 150ms;
  white-space: nowrap;
}

.sidebar-link:hover {
  background: var(--sidebar-accent);
  color: var(--sidebar-fg);
  text-decoration: none;
}

.sidebar-link.active {
  background: var(--sidebar-accent);
  color: var(--sidebar-fg);
  font-weight: 600;
}

.sidebar-link svg, .sidebar-link img {
  width: 16px; height: 16px;
  flex-shrink: 0;
  color: currentColor;
}

.sidebar.collapsed .sidebar-link span { display: none; }

/* Sidebar footer */
.sidebar-footer {
  padding-top: 8px;
  border-top: 1px solid var(--sidebar-border);
}

/* Collapse toggle */
.sidebar-collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px; height: 28px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--sidebar-border);
  background: transparent;
  color: var(--muted-foreground);
  cursor: pointer;
  position: absolute;
  top: 16px;
  right: -14px;
  z-index: 101;
  transition: background 150ms;
}
.sidebar-collapse-btn:hover { background: var(--sidebar-accent); }
```

- [ ] **Step 5: Write new CSS — Main Content**

```css
.content {
  margin-left: var(--sidebar-w);
  padding: 24px 32px;
  min-height: 100vh;
  transition: margin-left 200ms ease;
}

.sidebar.collapsed ~ .content { margin-left: var(--sidebar-w-collapsed); }

.page-header { margin-bottom: 24px; }
.page-header h1 { font-size: 20px; font-weight: 600; color: var(--foreground); line-height: 1.3; }
.page-header p, .page-header .subtitle { font-size: 13px; color: var(--muted-foreground); margin-top: 2px; }
.eyebrow { font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted-foreground); font-weight: 600; }
.subtitle { font-size: 13px; color: var(--muted-foreground); }
.text-muted { color: var(--muted-foreground); }
.text-success { color: var(--success); }
.text-warning { color: var(--warning); }
.text-danger { color: var(--destructive); }

.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.section-header h2 { font-size: 15px; font-weight: 600; color: var(--foreground); }
.section-header .count { font-size: 12px; color: var(--muted-foreground); }
```

- [ ] **Step 6: Write new CSS — Cards**

Restyle `.card` to use new tokens (same class name, new look):

```css
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 16px;
  transition: background-color 200ms ease, border-color 200ms ease;
}

.card-sm { padding: 12px; }

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.card-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--foreground);
}
```

- [ ] **Step 7: Write new CSS — Badges**

Keep `.badge` class names, restyle:

```css
.badge {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 9999px;
  white-space: nowrap;
  line-height: 1;
}

.badge-success { background: oklch(0.627 0.194 149.214 / 15%); color: var(--success); }
.badge-warning { background: oklch(0.769 0.188 70.08 / 15%); color: var(--warning); }
.badge-danger  { background: oklch(0.704 0.191 22.216 / 15%); color: var(--destructive); }
.badge-info    { background: oklch(0.6 0.118 184.714 / 15%); color: var(--info); }
.badge-muted   { background: var(--muted); color: var(--muted-foreground); }
.badge-accent  { background: var(--accent); color: var(--accent-foreground); }

.platform-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 8px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 9999px;
}

.platform-badge.platform-linkedin { background: rgba(37,99,235,0.12); color: var(--platform-linkedin); }
.platform-badge.platform-instagram { background: rgba(225,48,108,0.12); color: var(--platform-instagram); }
.platform-badge.platform-x { background: var(--muted); color: var(--foreground); }
.platform-badge.platform-newsletter { background: oklch(0.627 0.194 149.214 / 12%); color: var(--platform-newsletter); }
```

- [ ] **Step 8: Write new CSS — Buttons**

Keep `.btn` class names:

```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--foreground);
  cursor: pointer;
  transition: background 150ms, color 150ms, border-color 150ms;
  white-space: nowrap;
}

.btn:hover { background: var(--accent); }
.btn:active { opacity: 0.9; }
.btn:disabled { opacity: 0.5; pointer-events: none; }
.btn:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px; }

.btn-primary { background: var(--primary); color: var(--primary-foreground); border-color: var(--primary); }
.btn-primary:hover { opacity: 0.9; }
.btn-success { background: var(--success); color: white; border-color: var(--success); }
.btn-success:hover { opacity: 0.9; }
.btn-danger { background: var(--destructive); color: white; border-color: var(--destructive); }
.btn-danger:hover { opacity: 0.9; }
.btn-ghost { background: transparent; border-color: transparent; color: var(--muted-foreground); }
.btn-ghost:hover { background: var(--accent); color: var(--foreground); }
.btn-sm { height: 28px; padding: 0 10px; font-size: 12px; }
.btn-lg { height: 36px; padding: 0 16px; font-size: 14px; }
```

- [ ] **Step 9: Write new CSS — Tables, Inputs, Forms**

```css
.table { width: 100%; border-collapse: collapse; }
.table th, .table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); font-size: 13px; }
.table th { font-weight: 600; color: var(--muted-foreground); font-size: 12px; }
.table tr:hover td { background: var(--muted); }

.input, .select {
  height: 32px;
  padding: 0 10px;
  font-size: 13px;
  border: 1px solid var(--input);
  border-radius: var(--radius-lg);
  background: var(--card);
  color: var(--foreground);
  transition: border-color 150ms;
  font-family: inherit;
}
.input:focus, .select:focus { border-color: var(--ring); outline: none; box-shadow: 0 0 0 3px oklch(0.708 0 0 / 20%); }
.input::placeholder { color: var(--muted-foreground); }

.textarea {
  min-height: 64px;
  padding: 8px 10px;
  font-size: 13px;
  border: 1px solid var(--input);
  border-radius: var(--radius-lg);
  background: var(--card);
  color: var(--foreground);
  font-family: inherit;
  resize: vertical;
}
```

- [ ] **Step 10: Write new CSS — Remaining component sections**

Port all remaining sections from the existing CSS (draft cards, activity timeline, workflow cards, metric grid, widget grid, analytics, empty state, drawer, calendar, revenue, expansion, etc.), replacing old color variable references:

| Old variable | New variable |
|---|---|
| `var(--bg)` | `var(--background)` |
| `var(--bg-card)` | `var(--card)` |
| `var(--bg-surface)` | `var(--muted)` |
| `var(--text)` | `var(--foreground)` |
| `var(--text-muted)` | `var(--muted-foreground)` |
| `var(--accent)` | `var(--primary)` (for emphasis) or `var(--accent)` (for hover bg) |
| `var(--accent-light)` | `var(--accent)` |
| `var(--danger)` | `var(--destructive)` |
| `var(--topbar-h)` | remove (no topbar) |
| `var(--bg-hover)` | `var(--accent)` |

Preserve all class names: `.draft-card`, `.draft-header`, `.draft-title`, `.draft-preview`, `.draft-meta`, `.draft-actions`, `.scheduled-card`, `.activity-*`, `.timeline-*`, `.workflow-*`, `.metric-*`, `.widget-*`, `.analytics-*`, `.gcal-*`, `.revenue-*`, `.rev-*`, `.module-*`, `.empty-state`, `.drawer`, `.auth-*`, `.code-block`, `.filter-*`, `.chip`, `.status-*`, `.emergency-*`, `.plat-nav-*`, etc.

Key changes per section:
- `.content` padding: `padding-top: calc(var(--topbar-h) + 24px)` → `margin-left: var(--sidebar-w); padding: 24px 32px`
- `.draft-card` border-left colors: keep platform vars
- `.timeline-dot` colors: use `var(--success)`, `var(--destructive)`, `var(--warning)`, `var(--info)`
- `.gcal-*` calendar classes: swap bg/text vars, keep structure
- `.drawer`: swap to new card/border vars

- [ ] **Step 11: Verify CSS loads without errors**

```bash
# Restart uvicorn (auto-reload should pick it up)
curl -s http://localhost:8000/control-room/ -o /dev/null -w "%{http_code}"
# Expected: 200
```

- [ ] **Step 12: Commit**

```bash
git add app/static/css/control_room.css app/static/css/control_room.css.bak
git commit -m "feat: rewrite CSS with agent-engine design system (oklch tokens, sidebar, dark mode)"
```

---

### Task 2: Base Template with Sidebar Layout

**Files:**
- Rewrite: `app/web/templates/base.html`
- Modify: `app/static/js/control_room.js`

- [ ] **Step 1: Rewrite base.html**

Replace the topbar layout with a sidebar layout. Use Alpine.js for sidebar collapse, mode toggle, and theme toggle. Use Lucide icons via CDN.

```html
<!DOCTYPE html>
<html lang="en" x-data="{ theme: localStorage.getItem('ntangible-theme') || 'light' }"
      x-init="if(theme==='dark') $el.classList.add('dark')"
      :class="{ 'dark': theme === 'dark' }">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NTangible</title>
  <link rel="stylesheet" href="/static/css/control_room.css">
  <script>
    /* Prevent flash of wrong theme */
    (function(){
      var t = localStorage.getItem('ntangible-theme');
      if (t === 'dark') document.documentElement.classList.add('dark');
    })();
  </script>
  <style>[x-cloak]{display:none!important;}</style>
  <script src="https://unpkg.com/htmx.org@2.0.4" defer></script>
  <script src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.8/dist/cdn.min.js" defer></script>
</head>
<body x-data="{
  drawerOpen: false,
  sidebarCollapsed: false,
  mode: (window.location.pathname.indexOf('/brain') !== -1) ? 'brain' : 'marketing'
}"
x-on:control-room:open-drawer.window="drawerOpen = true"
x-on:control-room:close-drawer.window="drawerOpen = false"
>

<div class="app-layout">
  <!-- Sidebar -->
  <nav class="sidebar" :class="{ collapsed: sidebarCollapsed }">
    <!-- Brand -->
    <div class="sidebar-brand">
      <div class="sidebar-brand-dot"></div>
      <span class="sidebar-brand-text">NTangible</span>
    </div>

    <!-- Mode toggle pill -->
    <div class="mode-toggle">
      <a href="/control-room/brain/"
         class="mode-toggle-btn"
         :class="{ active: mode === 'brain' }">Brain</a>
      <a href="/control-room/"
         class="mode-toggle-btn"
         :class="{ active: mode === 'marketing' }">Marketing</a>
    </div>

    <!-- Brain nav -->
    <div class="sidebar-nav" x-show="mode === 'brain'" x-cloak>
      <a href="/control-room/brain/" class="sidebar-link {% if page == 'brain_overview' %}active{% endif %}">
        <img src="https://unpkg.com/lucide-static@latest/icons/home.svg" alt="">
        <span>Overview</span>
      </a>
      <a href="/control-room/brain/graph" class="sidebar-link {% if page == 'brain_graph' %}active{% endif %}">
        <img src="https://unpkg.com/lucide-static@latest/icons/network.svg" alt="">
        <span>Graph</span>
      </a>
      <a href="/control-room/brain/knowledge" class="sidebar-link {% if page == 'brain_knowledge' %}active{% endif %}">
        <img src="https://unpkg.com/lucide-static@latest/icons/brain.svg" alt="">
        <span>Knowledge</span>
      </a>
      <a href="/control-room/brain/review" class="sidebar-link {% if page == 'brain_review' %}active{% endif %}">
        <img src="https://unpkg.com/lucide-static@latest/icons/check-circle-2.svg" alt="">
        <span>Review</span>
      </a>
      <a href="/control-room/brain/sources" class="sidebar-link {% if page == 'brain_sources' %}active{% endif %}">
        <img src="https://unpkg.com/lucide-static@latest/icons/database.svg" alt="">
        <span>Sources</span>
      </a>
      <a href="/control-room/brain/topics" class="sidebar-link {% if page == 'brain_topics' %}active{% endif %}">
        <img src="https://unpkg.com/lucide-static@latest/icons/layers.svg" alt="">
        <span>Topics</span>
      </a>
    </div>

    <!-- Marketing nav -->
    <div class="sidebar-nav" x-show="mode === 'marketing'">
      <a href="/control-room/" class="sidebar-link {% if page == 'dashboard' %}active{% endif %}">
        <img src="https://unpkg.com/lucide-static@latest/icons/layout-dashboard.svg" alt="">
        <span>Dashboard</span>
      </a>
      <a href="/control-room/activity" class="sidebar-link {% if page == 'activity' %}active{% endif %}">
        <img src="https://unpkg.com/lucide-static@latest/icons/activity.svg" alt="">
        <span>Activity</span>
      </a>
      <a href="/control-room/workflows" class="sidebar-link {% if page == 'workflows' %}active{% endif %}">
        <img src="https://unpkg.com/lucide-static@latest/icons/git-branch.svg" alt="">
        <span>Workflows</span>
      </a>
      <a href="/control-room/analytics" class="sidebar-link {% if page == 'analytics' %}active{% endif %}">
        <img src="https://unpkg.com/lucide-static@latest/icons/bar-chart-3.svg" alt="">
        <span>Analytics</span>
      </a>
      <a href="/control-room/calendar" class="sidebar-link {% if page == 'calendar' %}active{% endif %}">
        <img src="https://unpkg.com/lucide-static@latest/icons/calendar.svg" alt="">
        <span>Calendar</span>
      </a>
      <a href="/control-room/expansion" class="sidebar-link {% if page == 'expansion' %}active{% endif %}">
        <img src="https://unpkg.com/lucide-static@latest/icons/rocket.svg" alt="">
        <span>Expansion</span>
      </a>
      <a href="/control-room/revenue" class="sidebar-link {% if page == 'revenue' %}active{% endif %}">
        <img src="https://unpkg.com/lucide-static@latest/icons/dollar-sign.svg" alt="">
        <span>Revenue</span>
      </a>
      <a href="/control-room/status" class="sidebar-link {% if page == 'status' %}active{% endif %}">
        <img src="https://unpkg.com/lucide-static@latest/icons/signal.svg" alt="">
        <span>Status</span>
      </a>
    </div>

    <!-- Footer: theme toggle -->
    <div class="sidebar-footer">
      <button class="sidebar-link" style="width:100%;"
              @click="theme = theme === 'dark' ? 'light' : 'dark'; localStorage.setItem('ntangible-theme', theme)">
        <img x-show="theme === 'light'" src="https://unpkg.com/lucide-static@latest/icons/moon.svg" alt="">
        <img x-show="theme === 'dark'" src="https://unpkg.com/lucide-static@latest/icons/sun.svg" alt="">
        <span x-text="theme === 'dark' ? 'Light mode' : 'Dark mode'"></span>
      </button>
    </div>
  </nav>

  <!-- Main content -->
  <main class="content">
    {% block content %}{% endblock %}
  </main>
</div>

<!-- Drawer -->
<aside class="drawer" x-show="drawerOpen" x-cloak x-transition.opacity>
  <button class="drawer-close" @click="drawerOpen = false">&times;</button>
  <div id="drawer-content">
    {% block drawer %}{% endblock %}
  </div>
</aside>

<script src="/static/js/control_room.js"></script>
</body>
</html>
```

- [ ] **Step 2: Add icon color inversion for dark mode**

Lucide SVG icons loaded via `<img>` won't inherit `currentColor`. Add a CSS filter to invert them in dark mode:

```css
/* Add to control_room.css sidebar section */
.sidebar-link img {
  width: 16px; height: 16px;
  flex-shrink: 0;
  opacity: 0.6;
  transition: opacity 150ms, filter 200ms;
}
.sidebar-link:hover img, .sidebar-link.active img { opacity: 1; }
.dark .sidebar-link img { filter: invert(1); }
```

- [ ] **Step 3: Verify page loads with sidebar**

```bash
curl -s http://localhost:8000/control-room/ -o /dev/null -w "%{http_code}"
# Expected: 200
```

Open http://localhost:8000/control-room/ in Chrome and verify sidebar renders.

- [ ] **Step 4: Commit**

```bash
git add app/web/templates/base.html app/static/css/control_room.css
git commit -m "feat: replace topbar with sidebar layout + brain/marketing toggle"
```

---

### Task 3: Brain Routes

**Files:**
- Modify: `app/web/routes.py` (add routes near existing graph routes, ~line 3995)

- [ ] **Step 1: Add brain page routes**

Add these routes after the existing graph routes in `app/web/routes.py`:

```python
# ─── Brain Pages ─────────────────────────────────────────────────────

@web_router.get("/brain/", response_class=HTMLResponse)
def brain_overview(request: Request, db: Session = Depends(get_db)):
    bq = BrainQuery(db)
    entity_count = db.query(EntityNode).filter(EntityNode.primary_topic_key == "marketing").count()
    knowledge_count = db.query(KnowledgeNode).filter(KnowledgeNode.primary_topic_key == "marketing").count()
    edge_count = db.query(EntityEdge).count()
    source_count = db.query(KnowledgeNode).filter(KnowledgeNode.kind == "reference_content").count()
    recent = (
        db.query(KnowledgeNode)
        .filter(KnowledgeNode.primary_topic_key == "marketing")
        .order_by(KnowledgeNode.created_at.desc())
        .limit(8)
        .all()
    )
    topics = db.query(TopicProfile).all()
    return templates.TemplateResponse(request, "brain_overview.html", {
        "request": request,
        "page": "brain_overview",
        "entity_count": entity_count,
        "knowledge_count": knowledge_count,
        "edge_count": edge_count,
        "source_count": source_count,
        "recent": recent,
        "topics": topics,
    })


@web_router.get("/brain/graph", response_class=HTMLResponse)
def brain_graph(request: Request, db: Session = Depends(get_db)):
    data = BrainQuery(db).get_graph_data(topic_key="marketing")
    nodes = (
        [{"id": str(e.id), "label": e.canonical_name, "group": "entity", "type": e.entity_type} for e in data["entities"]]
        + [{"id": str(k.id), "label": k.title, "group": "knowledge", "type": k.kind} for k in data["knowledge"]]
    )
    links = (
        [{"source": str(e.source_id), "target": str(e.target_id), "relation": e.relation} for e in data["entity_edges"]]
        + [{"source": str(e.source_id), "target": str(e.target_id), "relation": e.relation} for e in data["knowledge_edges"]]
    )
    return templates.TemplateResponse(request, "graph.html", {
        "request": request,
        "page": "brain_graph",
        "nodes_json": json.dumps(nodes),
        "links_json": json.dumps(links),
    })


@web_router.get("/brain/knowledge", response_class=HTMLResponse)
def brain_knowledge(request: Request, db: Session = Depends(get_db), kind: str = "", status: str = ""):
    q = db.query(KnowledgeNode).filter(KnowledgeNode.primary_topic_key == "marketing")
    if kind:
        q = q.filter(KnowledgeNode.kind == kind)
    if status:
        q = q.filter(KnowledgeNode.status == status)
    nodes = q.order_by(KnowledgeNode.created_at.desc()).limit(100).all()
    kinds = [r[0] for r in db.query(KnowledgeNode.kind).distinct().all()]
    statuses = [r[0] for r in db.query(KnowledgeNode.status).distinct().all()]
    return templates.TemplateResponse(request, "brain_knowledge.html", {
        "request": request,
        "page": "brain_knowledge",
        "nodes": nodes,
        "kinds": sorted(kinds),
        "statuses": sorted(statuses),
        "selected_kind": kind,
        "selected_status": status,
    })


@web_router.get("/brain/review", response_class=HTMLResponse)
def brain_review(request: Request, db: Session = Depends(get_db)):
    drafts = BrainQuery(db).list_drafts_by_status("review_required")
    return templates.TemplateResponse(request, "brain_review.html", {
        "request": request,
        "page": "brain_review",
        "drafts": drafts,
    })


@web_router.get("/brain/sources", response_class=HTMLResponse)
def brain_sources(request: Request, db: Session = Depends(get_db)):
    sources = (
        db.query(KnowledgeNode)
        .filter(KnowledgeNode.kind == "reference_content")
        .order_by(KnowledgeNode.title.asc())
        .all()
    )
    return templates.TemplateResponse(request, "brain_sources.html", {
        "request": request,
        "page": "brain_sources",
        "sources": sources,
    })


@web_router.get("/brain/topics", response_class=HTMLResponse)
def brain_topics(request: Request, db: Session = Depends(get_db)):
    topics = db.query(TopicProfile).all()
    topic_stats = {}
    for t in topics:
        e_count = db.query(EntityNode).filter(EntityNode.primary_topic_key == t.topic_key).count()
        k_count = db.query(KnowledgeNode).filter(KnowledgeNode.primary_topic_key == t.topic_key).count()
        topic_stats[t.topic_key] = {"entities": e_count, "knowledge": k_count}
    return templates.TemplateResponse(request, "brain_topics.html", {
        "request": request,
        "page": "brain_topics",
        "topics": topics,
        "topic_stats": topic_stats,
    })
```

- [ ] **Step 2: Add required imports at top of routes.py**

Ensure these imports exist (some may already be present):

```python
from app.models.brain import EntityNode, KnowledgeNode, EntityEdge, TopicProfile
```

- [ ] **Step 3: Verify routes respond**

```bash
curl -s http://localhost:8000/control-room/brain/ -o /dev/null -w "%{http_code}"
# Expected: 500 (template not yet created) or 200
```

- [ ] **Step 4: Commit**

```bash
git add app/web/routes.py
git commit -m "feat: add brain page routes (overview, graph, knowledge, review, sources, topics)"
```

---

### Task 4: Brain Templates

**Files:**
- Create: `app/web/templates/brain_overview.html`
- Create: `app/web/templates/brain_knowledge.html`
- Create: `app/web/templates/brain_review.html`
- Create: `app/web/templates/brain_sources.html`
- Create: `app/web/templates/brain_topics.html`
- Modify: `app/web/templates/graph.html` (update `page` variable usage)

- [ ] **Step 1: Create brain_overview.html**

```html
{% extends "base.html" %}
{% block content %}
<header class="page-header">
  <h1>Brain Overview</h1>
  <p class="subtitle">Knowledge graph system — entities, knowledge, and relationships.</p>
</header>

<div class="stat-grid">
  <div class="card stat-card">
    <div class="stat-icon stat-icon-blue">
      <img src="https://unpkg.com/lucide-static@latest/icons/network.svg" alt="">
    </div>
    <div>
      <div class="stat-value">{{ entity_count }}</div>
      <div class="stat-label">Entities</div>
    </div>
  </div>
  <div class="card stat-card">
    <div class="stat-icon stat-icon-emerald">
      <img src="https://unpkg.com/lucide-static@latest/icons/brain.svg" alt="">
    </div>
    <div>
      <div class="stat-value">{{ knowledge_count }}</div>
      <div class="stat-label">Knowledge</div>
    </div>
  </div>
  <div class="card stat-card">
    <div class="stat-icon stat-icon-violet">
      <img src="https://unpkg.com/lucide-static@latest/icons/git-branch.svg" alt="">
    </div>
    <div>
      <div class="stat-value">{{ edge_count }}</div>
      <div class="stat-label">Edges</div>
    </div>
  </div>
  <div class="card stat-card">
    <div class="stat-icon stat-icon-amber">
      <img src="https://unpkg.com/lucide-static@latest/icons/database.svg" alt="">
    </div>
    <div>
      <div class="stat-value">{{ source_count }}</div>
      <div class="stat-label">Sources</div>
    </div>
  </div>
</div>

<div class="section-header" style="margin-top: 24px;">
  <h2>Recent Knowledge</h2>
</div>

<div class="knowledge-list">
  {% for node in recent %}
  <div class="card" style="margin-bottom: 8px; padding: 12px;">
    <div style="display: flex; align-items: center; justify-content: space-between;">
      <div>
        <div style="font-weight: 500; font-size: 13px; color: var(--foreground);">{{ node.title }}</div>
        <div style="font-size: 12px; color: var(--muted-foreground); margin-top: 2px;">{{ node.kind }}</div>
      </div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <span class="badge {% if node.status == 'active' %}badge-success{% elif node.status == 'review_required' %}badge-warning{% elif node.status == 'published' %}badge-success{% elif node.status == 'scheduled' %}badge-info{% else %}badge-muted{% endif %}">
          {{ node.status }}
        </span>
        <span style="font-size: 11px; color: var(--muted-foreground);">{{ "%.0f"|format(node.confidence * 100) }}%</span>
      </div>
    </div>
  </div>
  {% endfor %}
</div>

{% if topics %}
<div class="section-header" style="margin-top: 24px;">
  <h2>Topics</h2>
</div>
<div class="stat-grid">
  {% for topic in topics %}
  <div class="card" style="padding: 14px;">
    <div style="font-weight: 600; font-size: 14px; color: var(--foreground);">{{ topic.display_name }}</div>
    <div style="font-size: 12px; color: var(--muted-foreground); margin-top: 2px;">{{ topic.description or topic.topic_key }}</div>
    <div style="display: flex; gap: 8px; margin-top: 8px;">
      <span class="badge badge-muted">{{ topic.priority }}</span>
      {% if topic.context_enabled %}<span class="badge badge-info">context</span>{% endif %}
      {% if topic.intelligence_enabled %}<span class="badge badge-success">intelligence</span>{% endif %}
      {% if topic.memory_enabled %}<span class="badge badge-accent">memory</span>{% endif %}
    </div>
  </div>
  {% endfor %}
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 2: Create brain_knowledge.html**

```html
{% extends "base.html" %}
{% block content %}
<header class="page-header">
  <h1>Knowledge</h1>
  <p class="subtitle">Browse and filter knowledge nodes.</p>
</header>

<form class="filter-bar" method="get" action="/control-room/brain/knowledge" style="display:flex; gap:8px; margin-bottom:16px;">
  <select name="kind" class="select" onchange="this.form.submit()">
    <option value="">All kinds</option>
    {% for k in kinds %}
    <option value="{{ k }}" {% if selected_kind == k %}selected{% endif %}>{{ k }}</option>
    {% endfor %}
  </select>
  <select name="status" class="select" onchange="this.form.submit()">
    <option value="">All statuses</option>
    {% for s in statuses %}
    <option value="{{ s }}" {% if selected_status == s %}selected{% endif %}>{{ s }}</option>
    {% endfor %}
  </select>
</form>

{% if nodes %}
<div class="card" style="padding: 0; overflow: hidden;">
  <table class="table">
    <thead>
      <tr>
        <th>Title</th>
        <th>Kind</th>
        <th>Status</th>
        <th>Confidence</th>
        <th>Created</th>
      </tr>
    </thead>
    <tbody>
      {% for node in nodes %}
      <tr>
        <td style="font-weight: 500;">{{ node.title[:60] }}{% if node.title|length > 60 %}...{% endif %}</td>
        <td><span class="badge badge-muted">{{ node.kind }}</span></td>
        <td>
          <span class="badge {% if node.status == 'active' or node.status == 'published' %}badge-success{% elif node.status == 'review_required' %}badge-warning{% elif node.status == 'scheduled' %}badge-info{% elif node.status == 'rejected' %}badge-danger{% else %}badge-muted{% endif %}">
            {{ node.status }}
          </span>
        </td>
        <td>
          <span style="color: {% if node.confidence >= 0.8 %}var(--success){% elif node.confidence >= 0.5 %}var(--warning){% else %}var(--destructive){% endif %}">
            {{ "%.0f"|format(node.confidence * 100) }}%
          </span>
        </td>
        <td style="color: var(--muted-foreground); font-size: 12px;">{{ node.created_at.strftime('%b %d, %H:%M') }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% else %}
<div class="empty-state">
  <div class="empty-state-title">No knowledge nodes found</div>
  <div class="empty-state-desc">Try adjusting your filters.</div>
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Create brain_review.html**

```html
{% extends "base.html" %}
{% block content %}
<header class="page-header">
  <h1>Review Queue</h1>
  <p class="subtitle">Drafts awaiting review.</p>
</header>

{% if drafts %}
<div class="draft-list">
  {% for draft in drafts %}
  <div class="card" style="margin-bottom: 10px; padding: 14px;">
    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
      <div style="flex: 1;">
        <div style="font-weight: 600; font-size: 14px; color: var(--foreground);">{{ draft.title }}</div>
        <div style="display: flex; gap: 6px; margin-top: 6px;">
          {% if draft.metadata_.get('platform') %}
          <span class="platform-badge platform-{{ draft.metadata_.platform }}">{{ draft.metadata_.platform }}</span>
          {% endif %}
          {% if draft.metadata_.get('pillar') %}
          <span class="badge badge-muted">{{ draft.metadata_.pillar }}</span>
          {% endif %}
          {% if draft.metadata_.get('mode') %}
          <span class="badge badge-accent">{{ draft.metadata_.mode }}</span>
          {% endif %}
        </div>
        {% if draft.content %}
        <div style="margin-top: 8px; font-size: 13px; color: var(--muted-foreground); line-height: 1.5; max-height: 60px; overflow: hidden;">
          {{ draft.content[:200] }}{% if draft.content|length > 200 %}...{% endif %}
        </div>
        {% endif %}
      </div>
      <div style="display: flex; gap: 6px; margin-left: 16px; flex-shrink: 0;">
        <button class="btn btn-success btn-sm">Approve</button>
        <button class="btn btn-sm">Schedule</button>
        <button class="btn btn-danger btn-sm">Reject</button>
      </div>
    </div>
  </div>
  {% endfor %}
</div>
{% else %}
<div class="empty-state">
  <div class="empty-state-title">Review queue is clear</div>
  <div class="empty-state-desc">No drafts need review right now.</div>
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Create brain_sources.html**

```html
{% extends "base.html" %}
{% block content %}
<header class="page-header">
  <h1>Sources</h1>
  <p class="subtitle">Content brain ingestion sources.</p>
</header>

{% if sources %}
<div class="card" style="padding: 0; overflow: hidden;">
  <table class="table">
    <thead>
      <tr>
        <th>Name</th>
        <th>Kind</th>
        <th>URL</th>
      </tr>
    </thead>
    <tbody>
      {% for src in sources %}
      <tr>
        <td style="font-weight: 500;">{{ src.title }}</td>
        <td><span class="badge badge-muted">{{ src.metadata_.get('source_kind', '-') }}</span></td>
        <td style="font-size: 12px; color: var(--muted-foreground);">
          {% if src.metadata_.get('url') %}
          <a href="{{ src.metadata_.url }}" target="_blank" style="color: var(--info);">{{ src.metadata_.url[:50] }}{% if src.metadata_.url|length > 50 %}...{% endif %}</a>
          {% else %}-{% endif %}
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% else %}
<div class="empty-state">
  <div class="empty-state-title">No sources configured</div>
  <div class="empty-state-desc">Add content sources to the brain.</div>
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 5: Create brain_topics.html**

```html
{% extends "base.html" %}
{% block content %}
<header class="page-header">
  <h1>Topics</h1>
  <p class="subtitle">Topic profiles and their knowledge coverage.</p>
</header>

<div class="stat-grid">
  {% for topic in topics %}
  <div class="card" style="padding: 16px;">
    <div style="font-weight: 600; font-size: 16px; color: var(--foreground);">{{ topic.display_name }}</div>
    <div style="font-size: 13px; color: var(--muted-foreground); margin-top: 4px;">{{ topic.description or '' }}</div>

    <div style="display: flex; gap: 16px; margin-top: 14px;">
      <div>
        <div style="font-size: 20px; font-weight: 600; color: var(--foreground);">{{ topic_stats[topic.topic_key].entities }}</div>
        <div style="font-size: 11px; color: var(--muted-foreground);">Entities</div>
      </div>
      <div>
        <div style="font-size: 20px; font-weight: 600; color: var(--foreground);">{{ topic_stats[topic.topic_key].knowledge }}</div>
        <div style="font-size: 11px; color: var(--muted-foreground);">Knowledge</div>
      </div>
    </div>

    <div style="display: flex; gap: 6px; margin-top: 12px;">
      <span class="badge {% if topic.context_enabled %}badge-info{% else %}badge-muted{% endif %}">context</span>
      <span class="badge {% if topic.intelligence_enabled %}badge-success{% else %}badge-muted{% endif %}">intelligence</span>
      <span class="badge {% if topic.memory_enabled %}badge-accent{% else %}badge-muted{% endif %}">memory</span>
    </div>
  </div>
  {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 6: Update graph.html page variable**

The graph template already works. Just ensure it passes `page: "brain_graph"` in the route (already done in Task 3). No template changes needed — the `{% if page == 'brain_graph' %}active{% endif %}` in base.html handles highlighting.

- [ ] **Step 7: Add stat-grid and stat-card CSS**

Add to `control_room.css`:

```css
/* Stat grid (brain overview) */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
}

.stat-icon {
  width: 40px; height: 40px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-icon img { width: 20px; height: 20px; }

.stat-icon-blue    { background: oklch(0.6 0.118 184.714 / 15%); }
.stat-icon-emerald { background: oklch(0.627 0.194 149.214 / 15%); }
.stat-icon-violet  { background: oklch(0.541 0.281 293.009 / 15%); }
.stat-icon-amber   { background: oklch(0.769 0.188 70.08 / 15%); }

.dark .stat-icon img { filter: invert(1); }

.stat-value { font-size: 22px; font-weight: 700; color: var(--foreground); font-variant-numeric: tabular-nums; }
.stat-label { font-size: 12px; color: var(--muted-foreground); }
```

- [ ] **Step 8: Verify all brain pages load**

```bash
for path in brain/ brain/graph brain/knowledge brain/review brain/sources brain/topics; do
  echo -n "$path: "
  curl -s http://localhost:8000/control-room/$path -o /dev/null -w "%{http_code}\n"
done
# Expected: all 200
```

- [ ] **Step 9: Commit**

```bash
git add app/web/templates/brain_*.html app/web/templates/graph.html app/web/routes.py app/static/css/control_room.css
git commit -m "feat: add brain pages (overview, knowledge, review, sources, topics)"
```

---

### Task 5: Visual Verification & Polish

**Files:**
- May touch: `app/static/css/control_room.css`, various templates

- [ ] **Step 1: Open marketing dashboard in Chrome, verify sidebar renders**

Navigate to http://localhost:8000/control-room/ — verify:
- Sidebar shows on the left with "NTangible" brand + green dot
- "Marketing" pill is active
- Marketing nav items visible with Lucide icons
- Dashboard content renders to the right of the sidebar
- Cards, badges, buttons use new design tokens

- [ ] **Step 2: Test dark mode toggle**

Click the theme toggle in sidebar footer:
- Page should switch to dark mode
- Cards get dark background
- Text inverts to light
- Sidebar darkens
- Refresh page — dark mode should persist (localStorage)

- [ ] **Step 3: Test Brain mode**

Click "Brain" in the toggle pill:
- Should navigate to /control-room/brain/
- Brain nav items appear (Overview, Graph, Knowledge, Review, Sources, Topics)
- Overview shows stat cards with counts
- Click through each brain page to verify rendering

- [ ] **Step 4: Test marketing pages still work**

Click "Marketing" pill, then visit each page:
- Dashboard, Activity, Workflows, Analytics, Calendar, Expansion, Revenue, Status
- Verify htmx interactions still work (draft approve/reject on dashboard, analytics refresh)
- Verify Alpine.js still works (calendar wizard, workflow wizard)

- [ ] **Step 5: Fix any visual issues found**

Common fixes:
- Adjust padding/margin if content overlaps sidebar
- Fix icon visibility in dark mode
- Adjust badge contrast
- Fix any hardcoded colors that didn't get token-ized

- [ ] **Step 6: Final commit**

```bash
git add -u
git commit -m "fix: polish sidebar layout and dark mode across all pages"
```
