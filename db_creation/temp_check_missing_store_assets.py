#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional

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


def load_target_appids(db_path: str, limit: Optional[int], only_no_assets: bool) -> list[int]:
    conditions = " OR ".join(f"COALESCE(g.{column_name}, '') = ''" for column_name in ASSET_COLUMNS)
    query = f"""
        SELECT g.appid
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
    try:
        rows = connection.execute(query, params).fetchall()
    finally:
        connection.close()
    return [int(row[0]) for row in rows]


def probe_appid(enricher: SteamStoreAssetEnricher, appid: int) -> Dict[str, object]:
    discovered = enricher.extract_asset_urls(appid)
    return {
        "appid": appid,
        "found": [name for name, value in discovered.items() if value],
        "assets": discovered,
        "updated": False,
    }


def main() -> int:
    args = parse_args()
    appids = load_target_appids(args.db_path, args.limit, args.only_no_assets)
    print(f"Checking {len(appids)} games for missing storefront assets with {args.workers} workers")
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

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        future_to_appid = {executor.submit(probe_appid, enricher, appid): appid for appid in appids}
        for future in as_completed(future_to_appid):
            processed += 1
            result = future.result()
            found = result["found"]
            if found:
                any_found += 1
                for name in found:
                    found_counts[name] += 1
                if args.write:
                    result["updated"] = enricher.update_assets(int(result["appid"]), result["assets"])
                    if result["updated"]:
                        updated_rows += 1
            print(
                f"[{processed}/{len(appids)}] appid={result['appid']} found={found} updated={result['updated']}",
                flush=True,
            )

    print("\nSummary")
    print(f"- checked: {len(appids)}")
    print(f"- games with at least one missing asset now discoverable: {any_found}")
    if args.write:
        print(f"- rows updated: {updated_rows}")
    for column_name in ASSET_COLUMNS:
        print(f"- {column_name}: {found_counts[column_name]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
