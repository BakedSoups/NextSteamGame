#!/usr/bin/env python3
"""
Steam metadata database builder.

This script builds a canonical SQLite metadata layer for Steam games using:
- SteamSpy catalog pages for broad app discovery and popularity metrics
- Steam Store appdetails for richer structured metadata

The output is intentionally SQLite-only. Chroma/vector generation can be built
later on top of the canonical `games` and related normalized tables.
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests

from paths import metadata_db_path


LOGGER = logging.getLogger("steam_metadata_builder")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def parse_owner_estimate(owners_text: str) -> Optional[int]:
    if not owners_text:
        return None
    if ".." in owners_text:
        lower_text, upper_text = owners_text.split("..", 1)
        try:
            lower = int(lower_text.strip().replace(",", ""))
            upper = int(upper_text.strip().replace(",", ""))
            return (lower + upper) // 2
        except ValueError:
            return None
    try:
        return int(owners_text.replace(",", ""))
    except ValueError:
        return None


def parse_release_date(date_text: str) -> Optional[str]:
    if not date_text:
        return None

    candidates = (
        "%b %d, %Y",
        "%d %b, %Y",
        "%b %Y",
        "%Y",
    )
    for fmt in candidates:
        try:
            parsed = datetime.strptime(date_text, fmt)
            if fmt == "%b %Y":
                parsed = parsed.replace(day=1)
            if fmt == "%Y":
                parsed = parsed.replace(month=1, day=1)
            return parsed.date().isoformat()
        except ValueError:
            continue
    return None


def parse_supported_languages(raw_value: Any) -> List[tuple[str, int, int, int]]:
    if not raw_value:
        return []

    text = html.unescape(str(raw_value))
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)

    languages = []
    for chunk in re.split(r",|\n", text):
        item = chunk.strip()
        if not item:
            continue

        lower_item = item.lower()
        audio = int("full audio" in lower_item)
        subtitles = int("subtitles" in lower_item)
        cleaned = re.sub(r"\(.*?\)", "", item).strip(" -*")
        if cleaned:
            languages.append((cleaned, 1, audio, subtitles))

    deduped: Dict[str, tuple[str, int, int, int]] = {}
    for language, interface_supported, audio_supported, subtitles_supported in languages:
        key = language.lower()
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = (language, interface_supported, audio_supported, subtitles_supported)
        else:
            deduped[key] = (
                existing[0],
                max(existing[1], interface_supported),
                max(existing[2], audio_supported),
                max(existing[3], subtitles_supported),
            )

    return list(deduped.values())


def ensure_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class RetryConfig:
    max_retries: int = 5
    base_delay: float = 2.0
    backoff_multiplier: float = 2.0
    timeout: int = 30


class SteamMetadataBuilder:
    steamspy_url = "https://steamspy.com/api.php"
    appdetails_url = "https://store.steampowered.com/api/appdetails"

    def __init__(
        self,
        db_path: Path,
        retry_config: RetryConfig,
        steamspy_delay: float = 1.1,
        store_delay: float = 0.4,
        store_batch_delay: float = 8.0,
        store_batch_size: int = 25,
        price_regions: Optional[Sequence[str]] = None,
    ) -> None:
        self.db_path = db_path
        self.retry_config = retry_config
        self.steamspy_delay = steamspy_delay
        self.store_delay = store_delay
        self.store_batch_delay = store_batch_delay
        self.store_batch_size = store_batch_size
        self.price_regions = [region.lower() for region in (price_regions or ["us"])]

        ensure_directory(db_path)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "SteamRecommenderMetadataBuilder/1.0 "
                    "(https://github.com/openai/codex)"
                ),
                "Accept": "application/json,text/plain,*/*",
            }
        )

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def create_schema(self) -> None:
        with self.connect() as conn:
            cursor = conn.cursor()

            cursor.executescript(
                """
                CREATE TABLE IF NOT EXISTS sync_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    steamspy_pages_seen INTEGER NOT NULL DEFAULT 0,
                    appids_discovered INTEGER NOT NULL DEFAULT 0,
                    store_attempted INTEGER NOT NULL DEFAULT 0,
                    store_succeeded INTEGER NOT NULL DEFAULT 0,
                    error_count INTEGER NOT NULL DEFAULT 0,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS sync_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_run_id INTEGER NOT NULL,
                    appid INTEGER,
                    source TEXT NOT NULL,
                    context TEXT,
                    error_message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (sync_run_id) REFERENCES sync_runs(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS ingestion_state (
                    appid INTEGER PRIMARY KEY,
                    steamspy_fetched_at TEXT,
                    store_fetched_at TEXT,
                    last_attempt_at TEXT,
                    store_fetch_status TEXT,
                    last_error TEXT
                );

                CREATE TABLE IF NOT EXISTS raw_steamspy_games (
                    appid INTEGER PRIMARY KEY,
                    source_page INTEGER NOT NULL,
                    fetched_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS raw_steam_app_details (
                    appid INTEGER NOT NULL,
                    region_code TEXT NOT NULL DEFAULT 'us',
                    fetched_at TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (appid, region_code)
                );

                CREATE TABLE IF NOT EXISTS games (
                    appid INTEGER PRIMARY KEY,
                    name TEXT,
                    type TEXT,
                    required_age INTEGER,
                    is_free INTEGER,
                    controller_support TEXT,
                    short_description TEXT,
                    detailed_description TEXT,
                    about_the_game TEXT,
                    supported_languages TEXT,
                    header_image TEXT,
                    capsule_image TEXT,
                    website TEXT,
                    developers_json TEXT,
                    publishers_json TEXT,
                    price_currency TEXT,
                    price_initial INTEGER,
                    price_final INTEGER,
                    price_discount_percent INTEGER,
                    release_date_text TEXT,
                    release_date_is_coming_soon INTEGER,
                    release_date_parsed TEXT,
                    metacritic_score INTEGER,
                    recommendations_total INTEGER,
                    steamspy_score_rank TEXT,
                    steamspy_owners TEXT,
                    steamspy_owner_estimate INTEGER,
                    steamspy_average_forever INTEGER,
                    steamspy_median_forever INTEGER,
                    steamspy_ccu INTEGER,
                    positive INTEGER,
                    negative INTEGER,
                    estimated_review_count INTEGER,
                    has_steamspy_data INTEGER NOT NULL DEFAULT 0,
                    has_store_data INTEGER NOT NULL DEFAULT 0,
                    source_last_updated TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS game_genres (
                    appid INTEGER NOT NULL,
                    genre_id INTEGER,
                    genre_name TEXT NOT NULL,
                    PRIMARY KEY (appid, genre_name),
                    FOREIGN KEY (appid) REFERENCES games(appid) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS game_categories (
                    appid INTEGER NOT NULL,
                    category_id INTEGER,
                    category_name TEXT NOT NULL,
                    PRIMARY KEY (appid, category_name),
                    FOREIGN KEY (appid) REFERENCES games(appid) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS game_tags (
                    appid INTEGER NOT NULL,
                    tag_name TEXT NOT NULL,
                    tag_rank INTEGER,
                    tag_weight REAL,
                    source TEXT NOT NULL,
                    PRIMARY KEY (appid, tag_name, source),
                    FOREIGN KEY (appid) REFERENCES games(appid) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS game_platforms (
                    appid INTEGER PRIMARY KEY,
                    windows INTEGER NOT NULL DEFAULT 0,
                    mac INTEGER NOT NULL DEFAULT 0,
                    linux INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (appid) REFERENCES games(appid) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS game_languages (
                    appid INTEGER NOT NULL,
                    language TEXT NOT NULL,
                    interface_supported INTEGER NOT NULL DEFAULT 1,
                    audio_supported INTEGER NOT NULL DEFAULT 0,
                    subtitles_supported INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (appid, language),
                    FOREIGN KEY (appid) REFERENCES games(appid) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS game_developers (
                    appid INTEGER NOT NULL,
                    developer_name TEXT NOT NULL,
                    PRIMARY KEY (appid, developer_name),
                    FOREIGN KEY (appid) REFERENCES games(appid) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS game_publishers (
                    appid INTEGER NOT NULL,
                    publisher_name TEXT NOT NULL,
                    PRIMARY KEY (appid, publisher_name),
                    FOREIGN KEY (appid) REFERENCES games(appid) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS game_packages (
                    appid INTEGER NOT NULL,
                    package_id INTEGER NOT NULL,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (appid, package_id),
                    FOREIGN KEY (appid) REFERENCES games(appid) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS game_pricing (
                    appid INTEGER NOT NULL,
                    region_code TEXT NOT NULL,
                    currency TEXT,
                    initial INTEGER,
                    final INTEGER,
                    discount_percent INTEGER,
                    initial_formatted TEXT,
                    final_formatted TEXT,
                    is_free INTEGER NOT NULL DEFAULT 0,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (appid, region_code),
                    FOREIGN KEY (appid) REFERENCES games(appid) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS game_screenshots (
                    appid INTEGER NOT NULL,
                    screenshot_id INTEGER NOT NULL,
                    path_thumbnail TEXT,
                    path_full TEXT,
                    PRIMARY KEY (appid, screenshot_id),
                    FOREIGN KEY (appid) REFERENCES games(appid) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS game_movies (
                    appid INTEGER NOT NULL,
                    movie_id INTEGER NOT NULL,
                    name TEXT,
                    thumbnail TEXT,
                    webm_480 TEXT,
                    mp4_480 TEXT,
                    PRIMARY KEY (appid, movie_id),
                    FOREIGN KEY (appid) REFERENCES games(appid) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_games_name ON games(name);
                CREATE INDEX IF NOT EXISTS idx_games_has_store_data ON games(has_store_data);
                CREATE INDEX IF NOT EXISTS idx_games_has_steamspy_data ON games(has_steamspy_data);
                CREATE INDEX IF NOT EXISTS idx_games_release_date ON games(release_date_parsed);
                CREATE INDEX IF NOT EXISTS idx_game_tags_name ON game_tags(tag_name);
                CREATE INDEX IF NOT EXISTS idx_game_genres_name ON game_genres(genre_name);
                CREATE INDEX IF NOT EXISTS idx_game_categories_name ON game_categories(category_name);
                CREATE INDEX IF NOT EXISTS idx_game_pricing_region ON game_pricing(region_code);
                CREATE INDEX IF NOT EXISTS idx_ingestion_state_status ON ingestion_state(store_fetch_status);
                """
            )
            self._migrate_schema_if_needed(conn)

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    def _table_columns(self, conn: sqlite3.Connection, table_name: str) -> set[str]:
        if not self._table_exists(conn, table_name):
            return set()
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row["name"]) for row in rows}

    def _migrate_schema_if_needed(self, conn: sqlite3.Connection) -> None:
        raw_columns = self._table_columns(conn, "raw_steam_app_details")
        if raw_columns and "region_code" not in raw_columns:
            LOGGER.info("Migrating raw_steam_app_details to region-aware schema")
            conn.executescript(
                """
                ALTER TABLE raw_steam_app_details RENAME TO raw_steam_app_details_legacy;

                CREATE TABLE raw_steam_app_details (
                    appid INTEGER NOT NULL,
                    region_code TEXT NOT NULL DEFAULT 'us',
                    fetched_at TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (appid, region_code)
                );

                INSERT INTO raw_steam_app_details (appid, region_code, fetched_at, success, payload_json)
                SELECT appid, 'us', fetched_at, success, payload_json
                FROM raw_steam_app_details_legacy;

                DROP TABLE raw_steam_app_details_legacy;
                """
            )

        games_columns = self._table_columns(conn, "games")
        if games_columns and "steamspy_owner_estimate" not in games_columns:
            LOGGER.info("Adding games.steamspy_owner_estimate")
            conn.execute("ALTER TABLE games ADD COLUMN steamspy_owner_estimate INTEGER")

        if not self._table_exists(conn, "game_pricing"):
            LOGGER.info("Creating game_pricing table")
            conn.executescript(
                """
                CREATE TABLE game_pricing (
                    appid INTEGER NOT NULL,
                    region_code TEXT NOT NULL,
                    currency TEXT,
                    initial INTEGER,
                    final INTEGER,
                    discount_percent INTEGER,
                    initial_formatted TEXT,
                    final_formatted TEXT,
                    is_free INTEGER NOT NULL DEFAULT 0,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (appid, region_code),
                    FOREIGN KEY (appid) REFERENCES games(appid) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_game_pricing_region ON game_pricing(region_code);
                """
            )
        conn.commit()

    def _request_json(self, url: str, params: Dict[str, Any], context: str) -> Any:
        delay = self.retry_config.base_delay
        last_error: Optional[Exception] = None

        for attempt in range(1, self.retry_config.max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.retry_config.timeout)

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait_time = float(retry_after) if retry_after and retry_after.isdigit() else delay
                    LOGGER.warning("%s rate limited, waiting %.1fs (attempt %s/%s)", context, wait_time, attempt, self.retry_config.max_retries)
                    time.sleep(wait_time)
                    delay *= self.retry_config.backoff_multiplier
                    continue

                response.raise_for_status()

                if response.text.lstrip().startswith("<"):
                    raise ValueError("Received HTML instead of JSON")

                return response.json()

            except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == self.retry_config.max_retries:
                    break
                LOGGER.warning("%s failed on attempt %s/%s: %s", context, attempt, self.retry_config.max_retries, exc)
                time.sleep(delay)
                delay *= self.retry_config.backoff_multiplier

        raise RuntimeError(f"{context} failed after {self.retry_config.max_retries} attempts: {last_error}")

    def start_sync_run(self, notes: Optional[str]) -> int:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sync_runs (started_at, status, notes)
                VALUES (?, 'running', ?)
                """,
                (utcnow_iso(), notes),
            )
            return int(cursor.lastrowid)

    def finish_sync_run(
        self,
        sync_run_id: int,
        status: str,
        steamspy_pages_seen: int,
        appids_discovered: int,
        store_attempted: int,
        store_succeeded: int,
        error_count: int,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE sync_runs
                SET finished_at = ?,
                    status = ?,
                    steamspy_pages_seen = ?,
                    appids_discovered = ?,
                    store_attempted = ?,
                    store_succeeded = ?,
                    error_count = ?
                WHERE id = ?
                """,
                (
                    utcnow_iso(),
                    status,
                    steamspy_pages_seen,
                    appids_discovered,
                    store_attempted,
                    store_succeeded,
                    error_count,
                    sync_run_id,
                ),
            )

    def record_error(self, sync_run_id: int, source: str, error_message: str, appid: Optional[int] = None, context: Optional[str] = None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_errors (sync_run_id, appid, source, context, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (sync_run_id, appid, source, context, error_message, utcnow_iso()),
            )

    def fetch_steamspy_page(self, page: int) -> Dict[str, Any]:
        return self._request_json(
            self.steamspy_url,
            {"request": "all", "page": page},
            context=f"SteamSpy page {page}",
        )

    def fetch_app_details(self, appid: int, region_code: str = "us") -> Dict[str, Any]:
        return self._request_json(
            self.appdetails_url,
            {"appids": appid, "cc": region_code},
            context=f"Steam appdetails {appid} [{region_code}]",
        )

    def upsert_steamspy_games(self, page: int, games_payload: Dict[str, Any]) -> int:
        fetched_at = utcnow_iso()
        rows_written = 0

        with self.connect() as conn:
            cursor = conn.cursor()

            for raw_game in games_payload.values():
                appid = int(raw_game.get("appid", 0) or 0)
                if appid <= 0:
                    continue

                name = raw_game.get("name") or None
                owners_text = raw_game.get("owners") or None
                positive = int(raw_game.get("positive", 0) or 0)
                negative = int(raw_game.get("negative", 0) or 0)
                estimated_review_count = positive + negative

                cursor.execute(
                    """
                    INSERT INTO raw_steamspy_games (appid, source_page, fetched_at, payload_json)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(appid) DO UPDATE SET
                        source_page = excluded.source_page,
                        fetched_at = excluded.fetched_at,
                        payload_json = excluded.payload_json
                    """,
                    (appid, page, fetched_at, json_dumps(raw_game)),
                )

                cursor.execute(
                    """
                    INSERT INTO games (
                        appid, name, steamspy_score_rank, steamspy_owners,
                        steamspy_owner_estimate,
                        steamspy_average_forever, steamspy_median_forever, steamspy_ccu,
                        positive, negative, estimated_review_count,
                        has_steamspy_data, source_last_updated, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                    ON CONFLICT(appid) DO UPDATE SET
                        name = COALESCE(excluded.name, games.name),
                        steamspy_score_rank = excluded.steamspy_score_rank,
                        steamspy_owners = excluded.steamspy_owners,
                        steamspy_owner_estimate = excluded.steamspy_owner_estimate,
                        steamspy_average_forever = excluded.steamspy_average_forever,
                        steamspy_median_forever = excluded.steamspy_median_forever,
                        steamspy_ccu = excluded.steamspy_ccu,
                        positive = excluded.positive,
                        negative = excluded.negative,
                        estimated_review_count = excluded.estimated_review_count,
                        has_steamspy_data = 1,
                        source_last_updated = excluded.source_last_updated,
                        updated_at = excluded.updated_at
                    """,
                    (
                        appid,
                        name,
                        str(raw_game.get("score_rank") or ""),
                        owners_text,
                        parse_owner_estimate(owners_text),
                        int(raw_game.get("average_forever", 0) or 0),
                        int(raw_game.get("median_forever", 0) or 0),
                        int(raw_game.get("ccu", 0) or 0),
                        positive,
                        negative,
                        estimated_review_count,
                        fetched_at,
                        fetched_at,
                        fetched_at,
                    ),
                )

                self._replace_lookup_rows(
                    cursor,
                    "game_developers",
                    appid,
                    "developer_name",
                    self._split_people_field(raw_game.get("developer")),
                )
                self._replace_lookup_rows(
                    cursor,
                    "game_publishers",
                    appid,
                    "publisher_name",
                    self._split_people_field(raw_game.get("publisher")),
                )

                tags = raw_game.get("tags") or {}
                self._replace_tags(cursor, appid, tags, source="steamspy")

                cursor.execute(
                    """
                    INSERT INTO ingestion_state (appid, steamspy_fetched_at)
                    VALUES (?, ?)
                    ON CONFLICT(appid) DO UPDATE SET steamspy_fetched_at = excluded.steamspy_fetched_at
                    """,
                    (appid, fetched_at),
                )

                rows_written += 1

        return rows_written

    def _split_people_field(self, value: Any) -> List[str]:
        if not value:
            return []
        if isinstance(value, list):
            raw_values = [str(item).strip() for item in value if str(item).strip()]
        else:
            raw_values = [piece.strip() for piece in str(value).split(",") if piece.strip()]

        deduped: List[str] = []
        seen = set()
        for item in raw_values:
            normalized = item.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(item)
        return deduped

    def _replace_lookup_rows(
        self,
        cursor: sqlite3.Cursor,
        table_name: str,
        appid: int,
        value_column: str,
        values: Sequence[str],
    ) -> None:
        cursor.execute(f"DELETE FROM {table_name} WHERE appid = ?", (appid,))
        if not values:
            return
        cursor.executemany(
            f"INSERT INTO {table_name} (appid, {value_column}) VALUES (?, ?)",
            [(appid, value) for value in values],
        )

    def _replace_tags(self, cursor: sqlite3.Cursor, appid: int, tags: Dict[str, Any], source: str) -> None:
        cursor.execute("DELETE FROM game_tags WHERE appid = ? AND source = ?", (appid, source))
        if not isinstance(tags, dict):
            return

        tag_rows = []
        for rank, (tag_name, tag_weight) in enumerate(sorted(tags.items(), key=lambda item: item[1], reverse=True), start=1):
            try:
                numeric_weight = float(tag_weight)
            except (TypeError, ValueError):
                numeric_weight = None
            tag_rows.append((appid, str(tag_name), rank, numeric_weight, source))

        cursor.executemany(
            """
            INSERT INTO game_tags (appid, tag_name, tag_rank, tag_weight, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            tag_rows,
        )

    def _replace_simple_join(self, cursor: sqlite3.Cursor, table_name: str, appid: int, rows: Iterable[Sequence[Any]]) -> None:
        cursor.execute(f"DELETE FROM {table_name} WHERE appid = ?", (appid,))
        seen: set[tuple] = set()
        deduped = []
        for row in rows:
            key = tuple(row)
            if key not in seen:
                seen.add(key)
                deduped.append(row)
        if deduped:
            placeholders = {
                "game_genres": "(appid, genre_id, genre_name)",
                "game_categories": "(appid, category_id, category_name)",
                "game_languages": "(appid, language, interface_supported, audio_supported, subtitles_supported)",
                "game_packages": "(appid, package_id, is_default)",
                "game_screenshots": "(appid, screenshot_id, path_thumbnail, path_full)",
                "game_movies": "(appid, movie_id, name, thumbnail, webm_480, mp4_480)",
            }[table_name]
            cursor.executemany(f"INSERT INTO {table_name} {placeholders} VALUES ({','.join('?' for _ in deduped[0])})", deduped)

    def _upsert_price_row(
        self,
        cursor: sqlite3.Cursor,
        appid: int,
        region_code: str,
        price: Dict[str, Any],
        fetched_at: str,
        is_free: bool,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO game_pricing (
                appid, region_code, currency, initial, final, discount_percent,
                initial_formatted, final_formatted, is_free, fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(appid, region_code) DO UPDATE SET
                currency = excluded.currency,
                initial = excluded.initial,
                final = excluded.final,
                discount_percent = excluded.discount_percent,
                initial_formatted = excluded.initial_formatted,
                final_formatted = excluded.final_formatted,
                is_free = excluded.is_free,
                fetched_at = excluded.fetched_at
            """,
            (
                appid,
                region_code,
                price.get("currency"),
                price.get("initial"),
                price.get("final"),
                price.get("discount_percent"),
                price.get("initial_formatted"),
                price.get("final_formatted"),
                int(is_free),
                fetched_at,
            ),
        )

    def upsert_store_details(self, appid: int, payload: Dict[str, Any], region_code: str = "us") -> bool:
        fetched_at = utcnow_iso()
        app_wrapper = payload.get(str(appid), {})
        success = bool(app_wrapper.get("success"))
        app_data = app_wrapper.get("data") or {}

        with self.connect() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO raw_steam_app_details (appid, region_code, fetched_at, success, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(appid, region_code) DO UPDATE SET
                    fetched_at = excluded.fetched_at,
                    success = excluded.success,
                    payload_json = excluded.payload_json
                """,
                (appid, region_code, fetched_at, int(success), json_dumps(payload)),
            )

            if region_code == "us":
                cursor.execute(
                    """
                    INSERT INTO ingestion_state (appid, store_fetched_at, last_attempt_at, store_fetch_status, last_error)
                    VALUES (?, ?, ?, ?, NULL)
                    ON CONFLICT(appid) DO UPDATE SET
                        store_fetched_at = excluded.store_fetched_at,
                        last_attempt_at = excluded.last_attempt_at,
                        store_fetch_status = excluded.store_fetch_status,
                        last_error = NULL
                    """,
                    (appid, fetched_at, fetched_at, "success" if success else "not_available"),
                )

            if not success:
                return False

            name = app_data.get("name") or None
            release_data = app_data.get("release_date") or {}
            price = app_data.get("price_overview") or {}
            metacritic = app_data.get("metacritic") or {}
            recommendations = app_data.get("recommendations") or {}
            developers = app_data.get("developers") or []
            publishers = app_data.get("publishers") or []
            is_free = bool(app_data.get("is_free"))

            self._upsert_price_row(cursor, appid, region_code, price, fetched_at, is_free)

            if region_code != "us":
                return True

            cursor.execute(
                """
                INSERT INTO games (
                    appid, name, type, required_age, is_free, controller_support,
                    short_description, detailed_description, about_the_game,
                    supported_languages, header_image, capsule_image, website,
                    developers_json, publishers_json, price_currency,
                    price_initial, price_final, price_discount_percent,
                    release_date_text, release_date_is_coming_soon, release_date_parsed,
                    metacritic_score, recommendations_total, has_store_data,
                    source_last_updated, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(appid) DO UPDATE SET
                    name = COALESCE(excluded.name, games.name),
                    type = excluded.type,
                    required_age = excluded.required_age,
                    is_free = excluded.is_free,
                    controller_support = excluded.controller_support,
                    short_description = excluded.short_description,
                    detailed_description = excluded.detailed_description,
                    about_the_game = excluded.about_the_game,
                    supported_languages = excluded.supported_languages,
                    header_image = excluded.header_image,
                    capsule_image = excluded.capsule_image,
                    website = excluded.website,
                    developers_json = excluded.developers_json,
                    publishers_json = excluded.publishers_json,
                    price_currency = excluded.price_currency,
                    price_initial = excluded.price_initial,
                    price_final = excluded.price_final,
                    price_discount_percent = excluded.price_discount_percent,
                    release_date_text = excluded.release_date_text,
                    release_date_is_coming_soon = excluded.release_date_is_coming_soon,
                    release_date_parsed = excluded.release_date_parsed,
                    metacritic_score = excluded.metacritic_score,
                    recommendations_total = excluded.recommendations_total,
                    has_store_data = 1,
                    source_last_updated = excluded.source_last_updated,
                    updated_at = excluded.updated_at
                """,
                (
                    appid,
                    name,
                    app_data.get("type"),
                    int(app_data.get("required_age", 0) or 0),
                    int(is_free),
                    app_data.get("controller_support"),
                    app_data.get("short_description"),
                    app_data.get("detailed_description"),
                    app_data.get("about_the_game"),
                    app_data.get("supported_languages"),
                    app_data.get("header_image"),
                    app_data.get("capsule_image"),
                    app_data.get("website"),
                    json_dumps(developers),
                    json_dumps(publishers),
                    price.get("currency"),
                    price.get("initial"),
                    price.get("final"),
                    price.get("discount_percent"),
                    release_data.get("date"),
                    int(bool(release_data.get("coming_soon"))),
                    parse_release_date(release_data.get("date", "")),
                    metacritic.get("score"),
                    recommendations.get("total"),
                    fetched_at,
                    fetched_at,
                    fetched_at,
                ),
            )

            self._replace_lookup_rows(cursor, "game_developers", appid, "developer_name", developers)
            self._replace_lookup_rows(cursor, "game_publishers", appid, "publisher_name", publishers)

            genres = (
                (appid, genre.get("id"), genre.get("description"))
                for genre in app_data.get("genres", [])
                if isinstance(genre, dict) and genre.get("description")
            )
            self._replace_simple_join(cursor, "game_genres", appid, genres)

            categories = (
                (appid, category.get("id"), category.get("description"))
                for category in app_data.get("categories", [])
                if isinstance(category, dict) and category.get("description")
            )
            self._replace_simple_join(cursor, "game_categories", appid, categories)

            cursor.execute("DELETE FROM game_platforms WHERE appid = ?", (appid,))
            platforms = app_data.get("platforms") or {}
            cursor.execute(
                """
                INSERT INTO game_platforms (appid, windows, mac, linux)
                VALUES (?, ?, ?, ?)
                """,
                (
                    appid,
                    int(bool(platforms.get("windows"))),
                    int(bool(platforms.get("mac"))),
                    int(bool(platforms.get("linux"))),
                ),
            )

            packages = ((appid, int(package_id), 0) for package_id in app_data.get("packages", []) if package_id)
            self._replace_simple_join(cursor, "game_packages", appid, packages)

            languages = (
                (appid, language, interface_supported, audio_supported, subtitles_supported)
                for language, interface_supported, audio_supported, subtitles_supported
                in parse_supported_languages(app_data.get("supported_languages"))
            )
            self._replace_simple_join(cursor, "game_languages", appid, languages)

            screenshots = (
                (appid, int(shot.get("id")), shot.get("path_thumbnail"), shot.get("path_full"))
                for shot in app_data.get("screenshots", [])
                if isinstance(shot, dict) and shot.get("id") is not None
            )
            self._replace_simple_join(cursor, "game_screenshots", appid, screenshots)

            movies = (
                (
                    appid,
                    int(movie.get("id")),
                    movie.get("name"),
                    movie.get("thumbnail"),
                    (movie.get("webm") or {}).get("480"),
                    (movie.get("mp4") or {}).get("480"),
                )
                for movie in app_data.get("movies", [])
                if isinstance(movie, dict) and movie.get("id") is not None
            )
            self._replace_simple_join(cursor, "game_movies", appid, movies)

        return True

    def mark_store_failure(self, appid: int, error_message: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO ingestion_state (appid, last_attempt_at, store_fetch_status, last_error)
                VALUES (?, ?, 'failed', ?)
                ON CONFLICT(appid) DO UPDATE SET
                    last_attempt_at = excluded.last_attempt_at,
                    store_fetch_status = excluded.store_fetch_status,
                    last_error = excluded.last_error
                """,
                (appid, utcnow_iso(), error_message[:1000]),
            )

    def _batched(self, items: Sequence[int], batch_size: int) -> Iterable[List[int]]:
        for start in range(0, len(items), batch_size):
            yield list(items[start:start + batch_size])

    def load_appids_for_store_enrichment(self, limit: Optional[int], refresh_store: bool) -> List[int]:
        query = """
            SELECT appid
            FROM games
            WHERE has_steamspy_data = 1
        """
        params: List[Any] = []

        if not refresh_store:
            query += " AND has_store_data = 0"

        query += " ORDER BY appid"

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self.connect() as conn:
            return [int(row["appid"]) for row in conn.execute(query, params)]

    def get_next_steamspy_page(self) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(source_page), -1) AS max_page FROM raw_steamspy_games"
            ).fetchone()
            return int(row["max_page"]) + 1

    def collect_steamspy_catalog(
        self,
        sync_run_id: int,
        limit: Optional[int],
        page_limit: Optional[int],
        resume: bool,
    ) -> tuple[int, int, int]:
        page = self.get_next_steamspy_page() if resume else 0
        total_pages = 0
        total_games = 0
        total_errors = 0

        while True:
            if page_limit is not None and page >= page_limit:
                break
            if limit is not None and total_games >= limit:
                break

            try:
                payload = self.fetch_steamspy_page(page)
            except Exception as exc:
                total_errors += 1
                self.record_error(sync_run_id, source="steamspy", error_message=str(exc), context=f"page={page}")
                LOGGER.error("SteamSpy page %s failed: %s", page, exc)
                break

            if not payload:
                break

            if limit is not None:
                remaining = limit - total_games
                trimmed_items = list(payload.items())[:remaining]
                payload = {key: value for key, value in trimmed_items}

            written = self.upsert_steamspy_games(page, payload)
            total_pages += 1
            total_games += written
            LOGGER.info("SteamSpy page %s saved %s apps (total=%s)", page, written, total_games)

            page += 1
            time.sleep(self.steamspy_delay)

        return total_pages, total_games, total_errors

    def enrich_store_metadata(self, sync_run_id: int, limit: Optional[int], refresh_store: bool) -> tuple[int, int, int]:
        appids = self.load_appids_for_store_enrichment(limit=limit, refresh_store=refresh_store)
        attempted = 0
        succeeded = 0
        errors = 0

        LOGGER.info("Store enrichment queue size: %s", len(appids))

        for index, appid in enumerate(appids, start=1):
            attempted += 1
            try:
                us_payload = self.fetch_app_details(appid, region_code="us")
                success = self.upsert_store_details(appid, us_payload, region_code="us")

                if success:
                    for region_code in self.price_regions:
                        if region_code == "us":
                            continue
                        regional_payload = self.fetch_app_details(appid, region_code=region_code)
                        self.upsert_store_details(appid, regional_payload, region_code=region_code)
                    succeeded += 1

                LOGGER.info("Store %s/%s appid=%s success=%s", index, len(appids), appid, success)
            except Exception as exc:
                errors += 1
                self.mark_store_failure(appid, str(exc))
                self.record_error(sync_run_id, source="steam_store", error_message=str(exc), appid=appid)
                LOGGER.error("Store enrichment failed for appid %s: %s", appid, exc)

            if index % self.store_batch_size == 0:
                time.sleep(self.store_batch_delay)
            else:
                time.sleep(self.store_delay)

        return attempted, succeeded, errors

    def build(
        self,
        limit: Optional[int],
        page_limit: Optional[int],
        skip_store: bool,
        refresh_store: bool,
        resume: bool,
        notes: Optional[str],
    ) -> int:
        self.create_schema()
        sync_run_id = self.start_sync_run(notes=notes)

        steamspy_pages_seen = 0
        appids_discovered = 0
        store_attempted = 0
        store_succeeded = 0
        error_count = 0
        status = "completed"

        try:
            steamspy_pages_seen, appids_discovered, steamspy_errors = self.collect_steamspy_catalog(
                sync_run_id=sync_run_id,
                limit=limit,
                page_limit=page_limit,
                resume=resume,
            )
            error_count += steamspy_errors

            if not skip_store:
                store_attempted, store_succeeded, store_errors = self.enrich_store_metadata(
                    sync_run_id=sync_run_id,
                    limit=limit,
                    refresh_store=refresh_store,
                )
                error_count += store_errors

            if error_count > 0:
                status = "completed_with_errors"
            return 0 if error_count == 0 else 2

        except KeyboardInterrupt:
            status = "interrupted"
            LOGGER.warning("Interrupted by user")
            return 130
        except Exception as exc:
            status = "failed"
            error_count += 1
            self.record_error(sync_run_id, source="builder", error_message=str(exc))
            LOGGER.exception("Metadata build failed")
            return 1
        finally:
            self.finish_sync_run(
                sync_run_id=sync_run_id,
                status=status,
                steamspy_pages_seen=steamspy_pages_seen,
                appids_discovered=appids_discovered,
                store_attempted=store_attempted,
                store_succeeded=store_succeeded,
                error_count=error_count,
            )


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


if __name__ == "__main__":
    sys.exit(main())
