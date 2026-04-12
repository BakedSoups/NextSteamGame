from __future__ import annotations

import random
from typing import Sequence


def choose_representative(tags: Sequence[str], rng: random.Random) -> str:
    return rng.choice(list(tags))
