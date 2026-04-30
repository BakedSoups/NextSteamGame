from __future__ import annotations

from collections import Counter
from typing import Dict

from .layer_1_normalization import normalize_tag


def collapse_exact_normalized(counter: Counter) -> tuple[Counter, Dict[str, Counter]]:
    collapsed = Counter()
    raw_members: Dict[str, Counter] = {}
    for raw_tag, count in counter.items():
        normalized = normalize_tag(raw_tag)
        if not normalized:
            continue
        collapsed[normalized] += count
        raw_members.setdefault(normalized, Counter())[raw_tag] += count
    return collapsed, raw_members
