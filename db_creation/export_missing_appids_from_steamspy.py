#!/usr/bin/env python3

from __future__ import annotations

import argparse
import time
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from db_creation.paths import metadata_db_path

METADATA_DB_PATH = metadata_db_path()
STEAMSPY_ALL_URL = 'https://steamspy.com/api.php?request=all&page={page}'
DEFAULT_MAX_PAGES = 200
DEFAULT_SAMPLE_SIZE = 25
OUTPUT_PATH = PROJECT_ROOT / 'data' / 'missing_catalog_appids_from_steamspy.json'


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def load_local_metadata_appids() -> set[int]:
    with connect(METADATA_DB_PATH) as connection:
        rows = connection.execute('SELECT appid FROM games ORDER BY appid').fetchall()
    return {int(row['appid']) for row in rows}


def fetch_steamspy_catalog(max_pages: int) -> list[dict[str, object]]:
    collected: dict[int, dict[str, object]] = {}
    consecutive_failures = 0

    for page in range(max_pages):
        payload = None
        for attempt in range(3):
            response = requests.get(STEAMSPY_ALL_URL.format(page=page), timeout=120)
            response.raise_for_status()
            try:
                payload = response.json()
                break
            except requests.exceptions.JSONDecodeError:
                wait_seconds = 2 ** attempt
                time.sleep(wait_seconds)

        if payload is None:
            consecutive_failures += 1
            print(f'SteamSpy page {page} returned non-JSON content; stopping after {consecutive_failures} consecutive failures.')
            if consecutive_failures >= 1:
                break
            continue

        consecutive_failures = 0
        if not payload:
            break

        page_added = 0
        for raw_key, raw_game in payload.items():
            try:
                appid = int(raw_key)
            except (TypeError, ValueError):
                appid = int(raw_game.get('appid') or 0)
            if appid <= 0 or appid in collected:
                continue
            collected[appid] = {
                'appid': appid,
                'name': str(raw_game.get('name') or '').strip(),
                'positive': int(raw_game.get('positive', 0) or 0),
                'negative': int(raw_game.get('negative', 0) or 0),
                'owners': str(raw_game.get('owners') or '').strip(),
                'score_rank': str(raw_game.get('score_rank') or '').strip(),
            }
            page_added += 1

        if page_added == 0:
            break

        time.sleep(1.0)

    return sorted(collected.values(), key=lambda item: int(item['appid']))


def compute_missing_from_local(steamspy_games: list[dict[str, object]]) -> list[dict[str, object]]:
    local_appids = load_local_metadata_appids()
    missing = [game for game in steamspy_games if int(game['appid']) not in local_appids]
    for game in missing:
        game['source'] = 'steamspy_all'
    return missing


def write_output(missing_games: list[dict[str, object]], max_pages: int) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'generated_at': utcnow_iso(),
        'source': 'steamspy_all',
        'max_pages_requested': max_pages,
        'output_count': len(missing_games),
        'games': missing_games,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + '\n')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Export a JSON file of SteamSpy appids/titles missing from local metadata.'
    )
    parser.add_argument(
        '--max-pages',
        type=int,
        default=DEFAULT_MAX_PAGES,
        help='Maximum SteamSpy all-pages to scan.',
    )
    parser.add_argument(
        '--sample-size',
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
        help='How many missing appids to print after export.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    steamspy_games = fetch_steamspy_catalog(args.max_pages)
    missing_games = compute_missing_from_local(steamspy_games)
    write_output(missing_games, args.max_pages)

    print(f'SteamSpy catalog rows scanned: {len(steamspy_games)}')
    print(f'Missing from local metadata: {len(missing_games)}')
    print(f'JSON output: {OUTPUT_PATH}')

    if missing_games:
        print()
        print(f'First {min(args.sample_size, len(missing_games))} missing appids:')
        for game in missing_games[:args.sample_size]:
            print(f"  {int(game['appid'])} :: {str(game['name'] or '')}")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
