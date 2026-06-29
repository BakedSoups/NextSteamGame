#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db_creation.metadata_pipeline.pipeline import RetryConfig, SteamMetadataBuilder, configure_logging
from db_creation.paths import initial_noncanon_db_path, metadata_db_path

METADATA_DB_PATH = metadata_db_path()
NONCANON_DB_PATH = initial_noncanon_db_path()
DEFAULT_NONCANON_WORKERS = 2
LOGGER = logging.getLogger('add_appids_to_noncanon')
STORE_SYNC_ERROR_TYPES = (RuntimeError, ValueError, sqlite3.Error)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def build_metadata_builder() -> SteamMetadataBuilder:
    return SteamMetadataBuilder(
        db_path=METADATA_DB_PATH,
        retry_config=RetryConfig(
            max_retries=5,
            base_delay=2.0,
            timeout=30,
        ),
        store_delay=0.4,
        store_batch_delay=12.0,
        store_batch_size=5,
        store_workers=1,
        price_regions=['us'],
    )


def build_noncanon_builder(max_workers: int):
    from db_creation.db_builders.initial_noncanon_db import InitialNoncanonDbBuilder

    return InitialNoncanonDbBuilder(
        metadata_db_path=METADATA_DB_PATH,
        output_db_path=NONCANON_DB_PATH,
        max_workers=max_workers,
    )


def load_metadata_rows(appids: list[int]) -> dict[int, sqlite3.Row]:
    if not appids:
        return {}
    placeholders = ','.join(['?'] * len(appids))
    with connect(METADATA_DB_PATH) as connection:
        rows = connection.execute(
            f'SELECT appid, name, has_store_data FROM games WHERE appid IN ({placeholders}) ORDER BY appid',
            appids,
        ).fetchall()
    return {int(row['appid']): row for row in rows}


def load_noncanon_appids(appids: list[int]) -> set[int]:
    if not appids:
        return set()
    placeholders = ','.join(['?'] * len(appids))
    with connect(NONCANON_DB_PATH) as connection:
        try:
            rows = connection.execute(
                f'SELECT appid FROM raw_game_semantics WHERE appid IN ({placeholders}) ORDER BY appid',
                appids,
            ).fetchall()
        except sqlite3.OperationalError:
            return set()
    return {int(row['appid']) for row in rows}


def print_status(appids: list[int], label: str) -> dict[int, dict[str, object]]:
    metadata_rows = load_metadata_rows(appids)
    noncanon_appids = load_noncanon_appids(appids)

    print()
    print(label)
    status_map: dict[int, dict[str, object]] = {}
    for appid in appids:
        metadata_row = metadata_rows.get(appid)
        in_metadata = metadata_row is not None
        has_store_data = bool(metadata_row['has_store_data']) if metadata_row is not None else False
        in_noncanon = appid in noncanon_appids
        name = str(metadata_row['name'] or '') if metadata_row is not None else ''
        status_map[appid] = {
            'name': name,
            'in_metadata': in_metadata,
            'has_store_data': has_store_data,
            'in_noncanon': in_noncanon,
        }
        print(
            f"  {appid} :: {name} :: in_metadata={int(in_metadata)} "
            f"has_store_data={int(has_store_data)} in_noncanon={int(in_noncanon)}"
        )
    return status_map


def ensure_metadata_placeholders(appids: list[int]) -> list[int]:
    metadata_rows = load_metadata_rows(appids)
    missing = [appid for appid in appids if appid not in metadata_rows]
    if not missing:
        return []

    timestamp = utcnow_iso()
    with connect(METADATA_DB_PATH) as connection:
        connection.executemany(
            "INSERT INTO games (appid, created_at, updated_at) VALUES (?, ?, ?) ON CONFLICT(appid) DO NOTHING",
            [(appid, timestamp, timestamp) for appid in missing],
        )
        connection.commit()
    return missing


def fetch_store_metadata_for_appids(builder: SteamMetadataBuilder, appids: list[int]) -> dict[str, int]:
    builder.create_schema()
    sync_run_id = builder.start_sync_run(notes='add_appids_to_noncanon')
    attempted = 0
    succeeded = 0
    error_count = 0
    status = 'completed'

    try:
        for appid in appids:
            try:
                payload = builder.fetch_app_details(appid, region_code='us')
                attempted += 1
                success = builder.upsert_store_details(appid, payload, region_code='us')
                if success:
                    succeeded += 1
                LOGGER.info('Targeted store sync appid=%s success=%s', appid, success)
            except STORE_SYNC_ERROR_TYPES as exc:
                error_count += 1
                builder.mark_store_failure(appid, str(exc))
                builder.record_error(sync_run_id, source='steam_store', error_message=str(exc), appid=appid)
                LOGGER.error('Targeted store enrichment failed for appid %s: %s', appid, exc)
        if error_count > 0:
            status = 'completed_with_errors'
    finally:
        builder.finish_sync_run(
            sync_run_id=sync_run_id,
            status=status,
            steamspy_pages_seen=0,
            appids_discovered=len(appids),
            store_attempted=attempted,
            store_succeeded=succeeded,
            error_count=error_count,
        )

    return {
        'attempted': attempted,
        'succeeded': succeeded,
        'errors': error_count,
    }


def run_noncanon_for_appids(appids: list[int], max_workers: int) -> dict:
    builder = build_noncanon_builder(max_workers)
    return builder.build(appids=appids, notes='add_appids_to_noncanon')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Ensure specific Steam appids exist in metadata and non-canon.'
    )
    parser.add_argument(
        'appids',
        nargs='+',
        type=int,
        help='Steam appids to seed into metadata and then generate missing non-canon vectors for.',
    )
    parser.add_argument(
        '--skip-noncanon',
        action='store_true',
        help='Stop after metadata/store sync and do not generate non-canon vectors.',
    )
    parser.add_argument(
        '--max-workers',
        type=int,
        default=DEFAULT_NONCANON_WORKERS,
        help='Worker count for non-canon vector generation.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging()
    requested_appids = sorted({int(appid) for appid in args.appids})

    print_status(requested_appids, 'Before sync:')

    inserted = ensure_metadata_placeholders(requested_appids)
    if inserted:
        print()
        print(f'Inserted {len(inserted)} placeholder metadata rows for missing appids.')

    metadata_builder = build_metadata_builder()
    metadata_summary = fetch_store_metadata_for_appids(metadata_builder, requested_appids)
    print()
    print(
        f"Metadata sync: attempted={metadata_summary['attempted']} "
        f"succeeded={metadata_summary['succeeded']} errors={metadata_summary['errors']}"
    )

    status_map = print_status(requested_appids, 'After metadata sync:')
    if args.skip_noncanon:
        return 0

    ready_for_noncanon = [
        appid for appid in requested_appids
        if status_map[appid]['has_store_data'] and not status_map[appid]['in_noncanon']
    ]
    if not ready_for_noncanon:
        print()
        print('No requested appids are eligible for non-canon generation.')
        return 0

    print()
    print(f'Generating non-canon vectors for {len(ready_for_noncanon)} appids with max_workers={args.max_workers}')
    summary = run_noncanon_for_appids(ready_for_noncanon, args.max_workers)
    final_status = summary.get('status', 'completed')
    print()
    print(f"Run {summary['run_id']} finished with status: {final_status}")
    print(f"Attempted games: {summary['attempted_games']}")
    print(f"Completed games: {summary['completed_games']}")
    print(f"Errors: {summary['error_count']}")
    print(f"Skips: {summary['skip_count']}")
    print(f"Output DB: {summary['output_db_path']}")
    print_status(requested_appids, 'After non-canon sync:')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
