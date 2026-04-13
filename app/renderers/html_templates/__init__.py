"""Registry of HTML templates used by :class:`HtmlRenderer` and the Studio.

Each family entry maps to:

* ``template_file`` — a Jinja2 HTML file in this directory
* ``fixture_file`` — a JSON sample payload used for design previews and tests
* ``default_size`` — ``(width, height)`` the template is designed for
* ``description`` — one-line human description shown in the Studio

Adding a new family is a three-step process:

1. Drop ``<family>.html`` next to this file.
2. Drop ``<family>.fixture.json`` next to this file.
3. Add an entry to :data:`FAMILIES` below with the fields above.

No other code changes are needed — the Studio tab auto-lists every entry,
and :class:`HtmlRenderer` dispatches on ``template_family``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


TEMPLATE_DIR = Path(__file__).parent


FAMILIES: dict[str, dict[str, Any]] = {
    "event_leaderboard": {
        "template_file": "event_leaderboard.html",
        "fixture_file": "event_leaderboard.fixture.json",
        "default_size": (1080, 1080),
        "description": "Top 5 athletes ranked by CF score for an event.",
    },
}


def list_families() -> list[str]:
    return list(FAMILIES.keys())


def get_family_config(family: str) -> dict[str, Any] | None:
    return FAMILIES.get(family)


def load_fixture(family: str) -> dict[str, Any]:
    cfg = FAMILIES.get(family)
    if cfg is None:
        raise KeyError(f"Unknown template family: {family}")
    path = TEMPLATE_DIR / cfg["fixture_file"]
    return json.loads(path.read_text())
