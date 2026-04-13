"""Event leaderboard template.

Renders a Top 5 ranked leaderboard for an event at 1080x1080 (Instagram feed
square). Each row shows Rank, Name, and CF Score. Phase 1 scope is fixed at
exactly 5 entries.

Expected inputs
---------------
text_fields:
    event_name: str — e.g. "Spring Clutch Showcase"
    date:       str — e.g. "Apr 13, 2026"
structured_data:
    top_athletes: list[dict] — exactly 5 entries with keys:
        rank:     int
        name:     str
        cf_score: float | int | str
"""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw

from app.renderers.pillow_templates._layout import (
    fit_text_to_width,
    hex_to_rgb,
    load_font,
)


ENTRY_COUNT = 5


def _require_entries(structured_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    data = structured_data or {}
    athletes = data.get("top_athletes") or []
    if len(athletes) != ENTRY_COUNT:
        raise ValueError(
            f"event_leaderboard expects exactly {ENTRY_COUNT} entries in "
            f"structured_data['top_athletes']; got {len(athletes)}."
        )
    return athletes


def render_event_leaderboard(
    text_fields: dict[str, str],
    structured_data: dict[str, Any] | None,
    size: tuple[int, int],
    palette: dict[str, str],
) -> Image.Image:
    width, height = size
    athletes = _require_entries(structured_data)
    event_name = text_fields.get("event_name", "Event")
    date = text_fields.get("date", "")

    bg = hex_to_rgb(palette["background"])
    surface = hex_to_rgb(palette.get("surface", palette["background"]))
    primary = hex_to_rgb(palette["primary_text"])
    secondary = hex_to_rgb(palette["secondary_text"])
    accent = hex_to_rgb(palette["accent"])
    rule = hex_to_rgb(palette.get("rule", palette["secondary_text"]))
    wordmark = hex_to_rgb(palette.get("wordmark", palette["primary_text"]))

    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)

    # Layout metrics (proportional so the same template scales to other sizes later).
    margin_x = int(width * 0.08)
    header_y = int(height * 0.07)

    # ---- Header: eyebrow label ----
    eyebrow_font = load_font(32, weight="regular")
    eyebrow = "LEADERBOARD  ·  TOP 5"
    draw.text((margin_x, header_y), eyebrow, font=eyebrow_font, fill=secondary)

    # ---- Header: event name (autoshrink so long names stay on one line) ----
    event_font = fit_text_to_width(
        event_name.upper(),
        max_width=width - 2 * margin_x,
        start_size=76,
        weight="bold",
        min_size=44,
    )
    event_y = header_y + 48
    draw.text((margin_x, event_y), event_name.upper(), font=event_font, fill=primary)

    # ---- Header: date ----
    if date:
        date_font = load_font(30, weight="regular")
        date_y = event_y + event_font.size + 12
        draw.text((margin_x, date_y), date, font=date_font, fill=accent)

    # ---- Divider rule under header ----
    rule_y = int(height * 0.28)
    draw.line(
        [(margin_x, rule_y), (width - margin_x, rule_y)],
        fill=rule,
        width=3,
    )

    # ---- Body: 5 ranked rows ----
    body_top = rule_y + int(height * 0.035)
    body_bottom = int(height * 0.90)
    row_gap = int(height * 0.012)
    available = body_bottom - body_top - row_gap * (ENTRY_COUNT - 1)
    row_height = available // ENTRY_COUNT

    rank_col_x = margin_x
    rank_col_w = int(width * 0.14)
    name_col_x = rank_col_x + rank_col_w + int(width * 0.01)
    score_col_right = width - margin_x
    score_col_w = int(width * 0.22)
    name_col_w = score_col_right - score_col_w - name_col_x - 20

    rank_font_size = int(row_height * 0.62)
    score_font_size = int(row_height * 0.48)
    name_font_size = int(row_height * 0.42)

    for index, entry in enumerate(athletes):
        row_y = body_top + index * (row_height + row_gap)
        row_center_y = row_y + row_height // 2

        # Row background card
        draw.rounded_rectangle(
            [(margin_x - 8, row_y), (width - margin_x + 8, row_y + row_height)],
            radius=18,
            fill=surface,
        )

        # Rank numeral
        rank_font = load_font(rank_font_size, weight="bold")
        rank_text = str(entry.get("rank", index + 1))
        rank_bbox = draw.textbbox((0, 0), rank_text, font=rank_font)
        rank_h = rank_bbox[3] - rank_bbox[1]
        draw.text(
            (rank_col_x + 12, row_center_y - rank_h // 2 - 6),
            rank_text,
            font=rank_font,
            fill=accent,
        )

        # Name (autoshrink to column width)
        name = str(entry.get("name", "")).strip()
        name_font = fit_text_to_width(
            name,
            max_width=name_col_w,
            start_size=name_font_size,
            weight="bold",
            min_size=28,
        )
        name_bbox = draw.textbbox((0, 0), name, font=name_font)
        name_h = name_bbox[3] - name_bbox[1]
        draw.text(
            (name_col_x, row_center_y - name_h // 2 - 4),
            name,
            font=name_font,
            fill=primary,
        )

        # CF Score (right-aligned, accent color)
        score_raw = entry.get("cf_score", "")
        if isinstance(score_raw, (int, float)):
            score_text = f"{float(score_raw):.1f}"
        else:
            score_text = str(score_raw)
        score_font = load_font(score_font_size, weight="bold")
        score_bbox = draw.textbbox((0, 0), score_text, font=score_font)
        score_w = score_bbox[2] - score_bbox[0]
        score_h = score_bbox[3] - score_bbox[1]
        draw.text(
            (score_col_right - score_w, row_center_y - score_h // 2 - 4),
            score_text,
            font=score_font,
            fill=accent,
        )

    # ---- Footer: wordmark ----
    footer_font = load_font(28, weight="bold")
    footer_text = "NTANGIBLE  ·  CLUTCH FACTOR"
    footer_bbox = draw.textbbox((0, 0), footer_text, font=footer_font)
    footer_w = footer_bbox[2] - footer_bbox[0]
    footer_y = int(height * 0.945)
    draw.text(
        ((width - footer_w) // 2, footer_y),
        footer_text,
        font=footer_font,
        fill=wordmark,
    )

    return image
