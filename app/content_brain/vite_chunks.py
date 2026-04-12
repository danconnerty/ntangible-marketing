from __future__ import annotations

import re
from urllib.parse import urljoin

from app.content_brain.types import SourceTarget


def _slugify_chunk_name(filename: str) -> str:
    base = filename.rsplit("/", 1)[-1]
    base = base.rsplit(".", 1)[0]
    name = re.sub(r"-[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)?$", "", base)
    slug = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()
    return f"ntangible_chunk_{slug}"


def extract_lazy_chunk_targets(bundle_text: str, *, base_url: str) -> list[SourceTarget]:
    filenames = sorted(set(re.findall(r'import\("\./([^"]+\.js)"\)', bundle_text)))
    return [
        SourceTarget(
            slug=_slugify_chunk_name(filename),
            display_name=f"NTangible Chunk {filename.rsplit('/', 1)[-1].rsplit('.', 1)[0]}",
            url=urljoin(f"{base_url.rstrip('/')}/assets/", filename),
            parser="js_text_chunk",
            platform="web",
            source_kind="website",
            notes="Auto-discovered lazy route chunk from the main Vite bundle.",
        )
        for filename in filenames
    ]
