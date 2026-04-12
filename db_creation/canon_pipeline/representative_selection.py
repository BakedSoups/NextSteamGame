from __future__ import annotations

from collections import Counter
import random
from typing import Sequence


def choose_representative(
    tags: Sequence[str],
    rng: random.Random,
    counts: Counter | None = None,
) -> str:
    if not tags:
        raise ValueError("choose_representative requires at least one tag")
    if counts is None:
        return rng.choice(list(tags))
    ordered = sorted(tags, key=lambda tag: (-counts[tag], len(tag), tag))
    return ordered[0]
