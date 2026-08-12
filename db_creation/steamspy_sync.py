from __future__ import annotations

import json
from pathlib import Path

from db_creation.add_appids_to_noncanon import (
    build_metadata_builder,
    ensure_metadata_placeholders,
    fetch_store_metadata_for_appids,
    load_metadata_rows,
    load_noncanon_appids,
    run_noncanon_for_appids,
)


def chunked(items: list[int], size: int) -> list[list[int]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def load_candidate_appids(input_path: Path, *, dedupe: bool = False) -> list[dict[str, object]]:
    payload = json.loads(input_path.read_text())
    games = payload.get("games") or []
    candidates: list[dict[str, object]] = []
    seen: set[int] = set()

    for game in games:
        try:
            appid = int(game.get("appid") or 0)
        except (TypeError, ValueError):
            continue
        if appid <= 0 or (dedupe and appid in seen):
            continue
        seen.add(appid)
        candidates.append(
            {
                "appid": appid,
                "name": str(game.get("name") or "").strip(),
            }
        )
    return candidates


def sync_selected_appids(
    selected_appids: list[int],
    *,
    batch_size: int,
    skip_noncanon: bool,
    max_workers: int,
) -> dict[str, int]:
    totals = {
        "inserted": 0,
        "store_attempted": 0,
        "store_succeeded": 0,
        "store_errors": 0,
        "noncanon_attempted": 0,
        "noncanon_completed": 0,
        "noncanon_errors": 0,
        "noncanon_skips": 0,
    }

    for batch_number, batch in enumerate(chunked(selected_appids, max(1, batch_size)), start=1):
        print()
        print(f"Batch {batch_number}: processing {len(batch)} appids")

        inserted = ensure_metadata_placeholders(batch)
        totals["inserted"] += len(inserted)
        if inserted:
            print(f"Inserted placeholder metadata rows: {len(inserted)}")

        metadata_summary = fetch_store_metadata_for_appids(build_metadata_builder(), batch)
        totals["store_attempted"] += int(metadata_summary["attempted"])
        totals["store_succeeded"] += int(metadata_summary["succeeded"])
        totals["store_errors"] += int(metadata_summary["errors"])
        print(
            f"Metadata sync batch {batch_number}: attempted={metadata_summary['attempted']} "
            f"succeeded={metadata_summary['succeeded']} errors={metadata_summary['errors']}"
        )

        if skip_noncanon:
            continue

        metadata_rows = load_metadata_rows(batch)
        noncanon_rows = load_noncanon_appids(batch)
        ready_for_noncanon = [
            appid for appid in batch
            if appid in metadata_rows and bool(metadata_rows[appid]["has_store_data"]) and appid not in noncanon_rows
        ]
        print(f"Ready for non-canon in batch {batch_number}: {len(ready_for_noncanon)}")
        if not ready_for_noncanon:
            continue

        summary = run_noncanon_for_appids(ready_for_noncanon, max_workers)
        totals["noncanon_attempted"] += int(summary["attempted_games"])
        totals["noncanon_completed"] += int(summary["completed_games"])
        totals["noncanon_errors"] += int(summary["error_count"])
        totals["noncanon_skips"] += int(summary["skip_count"])
        print(
            f"Non-canon batch {batch_number}: attempted={summary['attempted_games']} "
            f"completed={summary['completed_games']} errors={summary['error_count']} skips={summary['skip_count']}"
        )

    return totals


def print_sync_summary(totals: dict[str, int], *, skip_noncanon: bool) -> None:
    print()
    print("Run summary:")
    print(f"Placeholder metadata rows inserted: {totals['inserted']}")
    print(f"Store sync attempted: {totals['store_attempted']}")
    print(f"Store sync succeeded: {totals['store_succeeded']}")
    print(f"Store sync errors: {totals['store_errors']}")
    if not skip_noncanon:
        print(f"Non-canon attempted: {totals['noncanon_attempted']}")
        print(f"Non-canon completed: {totals['noncanon_completed']}")
        print(f"Non-canon errors: {totals['noncanon_errors']}")
        print(f"Non-canon skips: {totals['noncanon_skips']}")
