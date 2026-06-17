#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / '.env')

from db_creation.metadata_pipeline.pipeline import RetryConfig, SteamMetadataBuilder, configure_logging
from db_creation.paths import initial_noncanon_db_path, metadata_db_path

METADATA_DB_PATH = metadata_db_path()
NONCANON_DB_PATH = initial_noncanon_db_path()
STEAM_APP_LIST_URL = 'https://partner.steam-api.com/IStoreService/GetAppList/v1/'
STEAM_WEB_API_KEY_ENV = 'STEAM_WEB_API_KEY'
DEFAULT_SEED_LIMIT = 100
DEFAULT_NONCANON_WORKERS = 2
LOGGER = logging.getLogger('backfill_catalog_to_noncanon')


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def fetch_public_steam_applist() -> list[dict[str, object]]:
    api_key = os.getenv(STEAM_WEB_API_KEY_ENV, '').strip()
    if not api_key:
        raise RuntimeError(
            f"Missing {STEAM_WEB_API_KEY_ENV}. Set a Steam Web API key before running catalog backfill."
        )

    normalized: list[dict[str, object]] = []
    last_appid = 0

    while True:
        response = requests.get(
            STEAM_APP_LIST_URL,
            params={
                'input_json': json.dumps(
                    {
                        'include_games': True,
                        'last_appid': last_appid,
                        'max_results': 50000,
                    },
                    separators=(',', ':'),
                )
            },
            headers={'x-webapi-key': api_key},
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        response_block = payload.get('response') or {}
        apps = response_block.get('apps') or []
        if not apps:
            break

        for app in apps:
            try:
                appid = int(app.get('appid') or 0)
            except (TypeError, ValueError):
                continue
            if appid <= 0:
                continue
            normalized.append({
                'appid': appid,
                'name': str(app.get('name') or '').strip(),
            })

        next_last_appid = int(response_block.get('last_appid') or 0)
        have_more_results = bool(response_block.get('have_more_results'))
        if not have_more_results or next_last_appid <= last_appid:
            break
        last_appid = next_last_appid

    return normalized


def load_local_metadata_appids() -> set[int]:
    with connect(METADATA_DB_PATH) as connection:
        rows = connection.execute('SELECT appid FROM games ORDER BY appid').fetchall()
    return {int(row['appid']) for row in rows}


def load_local_noncanon_appids() -> set[int]:
    with connect(NONCANON_DB_PATH) as connection:
        try:
            rows = connection.execute('SELECT appid FROM raw_game_semantics ORDER BY appid').fetchall()
        except sqlite3.OperationalError:
            return set()
    return {int(row['appid']) for row in rows}


def compute_missing_catalog_apps() -> tuple[list[dict[str, object]], set[int], set[int]]:
    steam_apps = fetch_public_steam_applist()
    local_metadata_appids = load_local_metadata_appids()
    local_noncanon_appids = load_local_noncanon_appids()
    missing = [app for app in steam_apps if int(app['appid']) not in local_metadata_appids]
    return missing, local_metadata_appids, local_noncanon_appids


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


def insert_missing_metadata_placeholders(apps: list[dict[str, object]]) -> int:
    if not apps:
        return 0
    timestamp = utcnow_iso()
    rows = [
        (int(app['appid']), str(app['name'] or ''), timestamp, timestamp)
        for app in apps
    ]
    with connect(METADATA_DB_PATH) as connection:
        connection.executemany(
            'INSERT INTO games (appid, name, created_at, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(appid) DO NOTHING',
            rows,
        )
        connection.commit()
    return len(rows)


def fetch_store_metadata_for_appids(builder: SteamMetadataBuilder, appids: list[int]) -> dict[str, int]:
    builder.create_schema()
    sync_run_id = builder.start_sync_run(notes='backfill_catalog_to_noncanon')
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
                LOGGER.info('Catalog backfill store sync appid=%s success=%s', appid, success)
            except Exception as exc:
                error_count += 1
                builder.mark_store_failure(appid, str(exc))
                builder.record_error(sync_run_id, source='steam_store', error_message=str(exc), appid=appid)
                LOGGER.error('Catalog backfill store enrichment failed for appid %s: %s', appid, exc)
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

    return {'attempted': attempted, 'succeeded': succeeded, 'errors': error_count}


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


def load_noncanon_rows(appids: list[int]) -> set[int]:
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


def run_noncanon_for_appids(appids: list[int], max_workers: int) -> dict:
    builder = build_noncanon_builder(max_workers)
    return builder.build(appids=appids, notes='backfill_catalog_to_noncanon')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Backfill missing public Steam appids into metadata and optionally non-canon.'
    )
    parser.add_argument(
        '--run',
        action='store_true',
        help='Seed missing catalog appids into metadata, fetch store data, and optionally generate non-canon vectors.',
    )
    parser.add_argument(
        '--seed-limit',
        type=int,
        default=DEFAULT_SEED_LIMIT,
        help='How many missing catalog appids to seed in one run.',
    )
    parser.add_argument(
        '--sample-size',
        type=int,
        default=25,
        help='How many missing catalog appids to print in audit output.',
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
    missing_apps, local_metadata_appids, local_noncanon_appids = compute_missing_catalog_apps()

    print(f'Local metadata appids: {len(local_metadata_appids)}')
    print(f'Local non-canon appids: {len(local_noncanon_appids)}')
    print(f'Missing public Steam appids from local metadata: {len(missing_apps)}')

    if missing_apps:
        print()
        print(f'First {min(args.sample_size, len(missing_apps))} missing catalog appids:')
        for app in missing_apps[:args.sample_size]:
            print(f"  {int(app['appid'])} :: {str(app['name'] or '')}")
    else:
        print()
        print('No public Steam appids are missing from local metadata.')
        return 0

    if not args.run:
        return 0

    seed_apps = missing_apps[: max(0, args.seed_limit)]
    if not seed_apps:
        print()
        print('No appids selected for seeding.')
        return 0

    print()
    print(f'Seeding {len(seed_apps)} missing catalog appids into metadata.')
    inserted = insert_missing_metadata_placeholders(seed_apps)
    print(f'Inserted placeholder metadata rows: {inserted}')

    metadata_builder = build_metadata_builder()
    metadata_summary = fetch_store_metadata_for_appids(
        metadata_builder,
        [int(app['appid']) for app in seed_apps],
    )
    print()
    print(
        f"Metadata sync: attempted={metadata_summary['attempted']} "
        f"succeeded={metadata_summary['succeeded']} errors={metadata_summary['errors']}"
    )

    seeded_appids = [int(app['appid']) for app in seed_apps]
    metadata_rows = load_metadata_rows(seeded_appids)
    noncanon_rows = load_noncanon_rows(seeded_appids)
    ready_for_noncanon = [
        appid for appid in seeded_appids
        if appid in metadata_rows and bool(metadata_rows[appid]['has_store_data']) and appid not in noncanon_rows
    ]

    print()
    print(f'Seeded appids with store data now available: {len(ready_for_noncanon)}')
    if args.skip_noncanon or not ready_for_noncanon:
        if not ready_for_noncanon:
            print('No seeded appids are eligible for non-canon generation yet.')
        return 0

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
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
