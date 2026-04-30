from __future__ import annotations

from collections import Counter
from typing import Dict


def merge_surface_variants(counter: Counter, raw_members: Dict[str, Counter]) -> tuple[Counter, Dict[str, Counter]]:
    # Layer 3 is intentionally conservative in v1.
    # Layer 2 already collapses exact normalized variants, so this currently passes through.
    return counter, raw_members
