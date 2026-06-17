#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_SAMPLE_SIZE = 25
DEFAULT_DELAY_SECONDS = 1.0
SUGGEST_URL = (
    'https://store.steampowered.com/search/suggest'
    '?term={term}&f=games&cc=US&realm=1&l=english'
)
OUTPUT_PATH = PROJECT_ROOT / 'data' / 'resolved_titles_to_appids.json'
APP_LINK_RE = re.compile(r'https?://store\.steampowered\.com/app/(\d+)/[^"\']*', re.IGNORECASE)
NAME_RE = re.compile(r'<div[^>]*class="match_name"[^>]*>(.*?)</div>', re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r'<[^>]+>')


def normalize_title(text: str) -> str:
    return re.sub(r'\s+', ' ', text.strip().casefold())


def parse_suggestions(payload: str) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    anchors = payload.split('<a ')[1:]
    for anchor in anchors:
        href_match = APP_LINK_RE.search(anchor)
        if not href_match:
            continue
        appid = int(href_match.group(1))
        name_match = NAME_RE.search(anchor)
        raw_name = name_match.group(1) if name_match else ''
        cleaned_name = html.unescape(TAG_RE.sub('', raw_name)).strip()
        if not cleaned_name:
            continue
        matches.append({'appid': appid, 'name': cleaned_name})
    return matches


def score_candidate(title: str, candidate_name: str) -> tuple[int, int, str]:
    normalized_title = normalize_title(title)
    normalized_candidate = normalize_title(candidate_name)
    exact = int(normalized_title == normalized_candidate)
    substring = int(normalized_title in normalized_candidate or normalized_candidate in normalized_title)
    return (exact, substring, normalized_candidate)


def resolve_title(title: str, delay_seconds: float) -> dict[str, object]:
    response = requests.get(
        SUGGEST_URL.format(term=quote_plus(title)),
        headers={'User-Agent': 'SteamRecommenderTitleResolver/1.0'},
        timeout=60,
    )
    response.raise_for_status()
    suggestions = parse_suggestions(response.text)
    suggestions = sorted(
        suggestions,
        key=lambda candidate: score_candidate(title, str(candidate['name'])),
        reverse=True,
    )
    best = suggestions[0] if suggestions else None
    if delay_seconds > 0:
        time.sleep(delay_seconds)
    return {
        'query': title,
        'resolved': best is not None,
        'best_match': best,
        'candidates': suggestions[:10],
    }


def load_titles(args: argparse.Namespace) -> list[str]:
    titles: list[str] = []
    if args.titles:
        titles.extend(args.titles)
    if args.input_file:
        raw_lines = Path(args.input_file).read_text().splitlines()
        titles.extend(line.strip() for line in raw_lines if line.strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for title in titles:
        key = normalize_title(title)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(title.strip())
    return deduped


def write_output(results: list[dict[str, object]]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'resolved_count': sum(1 for row in results if row['resolved']),
        'unresolved_count': sum(1 for row in results if not row['resolved']),
        'results': results,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + '\n')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Resolve Steam appids from game titles using Steam store search suggestions.'
    )
    parser.add_argument('titles', nargs='*', help='Game titles to resolve.')
    parser.add_argument('--input-file', help='Optional newline-delimited text file of game titles.')
    parser.add_argument('--sample-size', type=int, default=DEFAULT_SAMPLE_SIZE, help='How many results to print.')
    parser.add_argument('--delay-seconds', type=float, default=DEFAULT_DELAY_SECONDS, help='Delay between search requests.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    titles = load_titles(args)
    if not titles:
        raise SystemExit('Provide titles as arguments or via --input-file.')

    results = [resolve_title(title, args.delay_seconds) for title in titles]
    write_output(results)

    resolved_count = sum(1 for row in results if row['resolved'])
    unresolved_count = len(results) - resolved_count
    print(f'Titles processed: {len(results)}')
    print(f'Resolved: {resolved_count}')
    print(f'Unresolved: {unresolved_count}')
    print(f'JSON output: {OUTPUT_PATH}')

    print()
    print(f'First {min(args.sample_size, len(results))} results:')
    for row in results[:args.sample_size]:
        if row['resolved']:
            best = row['best_match'] or {}
            print(f"  {row['query']} -> {best.get('appid')} :: {best.get('name')}")
        else:
            print(f"  {row['query']} -> unresolved")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
