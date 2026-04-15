#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests

from paths import metadata_db_path


LOGGER = logging.getLogger("steam_store_asset_enrichment")

STORE_PAGE_URL = "https://store.steampowered.com/app/{appid}/"
ASSET_COLUMNS = (
    "logo_image",
    "icon_image",
    "library_hero_image",
    "library_capsule_image",
)
ASSET_PATTERNS = {
    "logo_image": re.compile(r"/logo(?:_[^/\"'?]+)?\.(?:png|webp)", re.IGNORECASE),
    "icon_image": re.compile(r"/icon\.(?:jpg|jpeg|png|webp|ico)", re.IGNORECASE),
    "library_hero_image": re.compile(r"/library_hero(?:_[^/\"'?]+)?\.(?:jpg|jpeg|png|webp)", re.IGNORECASE),
    "library_capsule_image": re.compile(
        r"/(?:library_600x900(?:_[^/\"'?]+)?|library_capsule(?:_[^/\"'?]+)?)\.(?:jpg|jpeg|png|webp)",
        re.IGNORECASE,
    ),
}
URL_PATTERN = re.compile(r"https?://[^\"'<>\\)\\s]+", re.IGNORECASE)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def ensure_columns(connection: sqlite3.Connection) -> None:
    existing = {
        row[1]
        for row in connection.execute("PRAGMA table_info(games)").fetchall()
    }
    for column_name in ASSET_COLUMNS:
        if column_name in existing:
            continue
        connection.execute(f"ALTER TABLE games ADD COLUMN {column_name} TEXT")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS asset_enrichment_state (
            appid INTEGER PRIMARY KEY,
            status TEXT NOT NULL,
            last_attempt_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_success_at TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
        )
        """
    )
    connection.commit()


def choose_best_url(urls: Sequence[str]) -> Optional[str]:
    if not urls:
        return None

    def score(url: str) -> tuple[int, int, int, str]:
        lower = url.lower()
        return (
            int("_2x" in lower or "@2x" in lower),
            int(lower.endswith(".png")),
            int("shared.akamai.steamstatic.com" in lower or "cdn.akamai.steamstatic.com" in lower),
            url,
        )

    return max(urls, key=score)


class SteamStoreAssetEnricher:
    def __init__(
        self,
        db_path: str,
        workers: int,
        batch_size: int,
        batch_delay: float,
        timeout: int,
        limit: Optional[int],
        refresh: bool,
        retry_failures: bool,
    ) -> None:
        self.db_path = db_path
        self.workers = max(1, workers)
        self.batch_size = max(1, batch_size)
        self.batch_delay = max(0.0, batch_delay)
        self.timeout = timeout
        self.limit = limit
        self.refresh = refresh
        self.retry_failures = retry_failures
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "SteamRecommenderStoreAssetEnricher/1.0 "
                    "(https://github.com/openai/codex)"
                )
            }
        )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _batched(self, items: Sequence[int]) -> Iterable[List[int]]:
        for start in range(0, len(items), self.batch_size):
            yield list(items[start:start + self.batch_size])

    def load_target_appids(self) -> List[int]:
        conditions = " OR ".join(f"{column_name} IS NULL OR {column_name} = ''" for column_name in ASSET_COLUMNS)
        query = f"""
            SELECT g.appid
            FROM games g
            LEFT JOIN asset_enrichment_state aes ON aes.appid = g.appid
            WHERE has_store_data = 1
        """
        if not self.refresh:
            query += f" AND ({conditions})"
            query += " AND (aes.appid IS NULL"
            if self.retry_failures:
                query += " OR aes.status = 'failed'"
            query += ")"
        query += " ORDER BY g.appid"

        params: List[Any] = []
        if self.limit is not None:
            query += " LIMIT ?"
            params.append(self.limit)

        with self.connect() as connection:
            return [int(row["appid"]) for row in connection.execute(query, params)]

    def load_total_candidate_appids(self) -> List[int]:
        query = """
            SELECT g.appid
            FROM games g
            WHERE g.has_store_data = 1
            ORDER BY g.appid
        """
        with self.connect() as connection:
            return [int(row["appid"]) for row in connection.execute(query)]

    def fetch_store_page(self, appid: int) -> str:
        response = self.session.get(
            STORE_PAGE_URL.format(appid=appid),
            params={"cc": "us", "l": "english"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.text

    def extract_asset_urls(self, appid: int, html: str) -> Dict[str, Optional[str]]:
        app_segment = f"/steam/apps/{appid}/"
        candidates: Dict[str, List[str]] = {column_name: [] for column_name in ASSET_COLUMNS}

        for raw_url in URL_PATTERN.findall(html):
            cleaned = raw_url.replace("\\/", "/").replace("&amp;", "&")
            if app_segment not in cleaned:
                continue
            for column_name, pattern in ASSET_PATTERNS.items():
                if pattern.search(cleaned):
                    candidates[column_name].append(cleaned)

        return {
            column_name: choose_best_url(urls)
            for column_name, urls in candidates.items()
        }

    def update_assets(self, appid: int, assets: Dict[str, Optional[str]]) -> bool:
        if not any(assets.values()):
            return False

        with self.connect() as connection:
            result = connection.execute(
                """
                UPDATE games
                SET logo_image = COALESCE(?, logo_image),
                    icon_image = COALESCE(?, icon_image),
                    library_hero_image = COALESCE(?, library_hero_image),
                    library_capsule_image = COALESCE(?, library_capsule_image),
                    updated_at = datetime('now')
                WHERE appid = ?
                """,
                (
                    assets["logo_image"],
                    assets["icon_image"],
                    assets["library_hero_image"],
                    assets["library_capsule_image"],
                    appid,
                ),
            )
            connection.commit()
        return bool(result.rowcount)

    def mark_state(self, appid: int, status: str, error_message: Optional[str] = None) -> None:
        with self.connect() as connection:
            if status in {"success", "no_assets"}:
                connection.execute(
                    """
                    INSERT INTO asset_enrichment_state (
                        appid, status, last_attempt_at, last_success_at, attempt_count, last_error
                    )
                    VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, NULL)
                    ON CONFLICT(appid) DO UPDATE SET
                        status = excluded.status,
                        last_attempt_at = CURRENT_TIMESTAMP,
                        last_success_at = CURRENT_TIMESTAMP,
                        attempt_count = asset_enrichment_state.attempt_count + 1,
                        last_error = NULL
                    """,
                    (appid, status),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO asset_enrichment_state (
                        appid, status, last_attempt_at, last_success_at, attempt_count, last_error
                    )
                    VALUES (?, ?, CURRENT_TIMESTAMP, NULL, 1, ?)
                    ON CONFLICT(appid) DO UPDATE SET
                        status = excluded.status,
                        last_attempt_at = CURRENT_TIMESTAMP,
                        attempt_count = asset_enrichment_state.attempt_count + 1,
                        last_error = excluded.last_error
                    """,
                    (appid, status, error_message[:1000] if error_message else None),
                )
            connection.commit()

    def process_appid(self, appid: int) -> Dict[str, Any]:
        html = self.fetch_store_page(appid)
        assets = self.extract_asset_urls(appid, html)
        updated = self.update_assets(appid, assets)
        self.mark_state(appid, "success" if any(assets.values()) else "no_assets")
        return {
            "appid": appid,
            "updated": updated,
            "assets": assets,
        }

    def run(self) -> int:
        with self.connect() as connection:
            ensure_columns(connection)

        all_candidate_appids = self.load_total_candidate_appids()
        appids = self.load_target_appids()
        absolute_position = {
            appid: index + 1
            for index, appid in enumerate(all_candidate_appids)
        }
        LOGGER.info("Store asset enrichment queue size: %s", len(appids))

        attempted = 0
        updated = 0
        failures = 0
        populated_counts = {column_name: 0 for column_name in ASSET_COLUMNS}
        total = len(appids)
        total_candidates = len(all_candidate_appids)
        processed = 0

        for batch in self._batched(appids):
            with ThreadPoolExecutor(max_workers=min(self.workers, len(batch))) as executor:
                future_to_appid = {
                    executor.submit(self.process_appid, appid): appid
                    for appid in batch
                }
                for future in as_completed(future_to_appid):
                    appid = future_to_appid[future]
                    attempted += 1
                    processed += 1
                    try:
                        result = future.result()
                        if result["updated"]:
                            updated += 1
                        for column_name, value in result["assets"].items():
                            if value:
                                populated_counts[column_name] += 1
                        LOGGER.info(
                            "Assets %s/%s | run %s/%s | appid=%s updated=%s found=%s",
                            absolute_position.get(appid, processed),
                            total_candidates,
                            processed,
                            total,
                            appid,
                            result["updated"],
                            [name for name, value in result["assets"].items() if value],
                        )
                    except Exception as exc:
                        failures += 1
                        self.mark_state(appid, "failed", str(exc))
                        LOGGER.error("Asset enrichment failed for appid %s: %s", appid, exc)

            if processed < total and self.batch_delay > 0:
                time.sleep(self.batch_delay)

        print(f"Attempted: {attempted}")
        print(f"Rows updated: {updated}")
        print(f"Failures: {failures}")
        print("Populated asset hits:")
        for column_name in ASSET_COLUMNS:
            print(f"- {column_name}: {populated_counts[column_name]}")

        return 0 if failures == 0 else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Steam store page asset URLs into steam_metadata.db")
    parser.add_argument("--db-path", default=str(metadata_db_path()))
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--batch-delay", type=float, default=4.0)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--retry-failures", action="store_true")
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()
    enricher = SteamStoreAssetEnricher(
        db_path=args.db_path,
        workers=args.workers,
        batch_size=args.batch_size,
        batch_delay=args.batch_delay,
        timeout=args.timeout,
        limit=args.limit,
        refresh=args.refresh,
        retry_failures=args.retry_failures,
    )
    return enricher.run()


if __name__ == "__main__":
    raise SystemExit(main())
