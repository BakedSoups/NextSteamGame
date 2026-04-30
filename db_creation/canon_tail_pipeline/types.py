from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TailRow:
    context: str
    representative_tag: str
    total_occurrences: int
    members: list[str]
