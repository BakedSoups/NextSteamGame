from __future__ import annotations

import csv
from pathlib import Path

from .types import CanonGroup, LeftoverRow


def write_groups_csv(csv_path: Path, groups: list[CanonGroup]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "context",
                "representative_tag",
                "parent_tag",
                "specificity_level",
                "member_count",
                "total_occurrences",
                "members",
            ]
        )
        for group in groups:
            members = " | ".join(sorted(group.raw_counts))
            writer.writerow(
                [
                    group.context,
                    group.representative_tag,
                    group.parent_tag,
                    group.specificity_level,
                    group.member_count,
                    group.total_occurrences,
                    members,
                ]
            )


def write_leftovers_csv(csv_path: Path, leftovers: list[LeftoverRow]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["context", "representative_tag", "total_occurrences", "members"])
        for row in leftovers:
            writer.writerow(
                [
                    row.context,
                    row.representative_tag,
                    row.total_occurrences,
                    " | ".join(row.members),
                ]
            )


def write_summary(summary_path: Path, lines: list[str]) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
