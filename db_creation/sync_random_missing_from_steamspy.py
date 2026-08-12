#!/usr/bin/env python3

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db_creation.add_appids_to_noncanon import configure_logging
from db_creation.steamspy_sync import load_candidate_appids, print_sync_summary, sync_selected_appids

INPUT_PATH = PROJECT_ROOT / 'data' / 'missing_catalog_appids_from_steamspy.json'
DEFAULT_LIMIT = 3000
DEFAULT_BATCH_SIZE = 100
DEFAULT_NONCANON_WORKERS = 2
DEFAULT_SEED = 42


def select_random_appids(candidates: list[dict[str, object]], limit: int, seed: int) -> list[dict[str, object]]:
    pool = list(candidates)
    random.Random(seed).shuffle(pool)
    return pool[: max(0, min(limit, len(pool)))]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Randomly sample appids from the SteamSpy-missing JSON and sync them into metadata/non-canon.'
    )
    parser.add_argument('--input', default=str(INPUT_PATH), help='Path to missing SteamSpy JSON export.')
    parser.add_argument('--limit', type=int, default=DEFAULT_LIMIT, help='How many random missing appids to attempt.')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE, help='How many appids to process per batch.')
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED, help='Random seed for repeatable sampling.')
    parser.add_argument('--skip-noncanon', action='store_true', help='Stop after metadata/store sync.')
    parser.add_argument('--max-workers', type=int, default=DEFAULT_NONCANON_WORKERS, help='Worker count for non-canon generation.')
    parser.add_argument('--sample-size', type=int, default=25, help='How many sampled appids to print before processing.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f'Missing input file: {input_path}')

    candidates = load_candidate_appids(input_path)
    selected = select_random_appids(candidates, args.limit, args.seed)
    selected_appids = [int(item['appid']) for item in selected]

    print(f'Candidate appids in JSON: {len(candidates)}')
    print(f'Randomly selected appids: {len(selected)}')
    print(f'Batch size: {args.batch_size}')
    print(f'Input file: {input_path}')

    if selected:
        print()
        print(f'First {min(args.sample_size, len(selected))} sampled appids:')
        for item in selected[:args.sample_size]:
            print(f"  {int(item['appid'])} :: {item['name']}")
    else:
        print()
        print('No appids selected.')
        return 0

    totals = sync_selected_appids(
        selected_appids,
        batch_size=args.batch_size,
        skip_noncanon=args.skip_noncanon,
        max_workers=args.max_workers,
    )
    print_sync_summary(totals, skip_noncanon=args.skip_noncanon)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
