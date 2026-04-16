#!/usr/bin/env python3

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from paths import analysis_dir, final_canon_db_path


FINAL_DB_PATH = final_canon_db_path()
OUTPUT_DIR = analysis_dir() / "final_db_viz"
TOP_N = 20

PALETTE = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
    "#4e79a7",
    "#f28e2b",
]


def _load_rows(db_path: Path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(
            """
            SELECT name, canonical_vectors_json, canonical_metadata_json, source_review_samples_json
            FROM canonical_game_semantics
            ORDER BY appid
            """
        ).fetchall()
    finally:
        connection.close()


def _review_status_counter(rows) -> Counter:
    counter = Counter()
    for row in rows:
        payload = json.loads(row["source_review_samples_json"])
        status = payload.get("status") or "canonicalized"
        counter[status] += 1
    return counter


def _vector_context_counters(rows) -> dict[str, Counter]:
    counters = {
        "mechanics": Counter(),
        "narrative": Counter(),
        "vibe": Counter(),
        "structure_loop": Counter(),
        "uniqueness": Counter(),
    }
    for row in rows:
        payload = json.loads(row["canonical_vectors_json"])
        for context, tag_weights in payload.items():
            bucket = counters.setdefault(context, Counter())
            for tag, weight in tag_weights.items():
                try:
                    bucket[tag] += int(weight)
                except (TypeError, ValueError):
                    continue
    return counters


def _metadata_context_counters(rows) -> dict[str, Counter]:
    counters = {
        "micro_tags": Counter(),
        "signature_tag": Counter(),
        "soundtrack_tags": Counter(),
        "genre_tree.primary": Counter(),
        "genre_tree.sub": Counter(),
        "genre_tree.sub_sub": Counter(),
        "genre_tree.traits": Counter(),
    }
    for row in rows:
        payload = json.loads(row["canonical_metadata_json"])
        for tag in payload.get("micro_tags", []):
            counters["micro_tags"][tag] += 1
        signature_tag = str(payload.get("signature_tag", "")).strip()
        if signature_tag:
            counters["signature_tag"][signature_tag] += 1
        for tag in payload.get("soundtrack_tags", []):
            counters["soundtrack_tags"][tag] += 1
        genre_tree = payload.get("genre_tree", {})
        for branch in ("primary", "sub", "sub_sub", "traits"):
            for tag in genre_tree.get(branch, []):
                counters[f"genre_tree.{branch}"][tag] += 1
    return counters


def _compress_counter(counter: Counter, top_n: int) -> list[tuple[str, int]]:
    items = counter.most_common()
    if len(items) <= top_n:
        return items
    top_items = items[:top_n]
    other_total = sum(value for _, value in items[top_n:])
    return top_items + [("Other", other_total)]


def _render_stacked_chart(
    title: str,
    series: list[tuple[str, list[tuple[str, int]]]],
    output_path: Path,
) -> None:
    labels = []
    for _, parts in series:
        for label, _ in parts:
            if label not in labels:
                labels.append(label)

    colors = {label: PALETTE[index % len(PALETTE)] for index, label in enumerate(labels)}
    y_positions = list(range(len(series)))
    fig_height = max(3.5, len(series) * 0.9 + 1.8)
    fig, ax = plt.subplots(figsize=(16, fig_height))
    left = [0.0] * len(series)

    for label in labels:
        values = []
        for _, parts in series:
            total = sum(value for _, value in parts) or 1
            value = next((count for part_label, count in parts if part_label == label), 0)
            values.append((value / total) * 100.0)

        ax.barh(
            y_positions,
            values,
            left=left,
            color=colors[label],
            edgecolor="white",
            height=0.72,
            label=label,
        )
        left = [current + value for current, value in zip(left, values)]

    ax.set_yticks(y_positions)
    ax.set_yticklabels([context for context, _ in series], fontsize=11)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of context total (%)")
    ax.set_title(title, fontsize=18, pad=16)
    ax.grid(axis="x", linestyle="--", alpha=0.25)
    ax.legend(
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        frameon=False,
        fontsize=9,
        ncol=1,
    )
    plt.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _render_pie_chart(title: str, parts: list[tuple[str, int]], output_path: Path) -> None:
    labels = [label for label, value in parts if value > 0]
    values = [value for _, value in parts if value > 0]
    colors = [PALETTE[index % len(PALETTE)] for index in range(len(labels))]

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.pie(
        values,
        labels=labels,
        colors=colors,
        autopct=lambda pct: f"{pct:.1f}%",
        startangle=90,
        counterclock=False,
        wedgeprops={"edgecolor": "white", "linewidth": 1},
        textprops={"fontsize": 11},
    )
    ax.set_title(title, fontsize=18, pad=18)
    ax.axis("equal")
    plt.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _write_summary(
    output_path: Path,
    total_games: int,
    status_counter: Counter,
    vector_counters: dict[str, Counter],
    metadata_counters: dict[str, Counter],
) -> None:
    lines = [
        f"Final DB: {FINAL_DB_PATH}",
        f"Total canonical games: {total_games}",
        "",
        "Review source statuses:",
    ]
    for label, count in status_counter.most_common():
        lines.append(f"- {label}: {count}")

    lines.append("")
    lines.append("Top vector tags by context:")
    for context, counter in vector_counters.items():
        top = ", ".join(f"{tag} ({value})" for tag, value in counter.most_common(5))
        lines.append(f"- {context}: {top}")

    lines.append("")
    lines.append("Top metadata tags by context:")
    for context, counter in metadata_counters.items():
        top = ", ".join(f"{tag} ({value})" for tag, value in counter.most_common(5))
        lines.append(f"- {context}: {top}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_visualization_inputs():
    rows = _load_rows(FINAL_DB_PATH)
    status_counter = _review_status_counter(rows)
    vector_counters = _vector_context_counters(rows)
    metadata_counters = _metadata_context_counters(rows)
    return rows, status_counter, vector_counters, metadata_counters


def render_visualizations(
    rows,
    status_counter: Counter,
    vector_counters: dict[str, Counter],
    metadata_counters: dict[str, Counter],
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _render_pie_chart(
        "Final DB Review Source Statuses",
        _compress_counter(status_counter, TOP_N),
        OUTPUT_DIR / "review_statuses_pie.png",
    )
    _render_stacked_chart(
        "Final DB Vector Composition By Context",
        [(context, _compress_counter(counter, TOP_N)) for context, counter in vector_counters.items()],
        OUTPUT_DIR / "vector_contexts_stacked.png",
    )
    _render_stacked_chart(
        "Final DB Metadata Composition By Context",
        [(context, _compress_counter(counter, TOP_N)) for context, counter in metadata_counters.items()],
        OUTPUT_DIR / "metadata_contexts_stacked.png",
    )
    _write_summary(
        OUTPUT_DIR / "summary.txt",
        len(rows),
        status_counter,
        vector_counters,
        metadata_counters,
    )


def print_run_configuration() -> None:
    print(f"Reading final canonical DB from {FINAL_DB_PATH}")
    print(f"Writing QA visualizations to {OUTPUT_DIR}")
    print(f"Top N compression threshold: {TOP_N}")


def print_run_summary(total_rows: int) -> None:
    print(f"Wrote visualizations to {OUTPUT_DIR}")
    print(f"Games analyzed: {total_rows}")


def main() -> int:
    print_run_configuration()
    rows, status_counter, vector_counters, metadata_counters = load_visualization_inputs()
    render_visualizations(rows, status_counter, vector_counters, metadata_counters)
    print_run_summary(len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
