from __future__ import annotations

import random
from pathlib import Path
from typing import Callable, Iterable, Sequence, TypeVar


T = TypeVar("T")


def build_random_sample_section(
    *,
    title: str,
    rows: Sequence[T],
    formatter: Callable[[T, int], list[str]],
    sample_size: int = 20,
    seed: int = 0,
) -> list[str]:
    if not rows:
        return [f"{title}_count: 0"]

    sampled = random.Random(seed).sample(list(rows), min(sample_size, len(rows)))
    lines = [
        f"{title}_seed: {seed}",
        f"{title}_count: {len(sampled)}",
        f"{title}:",
    ]
    for index, row in enumerate(sampled, start=1):
        lines.extend(formatter(row, index))
    return lines


def write_stage_diagnostics(
    summary_path: Path,
    *,
    metrics: Iterable[str],
    sections: Iterable[Iterable[str]] | None = None,
) -> None:
    lines = list(metrics)
    for section in sections or []:
        section_lines = list(section)
        if not section_lines:
            continue
        lines.append("")
        lines.extend(section_lines)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
