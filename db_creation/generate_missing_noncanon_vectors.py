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
NONCANON_DB_PATH = initial_noncanon_db_path()
DEFAULT_MAX_WORKERS = 2
DEFAULT_SAMPLE_SIZE = 25


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def load_eligible_metadata_games() -> dict[int, str]:
    with connect(METADATA_DB_PATH) as connection:
        rows = connection.execute(
            """
            SELECT appid, name
            FROM games
            WHERE has_store_data = 1
            ORDER BY appid
            """
        ).fetchall()
    return {int(row["appid"]): str(row["name"] or "") for row in rows}


def load_existing_noncanon_appids() -> set[int]:
    with connect(NONCANON_DB_PATH) as connection:
        try:
            rows = connection.execute(
                "SELECT appid FROM raw_game_semantics ORDER BY appid"
            ).fetchall()
        except sqlite3.OperationalError:
            return set()
    return {int(row["appid"]) for row in rows}


def compute_missing_appids() -> tuple[dict[int, str], list[int], set[int]]:
    eligible_games = load_eligible_metadata_games()
    existing_appids = load_existing_noncanon_appids()
    missing_appids = sorted(appid for appid in eligible_games if appid not in existing_appids)
    return eligible_games, missing_appids, existing_appids


def print_audit(sample_size: int) -> list[int]:
    eligible_games, missing_appids, existing_appids = compute_missing_appids()
    print(f"Metadata games with store data: {len(eligible_games)}")
    print(f"Existing non-canon vector rows: {len(existing_appids)}")
    print(f"Missing non-canon vector rows: {len(missing_appids)}")

    if missing_appids:
        print()
        print(f"First {min(sample_size, len(missing_appids))} missing appids:")
        for appid in missing_appids[:sample_size]:
            print(f"  {appid} :: {eligible_games.get(appid, '')}")
    else:
        print()
        print("No missing non-canon appids found.")

    return missing_appids


def build_noncanon_builder(max_workers: int):
    from db_creation.db_builders.initial_noncanon_db import InitialNoncanonDbBuilder

    return InitialNoncanonDbBuilder(
        metadata_db_path=METADATA_DB_PATH,
        output_db_path=NONCANON_DB_PATH,
        max_workers=max_workers,
    )


def generate_missing_vectors(appids: list[int], max_workers: int) -> dict:
    builder = build_noncanon_builder(max_workers)
    return builder.build(appids=appids, notes='generate_missing_noncanon_vectors')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Audit and generate missing non-canonical vector rows from metadata-backed appids.'
    )
    parser.add_argument(
        '--run',
        action='store_true',
        help='Generate vectors only for appids that have store metadata but are missing from raw_game_semantics.',
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Generate at most this many missing appids.',
    )
    parser.add_argument(
        '--sample-size',
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
        help='How many missing appids to print in audit output.',
    )
    parser.add_argument(
        '--max-workers',
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help='Worker count for vector generation.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    missing_appids = print_audit(args.sample_size)
    if not args.run:
        return 0

    if args.limit is not None:
        missing_appids = missing_appids[: max(0, args.limit)]

    if not missing_appids:
        print()
        print('Generation skipped because there are no missing appids to process.')
        return 0

    print()
    print(f"Generating vectors for {len(missing_appids)} missing appids with max_workers={args.max_workers}")
    summary = generate_missing_vectors(missing_appids, args.max_workers)
    status = summary.get('status', 'completed')
    print()
    print(f"Run {summary['run_id']} finished with status: {status}")
    print(f"Attempted games: {summary['attempted_games']}")
    print(f"Completed games: {summary['completed_games']}")
    print(f"Errors: {summary['error_count']}")
    print(f"Skips: {summary['skip_count']}")
    print(f"Semantics retries: {summary['semantics_retry_count']}")
    print(f"Output DB: {summary['output_db_path']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
