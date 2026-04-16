#!/usr/bin/env python3

from paths import initial_noncanon_db_path, metadata_db_path

METADATA_DB_PATH = metadata_db_path()
OUTPUT_DB_PATH = initial_noncanon_db_path()
LIMIT = None
MAX_WORKERS = 10
NOTES = None


def build_noncanon_builder():
    from db_builders.initial_noncanon_db import InitialNoncanonDbBuilder

    return InitialNoncanonDbBuilder(
        metadata_db_path=METADATA_DB_PATH,
        output_db_path=OUTPUT_DB_PATH,
        max_workers=MAX_WORKERS,
    )


def run_noncanon_build() -> dict:
    builder = build_noncanon_builder()
    return builder.build(limit=LIMIT, notes=NOTES)


def print_run_configuration() -> None:
    print("Starting initial non-canonical DB build")
    print(f"Metadata DB: {METADATA_DB_PATH}")
    print(f"Output DB: {OUTPUT_DB_PATH}")
    print(f"Max workers: {MAX_WORKERS}")


def print_run_summary(summary: dict) -> None:
    print(f"\nInitial non-canonical DB: {summary['output_db_path']}")
    print(f"Resume point: {summary['existing_profiles']} games already stored")
    print(
        f"Run {summary['run_id']}: "
        f"{summary['completed_games']}/{summary['attempted_games']} stored, "
        f"{summary['error_count']} errors"
    )


def main() -> int:
    print_run_configuration()
    summary = run_noncanon_build()
    print_run_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
