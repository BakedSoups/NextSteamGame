#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from db_creation.paths import analysis_dir
else:
    from db_creation.paths import analysis_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualize tag usage from canon CSV outputs."
    )
    parser.add_argument(
        "--metadata-csv",
        type=Path,
        default=analysis_dir() / "metadata_canon_full.csv",
        help="Path to metadata_canon_full.csv",
    )
    parser.add_argument(
        "--vectors-csv",
        type=Path,
        default=analysis_dir() / "vectors_canon_full.csv",
        help="Path to vectors_canon_full.csv",
    )
    parser.add_argument(
        "--family",
        choices=("metadata", "vectors", "all"),
        default="all",
        help="Which canon CSV family to include.",
    )
    parser.add_argument(
        "--context",
        default=None,
        help="Optional context filter, e.g. mechanics or genre_tree.primary",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=30,
        help="How many top tags to show in the bar chart.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=analysis_dir(),
        help="Output directory for chart and summary files.",
    )
    return parser.parse_args()


def _load_csv_rows(csv_path: Path, family: str) -> list[dict[str, Any]]:
    if not csv_path.exists():
        raise RuntimeError(f"Missing canon CSV: {csv_path}")
    rows: list[dict[str, Any]] = []
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                {
                    "group_id": int(row["group_id"]),
                    "source_family": family,
                    "context": row["context"],
                    "representative_tag": row["representative_tag"],
                    "member_count": int(row["member_count"]),
                    "total_occurrences": int(row["total_occurrences"]),
                }
            )
    return rows


