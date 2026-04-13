"""Local filesystem asset storage for generated images.

Phase 1 writes PNGs to a local directory and returns a ``file://`` URL. The
interface is intentionally minimal so that Phase 4 can replace the body of
``save_png`` with an S3 upload (returning a public HTTPS URL) without touching
any caller.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    from PIL.Image import Image


def _asset_root() -> Path:
    root = Path(get_settings().generated_asset_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_png(image: "Image", prefix: str = "") -> tuple[str, str]:
    """Persist a Pillow image to disk and return (storage_path, url).

    ``storage_path`` is the absolute local path. ``url`` is a ``file://`` URL
    suitable for local development and test assertions; Phase 4 will swap this
    for a remote HTTPS URL.
    """
    root = _asset_root()
    filename = f"{prefix + '_' if prefix else ''}{uuid.uuid4().hex}.png"
    path = root / filename
    image.save(path, format="PNG", optimize=True)
    absolute = str(path.resolve())
    return absolute, f"file://{absolute}"
