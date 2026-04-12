from pathlib import Path

import yaml

from app.content_brain.types import SourceTarget


SOURCE_FILE = Path(__file__).resolve().parent.parent / "config_data" / "content_brain" / "public_sources.yaml"


def load_seed_targets() -> list[SourceTarget]:
    with SOURCE_FILE.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    return [SourceTarget(**entry) for entry in payload.get("sources", [])]
