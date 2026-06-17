#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db_creation.add_appids_to_noncanon import (
    build_metadata_builder,
    configure_logging,
    ensure_metadata_placeholders,
    fetch_store_metadata_for_appids,
    load_metadata_rows,
    load_noncanon_appids,
    run_noncanon_for_appids,
)

INPUT_PATH = PROJECT_ROOT / 'data' / 'missing_catalog_appids_from_steamspy.json'
DEFAULT_BATCH_SIZE = 100
DEFAULT_NONCANON_WORKERS = 2
DEFAULT_SAMPLE_SIZE = 25


def chunked(items: list[int], size: int) -> list[list[int]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def load_candidate_appids(input_path: Path) -> list[dict[str, object]]:
    payload = json.loads(input_path.read_text())
    games = payload.get('games') or []
    candidates: list[dict[str, object]] = []
    seen: set[int] = set()
    for game in games:
        try:
            appid = int(game.get('appid') or 0)
        except (TypeError, ValueError):
            continue
        if appid <= 0 or appid in seen:
            continue
        seen.add(appid)
        candidates.append(
            {
                'appid': appid,
                'name': str(game.get('name') or '').strip(),
            }
        )
    return candidates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Sync appids from the SteamSpy-missing JSON into metadata and non-canon in order.'
    )
    parser.add_argument('--input', default=str(INPUT_PATH), help='Path to missing SteamSpy JSON export.')
    parser.add_argument('--limit', type=int, default=None, help='Maximum number of appids to process from the JSON.')
    parser.add_argument('--offset', type=int, default=0, help='Skip this many appids from the front of the JSON.')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE, help='How many appids to process per batch.')
    parser.add_argument('--skip-noncanon', action='store_true', help='Stop after metadata/store sync.')
    parser.add_argument('--max-workers', type=int, default=DEFAULT_NONCANON_WORKERS, help='Worker count for non-canon generation.')
    parser.add_argument('--sample-size', type=int, default=DEFAULT_SAMPLE_SIZE, help='How many selected appids to print before processing.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f'Missing input file: {input_path}')

    candidates = load_candidate_appids(input_path)
    selected = candidates[max(0, args.offset):]
    if args.limit is not None:
        selected = selected[: max(0, args.limit)]
    selected_appids = [int(item['appid']) for item in selected]

    print(f'Candidate appids in JSON: {len(candidates)}')
    print(f'Selected appids to process: {len(selected)}')
    print(f'Offset: {args.offset}')
    print(f'Batch size: {args.batch_size}')
    print(f'Input file: {input_path}')

    if selected:
        print()
        print(f'First {min(args.sample_size, len(selected))} selected appids:')
        for item in selected[:args.sample_size]:
            print(f"  {int(item['appid'])} :: {item['name']}")
    else:
        print()
        print('No appids selected.')
        return 0

    total_inserted = 0
    total_store_attempted = 0
    total_store_succeeded = 0
    total_store_errors = 0
    total_noncanon_attempted = 0
    total_noncanon_completed = 0
    total_noncanon_errors = 0
    total_noncanon_skips = 0

    for batch_number, batch in enumerate(chunked(selected_appids, max(1, args.batch_size)), start=1):
        print()
        print(f'Batch {batch_number}: processing {len(batch)} appids')

        inserted = ensure_metadata_placeholders(batch)
        total_inserted += len(inserted)
        if inserted:
            print(f'Inserted placeholder metadata rows: {len(inserted)}')

        metadata_summary = fetch_store_metadata_for_appids(build_metadata_builder(), batch)
        total_store_attempted += metadata_summary['attempted']
        total_store_succeeded += metadata_summary['succeeded']
        total_store_errors += metadata_summary['errors']
        print(
            f"Metadata sync batch {batch_number}: attempted={metadata_summary['attempted']} "
            f"succeeded={metadata_summary['succeeded']} errors={metadata_summary['errors']}"
        )

        if args.skip_noncanon:
            continue

        metadata_rows = load_metadata_rows(batch)
        noncanon_rows = load_noncanon_appids(batch)
        ready_for_noncanon = [
            appid for appid in batch
            if appid in metadata_rows and bool(metadata_rows[appid]['has_store_data']) and appid not in noncanon_rows
        ]
        print(f'Ready for non-canon in batch {batch_number}: {len(ready_for_noncanon)}')
        if not ready_for_noncanon:
            continue

        summary = run_noncanon_for_appids(ready_for_noncanon, args.max_workers)
        total_noncanon_attempted += int(summary['attempted_games'])
        total_noncanon_completed += int(summary['completed_games'])
        total_noncanon_errors += int(summary['error_count'])
        total_noncanon_skips += int(summary['skip_count'])
        print(
            f"Non-canon batch {batch_number}: attempted={summary['attempted_games']} "
            f"completed={summary['completed_games']} errors={summary['error_count']} skips={summary['skip_count']}"
        )

    print()
    print('Run summary:')
    print(f'Placeholder metadata rows inserted: {total_inserted}')
    print(f'Store sync attempted: {total_store_attempted}')
    print(f'Store sync succeeded: {total_store_succeeded}')
    print(f'Store sync errors: {total_store_errors}')
    if not args.skip_noncanon:
        print(f'Non-canon attempted: {total_noncanon_attempted}')
        print(f'Non-canon completed: {total_noncanon_completed}')
        print(f'Non-canon errors: {total_noncanon_errors}')
        print(f'Non-canon skips: {total_noncanon_skips}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
