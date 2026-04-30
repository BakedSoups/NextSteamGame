from __future__ import annotations

from .types import TailRow


def run_tail_merge(rows: list[TailRow]) -> list[TailRow]:
    # Layer 5 reads leftovers from layers 1-4.
    # Keep this pass-through until conservative tail rules are added explicitly.
    return rows
