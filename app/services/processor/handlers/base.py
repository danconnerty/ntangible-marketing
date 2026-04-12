from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class HandlerResult:
    handler_name: str
    success: bool
    detail: dict = field(default_factory=dict)
    error: str | None = None
