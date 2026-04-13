"""Shared layout utilities for Pillow templates.

Only what's needed for Phase 1: font loading with a graceful fallback to
bundled system fonts, an autoshrink helper so long text never overflows its
box, and hex-to-RGB conversion.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

# System fonts always present on the Debian/Ubuntu base images we run on.
# These are used as Phase 1 defaults until branded TTFs are dropped into
# ``app/assets/fonts/``.
_FALLBACK_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
_FALLBACK_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

_BRAND_FONT_DIR = Path(__file__).resolve().parents[3] / "app" / "assets" / "fonts"


def _first_existing(paths: list[str]) -> str:
    for candidate in paths:
        if Path(candidate).is_file():
            return candidate
    raise FileNotFoundError(
        "No fallback font found. Install fonts-dejavu or fonts-liberation, "
        "or drop a brand TTF into app/assets/fonts/."
    )


@lru_cache(maxsize=32)
def _resolve_font_path(weight: str) -> str:
    """Resolve a font path by weight. Prefers brand font dir if populated."""
    if _BRAND_FONT_DIR.is_dir():
        for ttf in sorted(_BRAND_FONT_DIR.glob("*.ttf")):
            name = ttf.name.lower()
            if weight == "bold" and "bold" in name:
                return str(ttf)
            if weight == "regular" and "bold" not in name:
                return str(ttf)
    if weight == "bold":
        return _first_existing(_FALLBACK_BOLD)
    return _first_existing(_FALLBACK_REGULAR)


@lru_cache(maxsize=256)
def load_font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_resolve_font_path(weight), size=size)


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))


def fit_text_to_width(
    text: str,
    max_width: int,
    start_size: int,
    weight: str = "bold",
    min_size: int = 20,
) -> ImageFont.FreeTypeFont:
    """Return the largest font (<= start_size, >= min_size) that fits ``text``.

    Used so long athlete names don't overflow their column without needing
    manual per-row tuning in every template.
    """
    for size in range(start_size, min_size - 1, -2):
        font = load_font(size, weight)
        if font.getlength(text) <= max_width:
            return font
    return load_font(min_size, weight)
