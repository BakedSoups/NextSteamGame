from __future__ import annotations

import random
from pathlib import Path

from .candidate_search import build_groups, load_model
from .exporters import write_preview_csv
from .heuristic_filter import metadata_lexical_guard
from .tag_loader import (
    collect_metadata_counters,
    collect_vector_counters,
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
    "genre_tree.traits": 0.83,
}

VECTOR_MAX_NEIGHBORS = 12
METADATA_MAX_NEIGHBORS = 8


def run_canonical_preview(
    noncanon_db_path: Path = NONCANON_DB_PATH,
    analysis_output_dir: Path = ANALYSIS_DIR,
    limit: int = LIMIT,
    seed_tags: list[str] | None = None,
) -> dict:
    metadata_csv_path = analysis_output_dir / "metadata_canon_preview.csv"
    vector_csv_path = analysis_output_dir / "vectors_canon_preview.csv"
    rng = random.Random(RNG_SEED)
    rows = load_rows(noncanon_db_path, sample_size=limit)
    model = load_model(MODEL_NAME)
    metadata_counters = filter_counters_by_seed_tags(collect_metadata_counters(rows), seed_tags or [])
    vector_counters = filter_counters_by_seed_tags(collect_vector_counters(rows), seed_tags or [])

    metadata_groups = build_groups(
        counters=metadata_counters,
        model=model,
        thresholds=METADATA_THRESHOLDS,
        max_neighbors=METADATA_MAX_NEIGHBORS,
        rng=rng,
        guard=metadata_lexical_guard,
    )
    vector_groups = build_groups(
        counters=vector_counters,
        model=model,
        thresholds=VECTOR_THRESHOLDS,
        max_neighbors=VECTOR_MAX_NEIGHBORS,
        rng=rng,
    )

    write_preview_csv(metadata_csv_path, metadata_groups, limit)
    write_preview_csv(vector_csv_path, vector_groups, limit)

    return {
        "row_count": len(rows),
        "limit": limit,
        "seed_tags": list(seed_tags or []),
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
