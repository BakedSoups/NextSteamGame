from __future__ import annotations

from collections import defaultdict

from canon_pipeline.layer_1_normalization import head_token

from .types import TailRow


def build_tail_families(rows: list[TailRow]) -> dict[tuple[str, str], list[TailRow]]:
    families: dict[tuple[str, str], list[TailRow]] = defaultdict(list)
    for row in rows:
        families[(row.context, head_token(row.representative_tag))].append(row)
    return dict(families)
