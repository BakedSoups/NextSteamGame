#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

from database.initial_noncanon_db import InitialNoncanonDbBuilder


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METADATA_DB = PROJECT_ROOT / "data" / "steam_metadata.db"
DEFAULT_OUTPUT_DB = PROJECT_ROOT / "data" / "steam_initial_noncanon.db"


def main() -> None:
    builder = InitialNoncanonDbBuilder(
        metadata_db_path=DEFAULT_METADATA_DB,
        output_db_path=DEFAULT_OUTPUT_DB,
    )
    summary = builder.build()
    print(f"\nInitial non-canonical DB: {summary['output_db_path']}")
    print(f"Resume point: {summary['existing_profiles']} games already stored")
    print(
        f"Run {summary['run_id']}: "
        f"{summary['completed_games']}/{summary['attempted_games']} stored, "
        f"{summary['error_count']} errors"
    )


if __name__ == "__main__":
    main()