def load_groups(
    *,
    metadata_csv: Path,
    vectors_csv: Path,
    family: str,
    context: str | None,
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    if family in {"metadata", "all"}:
        groups.extend(_load_csv_rows(metadata_csv, "metadata"))
    if family in {"vectors", "all"}:
        groups.extend(_load_csv_rows(vectors_csv, "vectors"))
    if context:
        groups = [group for group in groups if str(group["context"]) == context]
    groups.sort(key=lambda group: (-int(group["total_occurrences"]), str(group["representative_tag"])))
    return groups


def tail_summary(groups: list[dict[str, Any]]) -> dict[str, Any]:
    if not groups:
        return {
            "group_count": 0,
            "total_occurrences": 0,
            "member_count_singleton_groups": 0,
            "occurrence_singletons": 0,
            "groups_with_occurrences_le_2": 0,
            "groups_with_occurrences_le_5": 0,
            "median_occurrences": 0,
            "median_member_count": 0,
            "occurrence_bucket_counts": {},
            "top_contexts_by_group_count": {},
        }

    occurrence_values = [int(group["total_occurrences"]) for group in groups]
    member_counts = [int(group["member_count"]) for group in groups]
    bucket_counts = Counter()
    for value in occurrence_values:
        if value <= 1:
            bucket = "1"
        elif value <= 2:
            bucket = "2"
        elif value <= 5:
            bucket = "3-5"
        elif value <= 10:
            bucket = "6-10"
        elif value <= 25:
            bucket = "11-25"
        elif value <= 50:
            bucket = "26-50"
        elif value <= 100:
            bucket = "51-100"
        else:
            bucket = "101+"
        bucket_counts[bucket] += 1

    context_counts = Counter(str(group["context"]) for group in groups)
    return {
        "group_count": len(groups),
        "total_occurrences": sum(occurrence_values),
        "member_count_singleton_groups": sum(1 for value in member_counts if value == 1),
        "occurrence_singletons": sum(1 for value in occurrence_values if value == 1),
        "groups_with_occurrences_le_2": sum(1 for value in occurrence_values if value <= 2),
        "groups_with_occurrences_le_5": sum(1 for value in occurrence_values if value <= 5),
        "median_occurrences": median(occurrence_values),
        "median_member_count": median(member_counts),
        "occurrence_bucket_counts": dict(bucket_counts),
        "top_contexts_by_group_count": dict(context_counts.most_common(10)),
    }


def write_csv(groups: list[dict[str, Any]], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_family",
                "context",
                "representative_tag",
                "member_count",
                "total_occurrences",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(groups)


def write_summary(summary: dict[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")


def render_chart(
    groups: list[dict[str, Any]],
    summary: dict[str, Any],
    destination: Path,
    *,
    family: str,
    context: str | None,
    top_n: int,
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "matplotlib is required for final DB visualization. Install it, then rerun."
        ) from exc

    destination.parent.mkdir(parents=True, exist_ok=True)

    top_groups = groups[:top_n]
    if not top_groups:
        raise RuntimeError("No canonical tag groups matched the requested filters.")

    labels = []
    values = []
    seen_labels = Counter()
    for group in top_groups:
        base_label = f'{group["representative_tag"]} [{group["context"]}]'
        seen_labels[base_label] += 1
        label = (
            f"{base_label} #{seen_labels[base_label]}"
            if seen_labels[base_label] > 1
            else base_label
        )
        labels.append(label)
        values.append(int(group["total_occurrences"]))

    fig, (ax_head, ax_tail) = plt.subplots(
        2,
        1,
        figsize=(18, 14),
        gridspec_kw={"height_ratios": [3, 2]},
        constrained_layout=True,
    )

    y_positions = list(range(len(labels)))
    ax_head.barh(y_positions, values, color="#2c7fb8")
    ax_head.set_yticks(y_positions)
    ax_head.set_yticklabels(labels, fontsize=9)
    ax_head.invert_yaxis()
    ax_head.set_xlabel("Total occurrences")
    title_bits = ["Canonical Tag Usage"]
    title_bits.append(f"family={family}")
    if context:
        title_bits.append(f"context={context}")
    ax_head.set_title(" | ".join(title_bits))

    for index, value in enumerate(values):
        ax_head.text(value, index, f" {value}", va="center", fontsize=8)

    bucket_order = ["1", "2", "3-5", "6-10", "11-25", "26-50", "51-100", "101+"]
    bucket_values = [
        int(summary["occurrence_bucket_counts"].get(bucket, 0))
        for bucket in bucket_order
    ]
    ax_tail.bar(bucket_order, bucket_values, color="#7fcdbb")
    ax_tail.set_title("Long-tail group counts by occurrence bucket")
    ax_tail.set_xlabel("Occurrence bucket")
    ax_tail.set_ylabel("Group count")

    info_lines = [
        f"groups={summary['group_count']}",
        f"total_occurrences={summary['total_occurrences']}",
        f"member_singletons={summary['member_count_singleton_groups']}",
        f"occurrence_singletons={summary['occurrence_singletons']}",
        f"<=2 occurrences={summary['groups_with_occurrences_le_2']}",
        f"<=5 occurrences={summary['groups_with_occurrences_le_5']}",
        f"median_occurrences={summary['median_occurrences']}",
        f"median_member_count={summary['median_member_count']}",
    ]
    ax_tail.text(
        1.02,
        0.98,
        "\n".join(info_lines),
        transform=ax_tail.transAxes,
        va="top",
        ha="left",
        fontsize=10,
        bbox={"facecolor": "#f7f7f7", "edgecolor": "#cccccc", "boxstyle": "round,pad=0.4"},
    )

    fig.savefig(destination, dpi=180)
    plt.close(fig)


def generate_visualization_artifacts(
    *,
    metadata_csv: Path,
    vectors_csv: Path,
    out_dir: Path,
    family: str = "all",
    context: str | None = None,
    top: int = 30,
) -> dict[str, str]:
    if top <= 0:
        raise RuntimeError("--top must be positive")

    groups = load_groups(
        metadata_csv=metadata_csv,
        vectors_csv=vectors_csv,
        family=family,
        context=context,
    )

    if not groups:
        raise RuntimeError("No canonical tag groups matched the requested filters.")

    summary = tail_summary(groups)
    suffix_parts = [family]
    if context:
        suffix_parts.append(context.replace(".", "_"))
    suffix = "__".join(suffix_parts)

    chart_path = out_dir / f"tag_usage_{suffix}.png"
    csv_path = out_dir / f"tag_usage_{suffix}.csv"
    summary_path = out_dir / f"tag_usage_{suffix}_summary.json"

    write_csv(groups, csv_path)
    write_summary(summary, summary_path)
    render_chart(
        groups,
        summary,
        chart_path,
        family=family,
        context=context,
        top_n=top,
    )

    return {
        "chart_path": str(chart_path),
        "csv_path": str(csv_path),
        "summary_path": str(summary_path),
    }


def main() -> int:
    args = parse_args()
    outputs = generate_visualization_artifacts(
        metadata_csv=args.metadata_csv,
        vectors_csv=args.vectors_csv,
        out_dir=args.out_dir,
        family=args.family,
        context=args.context,
        top=args.top,
    )

    summary = tail_summary(
        load_groups(
            metadata_csv=args.metadata_csv,
            vectors_csv=args.vectors_csv,
            family=args.family,
            context=args.context,
        )
    )

    print(f"Chart: {outputs['chart_path']}")
    print(f"CSV: {outputs['csv_path']}")
    print(f"Summary: {outputs['summary_path']}")
    print(
        "Tail stats: "
        f"groups={summary['group_count']} "
        f"occ_singletons={summary['occurrence_singletons']} "
        f"member_singletons={summary['member_count_singleton_groups']} "
        f"<=5={summary['groups_with_occurrences_le_5']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
