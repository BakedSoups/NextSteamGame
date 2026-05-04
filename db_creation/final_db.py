#!/usr/bin/env python3

from paths import analysis_dir, final_canon_db_path, initial_noncanon_db_path

NONCANON_DB_PATH = initial_noncanon_db_path()
OUTPUT_DB_PATH = final_canon_db_path()
ANALYSIS_DIR = analysis_dir()
CANON_GROUPS_CSV_PATH = ANALYSIS_DIR / "canon_groups_v5.csv"
BATCH_SIZE = 500


def print_batch_progress(update: dict) -> None:
    print(
        f"Store batch {update['batch_number']}: "
        f"{update['processed_rows']}/{update['total_rows']} canonical game rows written"
    )


def run_final_build() -> dict:
    from final_pipeline import run_final_db_build
    from add_screenshots import run_screenshot_sync

    summary = run_final_db_build(
        noncanon_db_path=NONCANON_DB_PATH,
        output_db_path=OUTPUT_DB_PATH,
        canon_groups_csv_path=CANON_GROUPS_CSV_PATH,
        batch_size=BATCH_SIZE,
        progress=print_batch_progress,
    )
    screenshot_summary = run_screenshot_sync(
        metadata_db_path=NONCANON_DB_PATH.parent / "steam_metadata.db",
        final_db_path=OUTPUT_DB_PATH,
        print_summary=True,
    )
    summary["screenshot_rows"] = screenshot_summary["stored_rows"]
    return summary


def print_run_configuration() -> None:
    print(f"Building final canonical DB from {NONCANON_DB_PATH}")
    print(f"Output DB: {OUTPUT_DB_PATH}")
    print(f"Canon groups CSV: {CANON_GROUPS_CSV_PATH}")
    print(f"Batch size: {BATCH_SIZE}")


def print_run_summary(summary: dict) -> None:
    print(f"Run {summary['run_id']} finished with status: {summary['status']}")
    print(f"Processed rows: {summary['processed_rows']}")
    print(f"Canon groups: {summary['canon_groups']}")
    print(f"Screenshots: {summary.get('screenshot_rows', 0)}")
    print(f"Final DB: {summary['output_db_path']}")


def main() -> int:
    print_run_configuration()
    summary = run_final_build()
    print_run_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
