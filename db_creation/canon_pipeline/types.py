from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class CanonGroup:
    context: str
    representative_tag: str
    parent_tag: str
    specificity_level: int
    counts: Dict[str, int] = field(default_factory=dict)
    raw_counts: Dict[str, int] = field(default_factory=dict)

    @property
    def member_count(self) -> int:
        return len(self.counts)

    @property
    def total_occurrences(self) -> int:
        return sum(self.counts.values())


@dataclass
class LeftoverRow:
    context: str
    representative_tag: str
    total_occurrences: int
    members: list[str]
