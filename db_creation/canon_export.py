#!/usr/bin/env python3

from paths import analysis_dir, initial_noncanon_db_path

NONCANON_DB_PATH = initial_noncanon_db_path()
ANALYSIS_DIR = analysis_dir()
BATCH_SIZE = 500


def print_batch_progress(update: dict) -> None:
    total_rows = update["total_rows"]
    processed_rows = update["processed_rows"]
    if total_rows:
        progress_label = f"{processed_rows}/{total_rows}"
    else:
        progress_label = str(processed_rows)
    print(
        f"Batch {update['batch_number']}: "
        f"{progress_label} rows processed, "
        f"{update['metadata_unique_tags']} metadata tags, "
        f"{update['vector_unique_tags']} vector tags"
    )


def run_canonical_export() -> dict:
    from canon_pipeline.full_export import run_full_canonical_export

    return run_full_canonical_export(
        noncanon_db_path=NONCANON_DB_PATH,
        analysis_output_dir=ANALYSIS_DIR,
        batch_size=BATCH_SIZE,
        progress=print_batch_progress,
    )


def print_run_configuration() -> None:
    print(f"Scanning all non-canon rows from {NONCANON_DB_PATH}")
    print(f"Batch size: {BATCH_SIZE}")


def print_run_summary(summary: dict) -> None:
    print(f"Processed {summary['processed_rows']} rows across {summary['batch_count']} batches")
    print(
        "Built tag pools: "
        f"{summary['metadata_unique_tags']} metadata tags across {summary['metadata_contexts']} contexts, "
        f"{summary['vector_unique_tags']} vector tags across {summary['vector_contexts']} contexts"
    )
    print(
        f"Metadata groups made: {summary['metadata_groups']}"
    )
    print(
        f"Metadata tail embedding merges: {summary.get('metadata_tail_embedding_merges', 0)}"
    )
    print(
        f"Metadata tail internal merges: {summary.get('metadata_tail_internal_merges', 0)}"
    )
    print(
        f"Vector groups made: {summary['vector_groups']}"
    )
    print(
        f"Vector tail embedding merges: {summary.get('vector_tail_embedding_merges', 0)}"
    )
    print(
        f"Vector tail internal merges: {summary.get('vector_tail_internal_merges', 0)}"
    )
    print(f"Metadata CSV: {summary['metadata_csv_path']}")
    print(f"Vector CSV: {summary['vector_csv_path']}")
    print(f"Summary: {summary['summary_path']}")
    print(f"Elapsed seconds: {summary.get('elapsed_seconds', 'n/a')}")


def main() -> int:
    print_run_configuration()
    summary = run_canonical_export()
    print_run_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
