#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db_creation.paths import initial_noncanon_db_path, metadata_db_path

DEFAULT_STATUS = "no_steam_review"
DEFAULT_MAX_WORKERS = 2
RETRYABLE_STATUSES = {
    "no_steam_review",
    "no_reviews",
    "no_reviews_after_filtering",
    "no_insightful_reviews",
}


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def profile_status(metadata_json: str) -> str:
    try:
        metadata = json.loads(metadata_json)
    except (TypeError, json.JSONDecodeError):
        return "invalid_metadata"
    return str(metadata.get("status", "")).strip() or "ok"


def load_candidates(
    db_path: Path,
    statuses: set[str],
    appids: set[int] | None,
) -> list[sqlite3.Row]:
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT appid, name, metadata_json, updated_at
            FROM raw_game_semantics
            ORDER BY appid
            """
        ).fetchall()
    return [
        row
        for row in rows
        if profile_status(row["metadata_json"]) in statuses
        and (appids is None or int(row["appid"]) in appids)
    ]


def load_review_signals(db_path: Path) -> dict[int, int]:
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT appid, estimated_review_count, recommendations_total
            FROM games
            """
        ).fetchall()
    return {
        int(row["appid"]): max(
            int(row["estimated_review_count"] or 0),
            int(row["recommendations_total"] or 0),
        )
        for row in rows
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit or retry non-canonical profiles stored with a failure status."
    )
    parser.add_argument(
        "--status",
        action="append",
        default=[],
        choices=sorted(RETRYABLE_STATUSES),
        help=f"Status to retry; repeat for multiple statuses (default: {DEFAULT_STATUS}).",
    )
    parser.add_argument("--appid", action="append", type=int, help="Retry only this appid; repeat as needed.")
    parser.add_argument("--limit", type=int, default=None, help="Retry at most this many matching rows.")
    parser.add_argument(
        "--min-reviews",
        type=int,
        default=0,
        help="Require at least this many estimated reviews or Steam recommendations.",
    )
    parser.add_argument("--sample-size", type=int, default=25, help="Rows to print during the audit.")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    parser.add_argument("--run", action="store_true", help="Perform retries; without this flag the command is audit-only.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    statuses = set(args.status or [DEFAULT_STATUS])
    requested_appids = set(args.appid) if args.appid else None
    output_path = initial_noncanon_db_path()
    candidates = load_candidates(output_path, statuses, requested_appids)
    review_signals = load_review_signals(metadata_db_path())
    candidates = [
        row for row in candidates
        if review_signals.get(int(row["appid"]), 0) >= max(0, args.min_reviews)
    ]
    if args.limit is not None:
        candidates = candidates[: max(0, args.limit)]

    print(f"Non-canon DB: {output_path}")
    print(f"Selected statuses: {', '.join(sorted(statuses))}")
    print(f"Minimum review signal: {max(0, args.min_reviews)}")
    print(f"Matching retry candidates: {len(candidates)}")
    for row in candidates[: max(0, args.sample_size)]:
        print(
            f"  {int(row['appid'])} :: {row['name']} :: "
            f"{profile_status(row['metadata_json'])} :: reviews={review_signals.get(int(row['appid']), 0)}"
        )

    if not args.run:
        print("Audit only. Pass --run to retry these rows.")
        return 0
    if not candidates:
        print("No matching rows to retry.")
        return 0

    from db_creation.db_builders.initial_noncanon_db import InitialNoncanonDbBuilder

    appids = [int(row["appid"]) for row in candidates]
    builder = InitialNoncanonDbBuilder(
        metadata_db_path=metadata_db_path(),
        output_db_path=output_path,
        max_workers=args.max_workers,
    )
    summary = builder.build(
        appids=appids,
        notes=f"retry_noncanon_status statuses={','.join(sorted(statuses))}",
        replace_existing=True,
        preserve_existing_on_skipped=True,
    )

    remaining = load_candidates(output_path, statuses, set(appids))
    repaired = len(appids) - len(remaining)
    print()
    print(f"Attempted: {summary['attempted_games']}")
    print(f"Successfully repaired: {repaired}")
    print(f"Still carrying selected failure status: {len(remaining)}")
    print(f"Worker errors: {summary['error_count']}")
    print("Successful rows are now in the non-canonical DB. Rebuild the canonical DB and reload Postgres before serving them.")
    return 0 if repaired == len(appids) and summary["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
