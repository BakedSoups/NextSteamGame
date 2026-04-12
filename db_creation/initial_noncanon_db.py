#!/usr/bin/env python3

from pathlib import Path

from paths import initial_noncanon_db_path, metadata_db_path

METADATA_DB_PATH = metadata_db_path()
OUTPUT_DB_PATH = initial_noncanon_db_path()
LIMIT = None
MAX_WORKERS = None
NOTES = None


def main() -> int:
    from db_builders.initial_noncanon_db import InitialNoncanonDbBuilder

    builder = InitialNoncanonDbBuilder(
        metadata_db_path=METADATA_DB_PATH,
        output_db_path=OUTPUT_DB_PATH,
        max_workers=MAX_WORKERS,
    )
    summary = builder.build(limit=LIMIT, notes=NOTES)
    print(f"\nInitial non-canonical DB: {summary['output_db_path']}")
    print(f"Resume point: {summary['existing_profiles']} games already stored")
    print(
        f"Run {summary['run_id']}: "
        f"{summary['completed_games']}/{summary['attempted_games']} stored, "
        f"{summary['error_count']} errors"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
