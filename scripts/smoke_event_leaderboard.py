"""Phase 1 smoke test: render a Top 5 event leaderboard to a local PNG.

Usage:
    python3 scripts/smoke_event_leaderboard.py

Reads ``tests/phase1/fixtures/top5_leaderboard.json`` and writes the rendered
PNG using the template function directly (no app config / database needed).
Prints the output path so it can be opened for a visual review.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.renderers.pillow_templates.event_leaderboard import (  # noqa: E402
    render_event_leaderboard,
)


PALETTE = {
    "background": "#0B1220",
    "surface": "#111A2E",
    "primary_text": "#F5F7FA",
    "secondary_text": "#9AA3B2",
    "accent": "#F4B72E",
    "rule": "#1E2A44",
    "wordmark": "#F5F7FA",
}

FIXTURE = REPO_ROOT / "tests" / "phase1" / "fixtures" / "top5_leaderboard.json"
OUTPUT_DIR = REPO_ROOT / "storage" / "generated_assets"


def main() -> int:
    if not FIXTURE.exists():
        print(f"Fixture missing: {FIXTURE}", file=sys.stderr)
        return 1

    data = json.loads(FIXTURE.read_text())
    image = render_event_leaderboard(
        text_fields={"event_name": data["event_name"], "date": data["date"]},
        structured_data={"top_athletes": data["top_athletes"]},
        size=(1080, 1080),
        palette=PALETTE,
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "smoke_event_leaderboard.png"
    image.save(out_path, format="PNG", optimize=True)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
