from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

from .candidate_search import Group


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
            ordered_members = sorted(set(group.raw_members), key=lambda item: (-group.raw_counts[item], item))
            writer.writerow(
                [
                    index,
                    group.context,
                    group.representative,
                    len(ordered_members),
                    group.total_occurrences,
                    " | ".join(ordered_members),
                    "; ".join(f"{member}:{group.raw_counts[member]}" for member in ordered_members),
                ]
            )
