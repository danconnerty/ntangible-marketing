from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class SourceTarget:
    slug: str
    display_name: str
    url: str
    parser: str
    platform: str
    source_kind: str
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedAsset:
    asset_type: str
    url: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedMetricSnapshot:
    observed_at: datetime
    payload: dict[str, Any]
    source_url: str | None = None


@dataclass(slots=True)
class ParsedContentItem:
    canonical_key: str
    platform: str
    item_type: str
    url: str
    title: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    body_text: str | None = None
    summary: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    assets: list[ParsedAsset] = field(default_factory=list)
    metrics: list[ParsedMetricSnapshot] = field(default_factory=list)
