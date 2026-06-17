from __future__ import annotations

from collections import Counter
from typing import Dict


def merge_family_variants(counter: Counter, raw_members: Dict[str, Counter]) -> tuple[Counter, Dict[str, Counter]]:
    # Layer 4 is the placeholder for conservative family-level merges after surface cleanup.
    # Keep it pass-through until the family rules are implemented explicitly.
    return counter, raw_members
