from __future__ import annotations

import random
from collections import Counter
from pathlib import Path
from typing import Dict, Tuple

from .candidate_search import build_groups, load_model
from .exporters import write_preview_csv
from .heuristic_filter import metadata_lexical_guard
from .tag_loader import (
    collect_metadata_counters,
    collect_vector_counters,
    collapse_counter_map,
    filter_counters_by_seed_tags,
    load_rows,
)
from paths import analysis_dir, initial_noncanon_db_path


NONCANON_DB_PATH = initial_noncanon_db_path()
ANALYSIS_DIR = analysis_dir()
LIMIT = 500
RNG_SEED = 42
MODEL_NAME = "all-MiniLM-L6-v2"

VECTOR_THRESHOLDS = {
    "mechanics": 0.74,
    "narrative": 0.78,
    "structure_loop": 0.76,
    "uniqueness": 0.78,
    "vibe": 0.80,
}

METADATA_THRESHOLDS = {
    "micro_tags": 0.82,
    "genre_tree.primary": 0.88,
    "genre_tree.sub": 0.84,
    "genre_tree.sub_sub": 0.85,
    "genre_tree.traits": 0.83,
}

VECTOR_MAX_NEIGHBORS = 12
METADATA_MAX_NEIGHBORS = 8


def sample_noncanon_rows(noncanon_db_path: Path, limit: int):
    return load_rows(noncanon_db_path, sample_size=limit)


def prepare_metadata_inputs(rows, seed_tags: list[str]) -> Tuple[Dict[str, Counter], Dict[str, Dict[str, Counter]]]:
    return collapse_counter_map(
        filter_counters_by_seed_tags(collect_metadata_counters(rows), seed_tags)
    )


def prepare_vector_inputs(rows, seed_tags: list[str]) -> Tuple[Dict[str, Counter], Dict[str, Dict[str, Counter]]]:
    return collapse_counter_map(
        filter_counters_by_seed_tags(collect_vector_counters(rows), seed_tags)
    )


def count_total_tags(counter_map: Dict[str, Counter]) -> int:
    return sum(len(counter) for counter in counter_map.values())


def build_metadata_groups(metadata_counters, metadata_raw_members, model, rng):
    return build_groups(
        counters=metadata_counters,
        raw_member_maps=metadata_raw_members,
        model=model,
        thresholds=METADATA_THRESHOLDS,
        max_neighbors=METADATA_MAX_NEIGHBORS,
        rng=rng,
        guard=metadata_lexical_guard,
    )


def build_vector_groups(vector_counters, vector_raw_members, model, rng):
    return build_groups(
        counters=vector_counters,
        raw_member_maps=vector_raw_members,
        model=model,
        thresholds=VECTOR_THRESHOLDS,
        max_neighbors=VECTOR_MAX_NEIGHBORS,
        rng=rng,
    )


def export_preview_outputs(analysis_output_dir: Path, metadata_groups, vector_groups, limit: int) -> tuple[Path, Path]:
    metadata_csv_path = analysis_output_dir / "metadata_canon_preview.csv"
    vector_csv_path = analysis_output_dir / "vectors_canon_preview.csv"
    write_preview_csv(metadata_csv_path, metadata_groups, limit)
    write_preview_csv(vector_csv_path, vector_groups, limit)
    return metadata_csv_path, vector_csv_path


def run_canonical_preview(
    noncanon_db_path: Path = NONCANON_DB_PATH,
    analysis_output_dir: Path = ANALYSIS_DIR,
    limit: int = LIMIT,
    seed_tags: list[str] | None = None,
) -> dict:
    seed_tags = list(seed_tags or [])
    rng = random.Random(RNG_SEED)
    rows = sample_noncanon_rows(noncanon_db_path, limit)
    model = load_model(MODEL_NAME)
    metadata_counters, metadata_raw_members = prepare_metadata_inputs(rows, seed_tags)
    vector_counters, vector_raw_members = prepare_vector_inputs(rows, seed_tags)

    metadata_groups = build_metadata_groups(metadata_counters, metadata_raw_members, model, rng)
    vector_groups = build_vector_groups(vector_counters, vector_raw_members, model, rng)
    metadata_csv_path, vector_csv_path = export_preview_outputs(
        analysis_output_dir,
        metadata_groups,
        vector_groups,
        limit,
    )

    return {
        "row_count": len(rows),
        "limit": limit,
        "seed_tags": seed_tags,
        "metadata_contexts": len(metadata_counters),
        "vector_contexts": len(vector_counters),
        "metadata_unique_tags": count_total_tags(metadata_counters),
        "vector_unique_tags": count_total_tags(vector_counters),
        "metadata_groups": len(metadata_groups),
        "vector_groups": len(vector_groups),
        "metadata_csv_path": str(metadata_csv_path),
        "vector_csv_path": str(vector_csv_path),
        "metadata_preview_rows": min(limit, len(metadata_groups)),
        "vector_preview_rows": min(limit, len(vector_groups)),
    }


def main() -> int:
    summary = run_canonical_preview()
    print(f"Loaded {summary['row_count']} rows from {NONCANON_DB_PATH}")
    print(f"Metadata groups made: {summary['metadata_groups']}")
    print(f"Vector groups made: {summary['vector_groups']}")
    print(f"Metadata CSV preview: {summary['metadata_csv_path']}")
    print(f"Vector CSV preview: {summary['vector_csv_path']}")
    print(
        "Preview groups written: "
        f"{summary['metadata_preview_rows']} metadata, "
        f"{summary['vector_preview_rows']} vectors"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
