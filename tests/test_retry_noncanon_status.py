from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from db_creation.retry_noncanon_status import load_candidates, load_review_signals, profile_status


class RetryNoncanonStatusTests(unittest.TestCase):
    def test_profile_status_handles_success_failure_and_invalid_json(self) -> None:
        self.assertEqual(profile_status(json.dumps({"music_primary": "metal"})), "ok")
        self.assertEqual(profile_status(json.dumps({"status": "no_steam_review"})), "no_steam_review")
        self.assertEqual(profile_status("not json"), "invalid_metadata")

    def test_load_candidates_filters_by_status_and_appid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "noncanon.db"
            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    """
                    CREATE TABLE raw_game_semantics (
                        appid INTEGER PRIMARY KEY,
                        name TEXT,
                        metadata_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                connection.executemany(
                    "INSERT INTO raw_game_semantics VALUES (?, ?, ?, ?)",
                    [
                        (1, "Good", "{}", "2026-01-01"),
                        (2, "Retry", '{"status":"no_steam_review"}', "2026-01-01"),
                        (3, "Filtered", '{"status":"no_reviews_after_filtering"}', "2026-01-01"),
                    ],
                )

            candidates = load_candidates(database_path, {"no_steam_review"}, None)
            self.assertEqual([int(row["appid"]) for row in candidates], [2])

            candidates = load_candidates(database_path, {"no_steam_review"}, {3})
            self.assertEqual(candidates, [])

    def test_load_review_signals_uses_larger_available_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "metadata.db"
            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    """
                    CREATE TABLE games (
                        appid INTEGER PRIMARY KEY,
                        estimated_review_count INTEGER,
                        recommendations_total INTEGER
                    )
                    """
                )
                connection.executemany(
                    "INSERT INTO games VALUES (?, ?, ?)",
                    [(1, 80, 120), (2, 500, 300), (3, None, None)],
                )

            self.assertEqual(load_review_signals(database_path), {1: 120, 2: 500, 3: 0})


if __name__ == "__main__":
    unittest.main()
