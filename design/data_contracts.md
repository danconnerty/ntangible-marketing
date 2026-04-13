# Template Data Contracts

Every HTML template in `app/renderers/html_templates/` receives a fixed set of
Jinja2 variables when rendered. **Use only these names when designing** — any
other variable will be undefined at render time and blow up silently.

## Global variables (every template gets these)

| Name | Type | Source |
|---|---|---|
| `palette.background` | string (hex) | `app/config_data/brand_palette.yaml` |
| `palette.surface` | string (hex) | same |
| `palette.primary_text` | string (hex) | same |
| `palette.secondary_text` | string (hex) | same |
| `palette.accent` | string (hex) | same |
| `palette.rule` | string (hex) | same |
| `palette.wordmark` | string (hex) | same |
| `width` | int | Template's default size (pixels) |
| `height` | int | Template's default size (pixels) |

Recommended CSS pattern:

```css
:root {
  --background: {{ palette.background }};
  --accent: {{ palette.accent }};
  /* ... */
}
html, body {
  width: {{ width }}px;
  height: {{ height }}px;
}
```

## Family-specific variables

### `event_leaderboard`

Top 5 athletes ranked by CF score for an event.

- **Default size:** 1080 × 1080 (Instagram feed square)
- **Template:** `app/renderers/html_templates/event_leaderboard.html`
- **Fixture:** `app/renderers/html_templates/event_leaderboard.fixture.json`

| Variable | Type | Description |
|---|---|---|
| `event_name` | string | Event title (e.g. "Spring Clutch Showcase") |
| `date` | string | Human-readable date (e.g. "Apr 13, 2026") |
| `top_athletes` | list of 5 dicts | Ranked athletes — exactly five entries |

Each entry in `top_athletes`:

| Field | Type | Description |
|---|---|---|
| `rank` | int | 1 through 5 |
| `name` | string | Full athlete name |
| `cf_score` | float | Clutch Factor score, 0–100 (render with one decimal) |

## Adding a new family

1. Create `app/renderers/html_templates/<family>.html` — your template, using
   only the variables documented above (or the new ones you define for it).
2. Create `app/renderers/html_templates/<family>.fixture.json` — sample data
   the Studio will render your template against.
3. Add an entry to `FAMILIES` in `app/renderers/html_templates/__init__.py`
   with `template_file`, `fixture_file`, `default_size`, and `description`.
4. Add a new section in this file documenting the data contract.
5. Reload `/control-room/studio` in the browser — your new family shows up.

No Python code changes needed beyond the registry entry.
