from __future__ import annotations

from pathlib import Path

from .defaults import (
    DEFAULT_ANALYSIS_DIR,
    METADATA_LEFTOVERS_CSV_PATH,
    METADATA_TAIL_CSV_PATH,
    SUMMARY_PATH,
    VECTORS_LEFTOVERS_CSV_PATH,
    VECTORS_TAIL_CSV_PATH,
)
from .exporters import write_summary, write_tail_csv
from .families import build_tail_families
from .io import load_leftovers
from .layer_5_tail_merge import run_tail_merge


def run_canon_tail_export(*, analysis_output_dir: Path = DEFAULT_ANALYSIS_DIR) -> dict:
    metadata_rows = load_leftovers(analysis_output_dir / METADATA_LEFTOVERS_CSV_PATH.name)
    vector_rows = load_leftovers(analysis_output_dir / VECTORS_LEFTOVERS_CSV_PATH.name)

    metadata_tail = run_tail_merge(metadata_rows)
    vector_tail = run_tail_merge(vector_rows)

    metadata_families = build_tail_families(metadata_tail)
    vector_families = build_tail_families(vector_tail)

    metadata_tail_csv = analysis_output_dir / METADATA_TAIL_CSV_PATH.name
    vectors_tail_csv = analysis_output_dir / VECTORS_TAIL_CSV_PATH.name
    summary_path = analysis_output_dir / SUMMARY_PATH.name

    write_tail_csv(metadata_tail_csv, metadata_tail)
    write_tail_csv(vectors_tail_csv, vector_tail)
    write_summary(
        summary_path,
        [
            f"metadata_leftovers_in: {len(metadata_rows)}",
            f"vector_leftovers_in: {len(vector_rows)}",
            f"metadata_tail_rows_out: {len(metadata_tail)}",
            f"vector_tail_rows_out: {len(vector_tail)}",
            f"metadata_families: {len(metadata_families)}",
            f"vector_families: {len(vector_families)}",
        ],
    )
    return {
        "metadata_leftovers_in": len(metadata_rows),
        "vector_leftovers_in": len(vector_rows),
        "metadata_tail_rows_out": len(metadata_tail),
        "vector_tail_rows_out": len(vector_tail),
        "metadata_families": len(metadata_families),
        "vector_families": len(vector_families),
        "metadata_tail_csv_path": str(metadata_tail_csv),
        "vector_tail_csv_path": str(vectors_tail_csv),
        "summary_path": str(summary_path),
    }
