#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db_creation.paths import initial_noncanon_db_path, metadata_db_path

METADATA_DB_PATH = metadata_db_path()
OUTPUT_DB_PATH = initial_noncanon_db_path()
DEFAULT_MAX_WORKERS = 10
DEFAULT_SAMPLE_SIZE = 25


def load_eligible_metadata_games(db_path: Path) -> dict[int, str]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT appid, name
            FROM games
            WHERE has_store_data = 1
            ORDER BY appid
            """
        ).fetchall()
    finally:
        connection.close()
    return {int(row["appid"]): str(row["name"] or "") for row in rows}


def load_existing_noncanon_appids(db_path: Path) -> set[int]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute("SELECT appid FROM raw_game_semantics ORDER BY appid").fetchall()
    except sqlite3.OperationalError:
        return set()
    finally:
        connection.close()
    return {int(row["appid"]) for row in rows}


def compute_missing_appids() -> tuple[dict[int, str], list[int], set[int]]:
    eligible_games = load_eligible_metadata_games(METADATA_DB_PATH)
    existing_appids = load_existing_noncanon_appids(OUTPUT_DB_PATH)
    missing_appids = sorted(appid for appid in eligible_games if appid not in existing_appids)
    return eligible_games, missing_appids, existing_appids


def print_audit(sample_size: int) -> list[int]:
    eligible_games, missing_appids, existing_appids = compute_missing_appids()
    print(f"Metadata games with store data: {len(eligible_games)}")
    print(f"Existing non-canon rows: {len(existing_appids)}")
    print(f"Missing non-canon rows: {len(missing_appids)}")

    if missing_appids:
        print()
        print(f"First {min(sample_size, len(missing_appids))} missing appids:")
        for appid in missing_appids[:sample_size]:
            print(f"  {appid} :: {eligible_games.get(appid, '')}")
    else:
        print()
        print("No missing appids found.")

    return missing_appids


def build_builder(max_workers: int):
    from db_creation.db_builders.initial_noncanon_db import InitialNoncanonDbBuilder

    return InitialNoncanonDbBuilder(
        metadata_db_path=METADATA_DB_PATH,
        output_db_path=OUTPUT_DB_PATH,
        max_workers=max_workers,
    )


def repair_missing_appids(appids: list[int], max_workers: int) -> dict:
    builder = build_builder(max_workers)
    return builder.build(appids=appids, notes="repair_initial_noncanon_db")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit and repair missing rows in the initial non-canonical DB.")
    parser.add_argument("--repair", action="store_true", help="Backfill only appids that are eligible in metadata but missing in the non-canon DB.")
    parser.add_argument("--limit", type=int, default=None, help="Repair at most this many missing appids.")
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE, help="How many missing appids to print in audit output.")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS, help="Worker count for repair mode.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    missing_appids = print_audit(args.sample_size)
    if not args.repair:
        return 0

    if args.limit is not None:
        missing_appids = missing_appids[: max(0, args.limit)]

    if not missing_appids:
        print()
        print("Repair skipped because there are no missing appids to process.")
        return 0

    print()
    print(f"Repairing {len(missing_appids)} missing appids with max_workers={args.max_workers}")
    summary = repair_missing_appids(missing_appids, args.max_workers)
    status = summary.get('status', 'completed')
    print()
    print(f"Run {summary['run_id']} finished with status: {status}")
    print(f"Attempted games: {summary['attempted_games']}")
    print(f"Completed games: {summary['completed_games']}")
    print(f"Errors: {summary['error_count']}")
    print(f"Skips: {summary['skip_count']}")
    print(f"Output DB: {summary['output_db_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
