from __future__ import annotations

import random
from collections import Counter
from pathlib import Path
from typing import Callable, Dict

from .candidate_search import load_model
from .exporters import write_groups_csv
from .pipeline import (
    ANALYSIS_DIR,
    MODEL_NAME,
    NONCANON_DB_PATH,
    RNG_SEED,
    build_metadata_groups,
    build_vector_groups,
    count_total_tags,
)
from .tag_loader import (
    collect_metadata_counters,
    collect_vector_counters,
    collapse_counter_map,
    count_rows,
    iter_row_batches,
)


BATCH_SIZE = 500


def _merge_counter_maps(target: Dict[str, Counter], source: Dict[str, Counter]) -> None:
    for context, counter in source.items():
        target.setdefault(context, Counter()).update(counter)


def scan_noncanon_counters_batched(
    noncanon_db_path: Path,
    batch_size: int = BATCH_SIZE,
    progress: Callable[[dict], None] | None = None,
) -> dict:
    metadata_counters: Dict[str, Counter] = {}
    vector_counters: Dict[str, Counter] = {}
    total_rows = count_rows(noncanon_db_path)
    processed_rows = 0
    batch_count = 0

    for rows in iter_row_batches(noncanon_db_path, batch_size):
        batch_count += 1
        processed_rows += len(rows)
        _merge_counter_maps(metadata_counters, collect_metadata_counters(rows))
        _merge_counter_maps(vector_counters, collect_vector_counters(rows))

        if progress is not None:
            progress(
                {
                    "batch_number": batch_count,
                    "batch_rows": len(rows),
                    "processed_rows": processed_rows,
                    "total_rows": total_rows,
                    "metadata_unique_tags": count_total_tags(metadata_counters),
                    "vector_unique_tags": count_total_tags(vector_counters),
                    "metadata_contexts": len(metadata_counters),
                    "vector_contexts": len(vector_counters),
                }
            )

    return {
        "batch_count": batch_count,
        "processed_rows": processed_rows,
        "total_rows": total_rows,
        "metadata_counters": metadata_counters,
        "vector_counters": vector_counters,
    }


def write_full_export_summary(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"Non-canon DB: {summary['noncanon_db_path']}",
        f"Batches processed: {summary['batch_count']}",
        f"Rows processed: {summary['processed_rows']}",
        f"Total rows reported by DB: {summary['total_rows']}",
        f"Batch size: {summary['batch_size']}",
        f"Metadata contexts: {summary['metadata_contexts']}",
        f"Metadata unique tags: {summary['metadata_unique_tags']}",
        f"Metadata groups: {summary['metadata_groups']}",
        f"Vector contexts: {summary['vector_contexts']}",
        f"Vector unique tags: {summary['vector_unique_tags']}",
        f"Vector groups: {summary['vector_groups']}",
        f"Metadata CSV: {summary['metadata_csv_path']}",
        f"Vector CSV: {summary['vector_csv_path']}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_full_canonical_export(
    noncanon_db_path: Path = NONCANON_DB_PATH,
    analysis_output_dir: Path = ANALYSIS_DIR,
    batch_size: int = BATCH_SIZE,
    progress: Callable[[dict], None] | None = None,
) -> dict:
    rng = random.Random(RNG_SEED)
    model = load_model(MODEL_NAME)

    scan_summary = scan_noncanon_counters_batched(
        noncanon_db_path=noncanon_db_path,
        batch_size=batch_size,
        progress=progress,
    )

    metadata_counters, metadata_raw_members = collapse_counter_map(scan_summary["metadata_counters"])
    vector_counters, vector_raw_members = collapse_counter_map(scan_summary["vector_counters"])

    metadata_groups = build_metadata_groups(metadata_counters, metadata_raw_members, model, rng)
    vector_groups = build_vector_groups(vector_counters, vector_raw_members, model, rng)

    metadata_csv_path = analysis_output_dir / "metadata_canon_full.csv"
    vector_csv_path = analysis_output_dir / "vectors_canon_full.csv"
    summary_path = analysis_output_dir / "canon_export_summary.txt"

    write_groups_csv(metadata_csv_path, metadata_groups)
    write_groups_csv(vector_csv_path, vector_groups)

    summary = {
        "noncanon_db_path": str(noncanon_db_path),
        "batch_count": scan_summary["batch_count"],
        "processed_rows": scan_summary["processed_rows"],
        "total_rows": scan_summary["total_rows"],
        "batch_size": batch_size,
        "metadata_contexts": len(metadata_counters),
        "vector_contexts": len(vector_counters),
        "metadata_unique_tags": count_total_tags(metadata_counters),
        "vector_unique_tags": count_total_tags(vector_counters),
        "metadata_groups": len(metadata_groups),
        "vector_groups": len(vector_groups),
        "metadata_csv_path": str(metadata_csv_path),
        "vector_csv_path": str(vector_csv_path),
        "summary_path": str(summary_path),
    }
    write_full_export_summary(summary_path, summary)
    return summary
