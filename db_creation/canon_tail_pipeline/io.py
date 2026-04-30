from __future__ import annotations

import csv
from pathlib import Path

from .types import TailRow


def load_leftovers(csv_path: Path) -> list[TailRow]:
    if not csv_path.exists():
        return []
    rows: list[TailRow] = []
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            members = [member.strip() for member in str(row.get("members", "")).split("|") if member.strip()]
            rows.append(
                TailRow(
                    context=str(row["context"]),
                    representative_tag=str(row["representative_tag"]),
                    total_occurrences=int(row.get("total_occurrences", 0) or 0),
                    members=members,
                )
            )
    return rows
