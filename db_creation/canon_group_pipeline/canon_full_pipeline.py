#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

from .canon_export import print_run_summary as print_v1_summary
from .canon_export import run_canonical_export
from .canon_group_v2 import main as run_v2
from .canon_group_v3 import main as run_v3
from .canon_group_v4 import main as run_v4
from .canon_group_v5 import main as run_v5
from paths import analysis_dir


ANALYSIS_DIR = analysis_dir()


def _print_step(step: int, total: int, label: str) -> None:
    print()
    print(f"[{step}/{total}] {label}")


def _print_outputs() -> None:
    outputs = [
        ANALYSIS_DIR / "canon_groups.csv",
        ANALYSIS_DIR / "canon_groups_v2.csv",
        ANALYSIS_DIR / "canon_groups_v3.csv",
        ANALYSIS_DIR / "canon_groups_v4.csv",
        ANALYSIS_DIR / "canon_groups_v5.csv",
    ]
    print()
    print("Canon pipeline outputs:")
    for output in outputs:
        print(output)


def main() -> int:
    total_steps = 5

    _print_step(1, total_steps, "v1 canon export")
    v1_summary = run_canonical_export()
    print_v1_summary(v1_summary)

    _print_step(2, total_steps, "v2 leftover concept-core grouping")
    run_v2()

    _print_step(3, total_steps, "v3 semantic rescue on v1/v2 leftovers")
    run_v3()

    _print_step(4, total_steps, "v4 niche_anchors validation and splitting")
    run_v4()

    _print_step(5, total_steps, "v5 semantic rescue on small v4 groups")
    run_v5()

    _print_outputs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
