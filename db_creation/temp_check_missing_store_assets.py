#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Optional

from metadata_pipeline.assets import (
    ASSET_COLUMNS,
    ASSET_FILENAME_CANDIDATES,
    SteamStoreAssetEnricher,
)
from paths import metadata_db_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Temporary parallel probe for missing Steam storefront assets.",
    )
    parser.add_argument("--db-path", default=str(metadata_db_path()))
    parser.add_argument("--workers", type=int, default=40)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--only-no-assets",
        action="store_true",
        help="Restrict to rows currently marked no_assets in asset_enrichment_state.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write any discovered assets back into the database.",
    )
    return parser.parse_args()


def _missing_asset_columns(row: sqlite3.Row) -> tuple[str, ...]:
    return tuple(
        column_name
        for column_name in ASSET_COLUMNS
        if not (row[column_name] or "").strip()
    )


def load_target_rows(db_path: str, limit: Optional[int], only_no_assets: bool) -> list[dict[str, Any]]:
    conditions = " OR ".join(f"COALESCE(g.{column_name}, '') = ''" for column_name in ASSET_COLUMNS)
    query = f"""
        SELECT
            g.appid,
            g.header_image,
            g.capsule_image,
            g.capsule_imagev5,
            g.background_image,
            g.logo_image,
            g.library_hero_image,
            g.library_capsule_image
        FROM games g
        LEFT JOIN asset_enrichment_state aes ON aes.appid = g.appid
        WHERE g.has_store_data = 1
          AND (
            COALESCE(g.header_image, '') != ''
            OR COALESCE(g.capsule_image, '') != ''
            OR COALESCE(g.capsule_imagev5, '') != ''
            OR COALESCE(g.background_image, '') != ''
          )
          AND ({conditions})
    """
    params: list[object] = []
    if only_no_assets:
        query += " AND aes.status = 'no_assets'"
    query += " ORDER BY g.appid"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(query, params).fetchall()
    finally:
        connection.close()
    targets: list[dict[str, Any]] = []
    for row in rows:
        missing_columns = _missing_asset_columns(row)
        if not missing_columns:
            continue
        targets.append(
            {
                "appid": int(row["appid"]),
                "missing_columns": missing_columns,
                "existing_context": {
                    "header_image": row["header_image"] or "",
                    "capsule_image": row["capsule_image"] or "",
                    "capsule_imagev5": row["capsule_imagev5"] or "",
                    "background_image": row["background_image"] or "",
                },
            }
        )
    return targets


def probe_appid(enricher: SteamStoreAssetEnricher, target: dict[str, Any]) -> Dict[str, object]:
    discovered = enricher.extract_asset_urls(
        int(target["appid"]),
        existing_context=target["existing_context"],
        missing_columns=target["missing_columns"],
    )
    return {
        "appid": int(target["appid"]),
        "found": [name for name, value in discovered.items() if value],
        "assets": discovered,
    }


def main() -> int:
    args = parse_args()
    targets = load_target_rows(args.db_path, args.limit, args.only_no_assets)
    print(f"Checking {len(targets)} games for missing storefront assets with {args.workers} workers")
    print(f"Candidate filenames: {sum(len(v) for v in ASSET_FILENAME_CANDIDATES.values())}")

    enricher = SteamStoreAssetEnricher(
        db_path=args.db_path,
        workers=args.workers,
        batch_size=max(1, args.workers),
        timeout=20,
    )

    found_counts = {column_name: 0 for column_name in ASSET_COLUMNS}
    any_found = 0
    processed = 0
    updated_rows = 0
    pending_updates: list[tuple[int, Dict[str, Optional[str]]]] = []

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        future_to_appid = {
            executor.submit(probe_appid, enricher, target): int(target["appid"])
            for target in targets
        }
        for future in as_completed(future_to_appid):
            processed += 1
            result = future.result()
            found = result["found"]
            update_status = "not-requested"
            if found:
                any_found += 1
                for name in found:
                    found_counts[name] += 1
                if args.write:
                    pending_updates.append((int(result["appid"]), result["assets"]))
                    update_status = "queued"
                else:
                    update_status = "dry-run"
            print(
                f"[{processed}/{len(targets)}] appid={result['appid']} found={found} write={update_status}",
                flush=True,
            )

    if args.write and pending_updates:
        updated_rows = enricher.update_assets_batch(pending_updates)

    print("\nSummary")
    print(f"- checked: {len(targets)}")
    print(f"- games with at least one missing asset now discoverable: {any_found}")
    if args.write:
        print(f"- rows updated: {updated_rows}")
    for column_name in ASSET_COLUMNS:
        print(f"- {column_name}: {found_counts[column_name]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
