#!/usr/bin/env python3
"""
Sequential Steam review harvester.

Fetches reviews for appids already stored in the metadata database, keeps the
most popular reviews above a minimum word count threshold, and stores the final
review list as JSON in a dedicated table.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


LOGGER = logging.getLogger("steam_review_harvester")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_db_path() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "data" / "steam_metadata.db"


class SteamReviewHarvester:
    reviews_url = "https://store.steampowered.com/appreviews/{appid}"

    def __init__(
        self,
        db_path: Path,
        max_reviews: int = 200,
        min_words: int = 100,
        request_delay: float = 0.5,
        max_pages: int = 20,
        max_retries: int = 5,
        timeout: int = 30,
    ) -> None:
        self.db_path = db_path
        self.max_reviews = max_reviews
        self.min_words = min_words
        self.request_delay = request_delay
        self.max_pages = max_pages
        self.max_retries = max_retries
        self.timeout = timeout

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.sentiment_analyzer = SentimentIntensityAnalyzer()

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "SteamReviewHarvester/1.0",
                "Accept": "application/json,text/plain,*/*",
            }
        )

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS game_reviews (
                    appid INTEGER PRIMARY KEY,
                    review_count INTEGER NOT NULL DEFAULT 0,
                    min_word_count INTEGER NOT NULL,
                    reviews_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'steam_store_reviews',
                    FOREIGN KEY (appid) REFERENCES games(appid) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS review_harvest_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    attempted_games INTEGER NOT NULL DEFAULT 0,
                    completed_games INTEGER NOT NULL DEFAULT 0,
                    error_count INTEGER NOT NULL DEFAULT 0,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS review_harvest_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    appid INTEGER,
                    error_message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES review_harvest_runs(id) ON DELETE CASCADE
                );
                """
            )

    def start_run(self, notes: Optional[str]) -> int:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO review_harvest_runs (started_at, status, notes)
                VALUES (?, 'running', ?)
                """,
                (utcnow_iso(), notes),
            )
            return int(cursor.lastrowid)

    def finish_run(self, run_id: int, status: str, attempted_games: int, completed_games: int, error_count: int) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE review_harvest_runs
                SET finished_at = ?,
                    status = ?,
                    attempted_games = ?,
                    completed_games = ?,
                    error_count = ?
                WHERE id = ?
                """,
                (utcnow_iso(), status, attempted_games, completed_games, error_count, run_id),
            )

    def record_error(self, run_id: int, appid: Optional[int], error_message: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO review_harvest_errors (run_id, appid, error_message, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, appid, error_message[:2000], utcnow_iso()),
            )

    def load_appids(self, limit: Optional[int], refresh: bool) -> List[int]:
        query = """
            SELECT g.appid
            FROM games g
            WHERE g.has_store_data = 1
        """
        params: List[Any] = []

        if not refresh:
            query += " AND NOT EXISTS (SELECT 1 FROM game_reviews gr WHERE gr.appid = g.appid)"

        query += " ORDER BY g.appid"

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self.connect() as conn:
            return [int(row["appid"]) for row in conn.execute(query, params)]

    def _request_json(self, appid: int, params: Dict[str, Any], context: str) -> Dict[str, Any]:
        url = self.reviews_url.format(appid=appid)
        delay = 2.0
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)

                if response.status_code == 429:
                    time.sleep(delay)
                    delay *= 2
                    continue

                response.raise_for_status()
                return response.json()
            except (requests.RequestException, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                LOGGER.warning("%s failed on attempt %s/%s: %s", context, attempt, self.max_retries, exc)
                time.sleep(delay)
                delay *= 2

        raise RuntimeError(f"{context} failed after {self.max_retries} attempts: {last_error}")

    def _word_count(self, text: str) -> int:
        return len(text.split())

    def _sentiment_score(self, text: str) -> float:
        return float(self.sentiment_analyzer.polarity_scores(text)["compound"])

    def _looks_like_ascii_art(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return True

        lines = [line.rstrip() for line in stripped.splitlines() if line.strip()]
        if not lines:
            return True

        long_symbol_lines = 0
        low_alpha_lines = 0
        repeated_char_lines = 0

        for line in lines:
            alpha_count = sum(1 for ch in line if ch.isalpha())
            non_space_count = sum(1 for ch in line if not ch.isspace())
            symbol_count = sum(1 for ch in line if not ch.isalnum() and not ch.isspace())

            if non_space_count >= 12 and symbol_count / max(non_space_count, 1) > 0.6:
                long_symbol_lines += 1
            if non_space_count >= 12 and alpha_count / max(non_space_count, 1) < 0.25:
                low_alpha_lines += 1
            if re.search(r"(.)\1{7,}", line):
                repeated_char_lines += 1

        if long_symbol_lines >= 2:
            return True
        if low_alpha_lines >= max(3, len(lines) // 2):
            return True
        if repeated_char_lines >= 1:
            return True

        return False

    def _popularity_score(self, review: Dict[str, Any]) -> tuple[int, int, int, int]:
        return (
            int(review.get("votes_up", 0) or 0),
            int(review.get("weighted_vote_score", 0) or 0),
            int(review.get("votes_funny", 0) or 0),
            int((review.get("author") or {}).get("playtime_forever", 0) or 0),
        )

    def fetch_popular_reviews(self, appid: int) -> List[Dict[str, Any]]:
        cursor_value = "*"
        collected: List[Dict[str, Any]] = []
        seen_recommendation_ids = set()

        for page in range(self.max_pages):
            params = {
                "json": 1,
                "cursor": cursor_value,
                "num_per_page": 100,
                "language": "english",
                "purchase_type": "all",
                "review_type": "all",
                "filter": "all",
            }
            payload = self._request_json(appid, params, context=f"reviews appid={appid} page={page + 1}")
            reviews = payload.get("reviews") or []
            if not reviews:
                break

            for review in reviews:
                recommendation_id = review.get("recommendationid")
                if recommendation_id in seen_recommendation_ids:
                    continue
                seen_recommendation_ids.add(recommendation_id)

                text = (review.get("review") or "").strip()
                word_count = self._word_count(text)
                if word_count < self.min_words:
                    continue
                if self._looks_like_ascii_art(text):
                    continue
                sentiment = self._sentiment_score(text)
                if sentiment < 0:
                    continue

                collected.append(
                    {
                        "recommendationid": recommendation_id,
                        "review": text,
                        "word_count": word_count,
                        "sentiment_compound": sentiment,
                        "votes_up": int(review.get("votes_up", 0) or 0),
                        "votes_funny": int(review.get("votes_funny", 0) or 0),
                        "weighted_vote_score": review.get("weighted_vote_score"),
                        "comment_count": int(review.get("comment_count", 0) or 0),
                        "steam_purchase": bool(review.get("steam_purchase")),
                        "received_for_free": bool(review.get("received_for_free")),
                        "written_during_early_access": bool(review.get("written_during_early_access")),
                        "voted_up": bool(review.get("voted_up")),
                        "timestamp_created": int(review.get("timestamp_created", 0) or 0),
                        "timestamp_updated": int(review.get("timestamp_updated", 0) or 0),
                        "author": {
                            "steamid": (review.get("author") or {}).get("steamid"),
                            "num_games_owned": int((review.get("author") or {}).get("num_games_owned", 0) or 0),
                            "num_reviews": int((review.get("author") or {}).get("num_reviews", 0) or 0),
                            "playtime_forever": int((review.get("author") or {}).get("playtime_forever", 0) or 0),
                            "playtime_last_two_weeks": int((review.get("author") or {}).get("playtime_last_two_weeks", 0) or 0),
                            "playtime_at_review": int((review.get("author") or {}).get("playtime_at_review", 0) or 0),
                            "last_played": int((review.get("author") or {}).get("last_played", 0) or 0),
                        },
                    }
                )

            cursor_value = payload.get("cursor")
            if not cursor_value:
                break

            time.sleep(self.request_delay)

        collected.sort(key=self._popularity_score, reverse=True)
        return collected[: self.max_reviews]

    def store_reviews(self, appid: int, reviews: List[Dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO game_reviews (appid, review_count, min_word_count, reviews_json, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(appid) DO UPDATE SET
                    review_count = excluded.review_count,
                    min_word_count = excluded.min_word_count,
                    reviews_json = excluded.reviews_json,
                    fetched_at = excluded.fetched_at
                """,
                (
                    appid,
                    len(reviews),
                    self.min_words,
                    json.dumps(reviews, ensure_ascii=True),
                    utcnow_iso(),
                ),
            )

    def harvest(self, limit: Optional[int], refresh: bool, notes: Optional[str]) -> int:
        self.create_schema()
        run_id = self.start_run(notes=notes)

        attempted_games = 0
        completed_games = 0
        error_count = 0
        status = "completed"

        try:
            appids = self.load_appids(limit=limit, refresh=refresh)
            LOGGER.info("Review harvest queue size: %s", len(appids))

            for index, appid in enumerate(appids, start=1):
                attempted_games += 1
                try:
                    reviews = self.fetch_popular_reviews(appid)
                    self.store_reviews(appid, reviews)
                    completed_games += 1
                    LOGGER.info(
                        "Reviews %s/%s appid=%s stored=%s",
                        index,
                        len(appids),
                        appid,
                        len(reviews),
                    )
                except Exception as exc:
                    error_count += 1
                    self.record_error(run_id, appid, str(exc))
                    LOGGER.error("Review harvest failed for appid %s: %s", appid, exc)

                time.sleep(self.request_delay)

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
            self.record_error(run_id, None, str(exc))
            LOGGER.exception("Review harvest failed")
            return 1
        finally:
            self.finish_run(
                run_id=run_id,
                status=status,
                attempted_games=attempted_games,
                completed_games=completed_games,
                error_count=error_count,
            )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Harvest Steam reviews into the metadata SQLite database.")
    return parser.parse_args(argv)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parse_args(argv)
    configure_logging()

    harvester = SteamReviewHarvester(
        db_path=default_db_path(),
        max_reviews=200,
        min_words=100,
        request_delay=0.5,
        max_pages=20,
        max_retries=5,
        timeout=30,
    )
    return harvester.harvest(limit=None, refresh=False, notes=None)


if __name__ == "__main__":
    sys.exit(main())
