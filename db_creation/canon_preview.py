#!/usr/bin/env python3

from paths import analysis_dir, initial_noncanon_db_path

NONCANON_DB_PATH = initial_noncanon_db_path()
ANALYSIS_DIR = analysis_dir()
LIMIT = 500
SEED_TAGS = ["action", "mystery"]


def main() -> int:
    from canon_pipeline.pipeline import run_canonical_preview

    print(f"Sampling up to {LIMIT} non-canon rows from {NONCANON_DB_PATH}")
    summary = run_canonical_preview(
        noncanon_db_path=NONCANON_DB_PATH,
        analysis_output_dir=ANALYSIS_DIR,
        limit=LIMIT,
        seed_tags=SEED_TAGS,
    )
    print(f"Loaded {summary['row_count']} sampled rows from {NONCANON_DB_PATH}")
    print(f"Unified limit: {summary['limit']}")
    print(f"Seed tags: {', '.join(summary['seed_tags'])}")
    print(
        "Prepared tag pools: "
        f"{summary['metadata_unique_tags']} metadata tags across {summary['metadata_contexts']} contexts, "
        f"{summary['vector_unique_tags']} vector tags across {summary['vector_contexts']} contexts"
    )
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
