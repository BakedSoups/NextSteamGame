#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db_creation.metadata_pipeline.pipeline import RetryConfig, SteamMetadataBuilder, configure_logging
from db_creation.paths import metadata_db_path

DB_PATH = metadata_db_path()
DEFAULT_SAMPLE_SIZE = 25
DEFAULT_STORE_WORKERS = 1
DEFAULT_STORE_BATCH_SIZE = 5
DEFAULT_STORE_BATCH_DELAY = 12.0
DEFAULT_TIMEOUT = 30
PRICE_REGIONS = ["us"]


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def load_metadata_counts(db_path: Path) -> dict[str, int]:
    with connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_games,
                SUM(CASE WHEN has_store_data = 1 THEN 1 ELSE 0 END) AS with_store_data,
                SUM(CASE WHEN has_store_data = 0 THEN 1 ELSE 0 END) AS missing_store_data
            FROM games
            """
        ).fetchone()
    return {
        "total_games": int(row["total_games"] or 0),
        "with_store_data": int(row["with_store_data"] or 0),
        "missing_store_data": int(row["missing_store_data"] or 0),
    }


def load_missing_status_counts(db_path: Path) -> list[tuple[str, int]]:
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                COALESCE(NULLIF(ist.store_fetch_status, ''), 'never_attempted') AS fetch_status,
                COUNT(*) AS row_count
            FROM games g
            LEFT JOIN ingestion_state ist ON ist.appid = g.appid
            WHERE g.has_store_data = 0
            GROUP BY COALESCE(NULLIF(ist.store_fetch_status, ''), 'never_attempted')
            ORDER BY row_count DESC, fetch_status ASC
            """
        ).fetchall()
    return [(str(row["fetch_status"]), int(row["row_count"])) for row in rows]


def load_missing_appids(db_path: Path, sample_size: int) -> list[sqlite3.Row]:
    with connect(db_path) as connection:
        return connection.execute(
            """
            SELECT
                g.appid,
                g.name,
                COALESCE(NULLIF(ist.store_fetch_status, ''), 'never_attempted') AS fetch_status,
                COALESCE(ist.last_error, '') AS last_error
            FROM games g
            LEFT JOIN ingestion_state ist ON ist.appid = g.appid
            WHERE g.has_store_data = 0
            ORDER BY g.appid
            LIMIT ?
            """,
            (sample_size,),
        ).fetchall()


def build_metadata_builder() -> SteamMetadataBuilder:
    return SteamMetadataBuilder(
        db_path=DB_PATH,
        retry_config=RetryConfig(
            max_retries=5,
            base_delay=2.0,
            timeout=DEFAULT_TIMEOUT,
        ),
        store_delay=0.4,
        store_batch_delay=DEFAULT_STORE_BATCH_DELAY,
        store_batch_size=DEFAULT_STORE_BATCH_SIZE,
        store_workers=DEFAULT_STORE_WORKERS,
        price_regions=PRICE_REGIONS,
    )


def print_audit(sample_size: int) -> int:
    counts = load_metadata_counts(DB_PATH)
    print(f"Total games in metadata DB: {counts['total_games']}")
    print(f"Games with store data: {counts['with_store_data']}")
    print(f"Games missing store data: {counts['missing_store_data']}")

    status_counts = load_missing_status_counts(DB_PATH)
    if status_counts:
        print()
        print("Missing-store status breakdown:")
        for status, count in status_counts:
            print(f"  {status}: {count}")

    sample_rows = load_missing_appids(DB_PATH, sample_size)
    if sample_rows:
        print()
        print(f"First {len(sample_rows)} appids missing store data:")
        for row in sample_rows:
            suffix = f" :: {row['last_error']}" if row['last_error'] else ""
            print(f"  {int(row['appid'])} :: {row['name'] or ''} :: {row['fetch_status']}{suffix}")

    return counts["missing_store_data"]


def run_repair(limit: int | None) -> int:
    builder = build_metadata_builder()
    return builder.build(
        limit=limit,
        page_limit=None,
        skip_store=False,
        refresh_store=False,
        resume=True,
        notes="repair_metadata_db",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit and repair missing basic metadata/store rows in steam_metadata.db.")
    parser.add_argument("--repair", action="store_true", help="Fetch Steam store metadata only for appids where has_store_data = 0.")
    parser.add_argument("--limit", type=int, default=None, help="Repair at most this many missing appids.")
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE, help="How many missing appids to print in audit output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging()
    missing_count = print_audit(args.sample_size)
    if not args.repair:
        return 0

    if missing_count == 0:
        print()
        print("Repair skipped because there are no appids missing store data.")
        return 0

    print()
    print("Running metadata-only repair for appids with has_store_data = 0")
    if args.limit is not None:
        print(f"Limit: {args.limit}")
    return run_repair(args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
