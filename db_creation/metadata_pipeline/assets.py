from __future__ import annotations

import logging
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlsplit, urlunsplit

import requests


LOGGER = logging.getLogger("steam_store_asset_enrichment")

ASSET_COLUMNS = (
    "logo_image",
    "library_hero_image",
    "library_capsule_image",
)

ASSET_FILENAME_CANDIDATES = {
    "logo_image": [
        "logo.png",
        "logo_2x.png",
        "logo.jpg",
        "logo.webp",
    ],
    "library_hero_image": [
        "library_hero.jpg",
        "library_hero.png",
        "library_hero_2x.jpg",
        "library_hero_2x.png",
    ],
    "library_capsule_image": [
        "library_600x900.jpg",
        "library_600x900_2x.jpg",
        "library_capsule.jpg",
        "library_capsule.png",
        "library_capsule_2x.jpg",
        "library_capsule_2x.png",
    ],
}


def ensure_asset_columns(connection: sqlite3.Connection) -> None:
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


def _strip_query(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _directory_url(url: str) -> str:
    stripped = _strip_query(url)
    if "/" not in stripped:
        return stripped
    return stripped.rsplit("/", 1)[0]


class SteamStoreAssetEnricher:
    def __init__(
        self,
        db_path: str,
        workers: int = 5,
        batch_size: int = 25,
        batch_delay: float = 4.0,
        timeout: int = 20,
        limit: Optional[int] = None,
        refresh: bool = False,
        retry_failures: bool = False,
        restart: bool = False,
    ) -> None:
        self.db_path = db_path
        self.workers = max(1, workers)
        self.batch_size = max(1, batch_size)
        self.batch_delay = max(0.0, batch_delay)
        self.timeout = timeout
        self.limit = limit
        self.refresh = refresh
        self.retry_failures = retry_failures
        self.restart = restart
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

    def load_existing_asset_context(self, appid: int) -> dict[str, str]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    header_image,
                    capsule_image,
                    capsule_imagev5,
                    background_image
                FROM games
                WHERE appid = ?
                """,
                (appid,),
            ).fetchone()
        if row is None:
            return {}
        return {
            "header_image": row["header_image"] or "",
            "capsule_image": row["capsule_image"] or "",
            "capsule_imagev5": row["capsule_imagev5"] or "",
            "background_image": row["background_image"] or "",
        }

    def reset_restart_state(self) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM asset_enrichment_state")
            connection.execute(
                """
                UPDATE games
                SET logo_image = NULL,
                    library_hero_image = NULL,
                    library_capsule_image = NULL
                """
            )
            connection.commit()

    def _derive_store_asset_base(self, appid: int) -> str:
        context = self.load_existing_asset_context(appid)
        for key in ("header_image", "capsule_image", "capsule_imagev5"):
            value = context.get(key)
            if value:
                return _directory_url(value)
        return f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{appid}"

    def _probe_image_url(self, url: str) -> bool:
        response = self.session.get(url, timeout=self.timeout, stream=True, allow_redirects=True)
        try:
            if response.status_code != 200:
                return False
            content_type = (response.headers.get("content-type") or "").lower()
            return content_type.startswith("image/")
        finally:
            response.close()

    def extract_asset_urls(self, appid: int) -> Dict[str, Optional[str]]:
        base_url = self._derive_store_asset_base(appid)
        discovered: Dict[str, Optional[str]] = {}

        for column_name in ASSET_COLUMNS:
            discovered[column_name] = None
            for filename in ASSET_FILENAME_CANDIDATES[column_name]:
                candidate = f"{base_url}/{filename}"
                try:
                    if self._probe_image_url(candidate):
                        discovered[column_name] = candidate
                        break
                except requests.RequestException:
                    continue

        return discovered

    def update_assets(self, appid: int, assets: Dict[str, Optional[str]]) -> bool:
        if not any(assets.values()):
            return False

        with self.connect() as connection:
            result = connection.execute(
                """
                UPDATE games
                SET logo_image = COALESCE(?, logo_image),
                    library_hero_image = COALESCE(?, library_hero_image),
                    library_capsule_image = COALESCE(?, library_capsule_image),
                    updated_at = datetime('now')
                WHERE appid = ?
                """,
                (
                    assets["logo_image"],
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
        assets = self.extract_asset_urls(appid)
        updated = self.update_assets(appid, assets)
        self.mark_state(appid, "success" if any(assets.values()) else "no_assets")
        return {
            "appid": appid,
            "updated": updated,
            "assets": assets,
        }

    def run(self) -> int:
        with self.connect() as connection:
            ensure_asset_columns(connection)

        if self.restart:
            LOGGER.info("Restart requested: clearing asset_enrichment_state and asset columns")
            self.reset_restart_state()

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
