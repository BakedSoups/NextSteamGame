#!/usr/bin/env python3

from paths import analysis_dir, final_canon_db_path, initial_noncanon_db_path

NONCANON_DB_PATH = initial_noncanon_db_path()
OUTPUT_DB_PATH = final_canon_db_path()
ANALYSIS_DIR = analysis_dir()
METADATA_CSV_PATH = ANALYSIS_DIR / "metadata_canon_full.csv"
VECTORS_CSV_PATH = ANALYSIS_DIR / "vectors_canon_full.csv"
BATCH_SIZE = 500


def print_batch_progress(update: dict) -> None:
    print(
        f"Store batch {update['batch_number']}: "
        f"{update['processed_rows']}/{update['total_rows']} canonical game rows written"
    )


def run_final_build() -> dict:
    from final_pipeline import run_final_db_build

    return run_final_db_build(
        noncanon_db_path=NONCANON_DB_PATH,
        output_db_path=OUTPUT_DB_PATH,
        metadata_csv_path=METADATA_CSV_PATH,
        vectors_csv_path=VECTORS_CSV_PATH,
        batch_size=BATCH_SIZE,
        progress=print_batch_progress,
    )


def print_run_configuration() -> None:
    print(f"Building final canonical DB from {NONCANON_DB_PATH}")
    print(f"Output DB: {OUTPUT_DB_PATH}")
    print(f"Metadata CSV: {METADATA_CSV_PATH}")
    print(f"Vector CSV: {VECTORS_CSV_PATH}")
    print(f"Batch size: {BATCH_SIZE}")


def print_run_summary(summary: dict) -> None:
    print(f"Run {summary['run_id']} finished with status: {summary['status']}")
    print(f"Processed rows: {summary['processed_rows']}")
    print(f"Metadata groups: {summary['metadata_groups']}")
    print(f"Vector groups: {summary['vector_groups']}")
    print(f"Final DB: {summary['output_db_path']}")


def main() -> int:
    print_run_configuration()
    summary = run_final_build()
    print_run_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
