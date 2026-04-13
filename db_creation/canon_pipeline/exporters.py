from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Sequence

from .candidate_search import Group
from .normalization.display_forms import format_representative_tag
from .normalization.surface_forms import normalize_text


def collapse_export_members(context: str, group: Group) -> tuple[list[str], Counter]:
    collapsed = Counter()
    for raw_member in group.raw_members:
        normalized = normalize_text(raw_member)
        display = format_representative_tag(context, normalized)
        collapsed[display] += group.raw_counts[raw_member]
    ordered_members = sorted(collapsed, key=lambda item: (-collapsed[item], item))
    return ordered_members, collapsed


def write_preview_csv(path: Path, groups: Sequence[Group], preview_limit: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "group_id",
                "context",
                "representative_tag",
                "member_count",
                "total_occurrences",
                "members",
                "member_occurrences",
            ]
        )
        for index, group in enumerate(groups[:preview_limit], start=1):
            ordered_members, collapsed_counts = collapse_export_members(group.context, group)
            writer.writerow(
                [
                    index,
                    group.context,
                    group.representative,
                    len(ordered_members),
                    group.total_occurrences,
                    " | ".join(ordered_members),
                    "; ".join(f"{member}:{collapsed_counts[member]}" for member in ordered_members),
                ]
            )
