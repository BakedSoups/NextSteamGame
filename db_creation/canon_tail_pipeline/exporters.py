from __future__ import annotations

import csv
from pathlib import Path

from .types import TailRow


def write_tail_csv(csv_path: Path, rows: list[TailRow]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["context", "representative_tag", "total_occurrences", "members"])
        for row in rows:
            writer.writerow([row.context, row.representative_tag, row.total_occurrences, " | ".join(row.members)])


def write_summary(summary_path: Path, lines: list[str]) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
