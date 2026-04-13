"""Pillow-based image template implementations.

Each template is a pure function taking (text_fields, structured_data, size,
palette) and returning a :class:`PIL.Image.Image`. The ``FAMILY_RENDERERS``
registry maps ``template_family`` names to these functions so that
``PillowRenderer`` can dispatch without hard-coding imports.
"""

from app.renderers.pillow_templates.event_leaderboard import render_event_leaderboard


FAMILY_RENDERERS = {
    "event_leaderboard": render_event_leaderboard,
}

__all__ = ["FAMILY_RENDERERS", "render_event_leaderboard"]
