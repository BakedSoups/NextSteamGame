#!/usr/bin/env python3
"""
Build the initial non-canonical semantic database for Steam games.

This stage stores the raw output of the current vectorizer pipeline:
- selected review samples
- semantic vectors
- metadata (micro_tags + genre_tree)

Later stages can read this database and build canonical tag mappings on top of
it without losing the original model output.
"""

from __future__ import annotations

import json
import os
import queue
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from noncanon_pipeline.pipeline import build_game_output, load_insightful_words
from noncanon_pipeline.llm.errors import CreditsExhaustedError


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class InitialNoncanonDbBuilder:
    WRITE_BATCH_SIZE = 100

    def __init__(
        self,
        metadata_db_path: Path,
        output_db_path: Path,
        max_workers: Optional[int] = None,
    ) -> None:
        self.metadata_db_path = metadata_db_path
        self.output_db_path = output_db_path
        self.output_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_workers = max(1, max_workers or min(4, (os.cpu_count() or 2)))

    def metadata_conn(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.metadata_db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def output_conn(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.output_db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def create_schema(self) -> None:
        with self.output_conn() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS noncanon_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    attempted_games INTEGER NOT NULL DEFAULT 0,
                    completed_games INTEGER NOT NULL DEFAULT 0,
                    error_count INTEGER NOT NULL DEFAULT 0,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS raw_game_semantics (
                    appid INTEGER PRIMARY KEY,
                    name TEXT,
                    review_samples_json TEXT NOT NULL,
                    vectors_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS noncanon_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    appid INTEGER,
                    game_name TEXT,
                    error_message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES noncanon_runs(id) ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_raw_game_semantics_name
                ON raw_game_semantics(name);
                """
            )

    def start_run(self, notes: Optional[str] = None) -> int:
        with self.output_conn() as connection:
            cursor = connection.execute(
                """
                INSERT INTO noncanon_runs (started_at, status, notes)
                VALUES (?, 'running', ?)
                """,
                (utcnow_iso(), notes),
            )
            return int(cursor.lastrowid)

    def finish_run(
        self,
        run_id: int,
        status: str,
        attempted_games: int,
        completed_games: int,
        error_count: int,
    ) -> None:
        with self.output_conn() as connection:
            connection.execute(
                """
                UPDATE noncanon_runs
                SET finished_at = ?,
                    status = ?,
                    attempted_games = ?,
                    completed_games = ?,
                    error_count = ?
                WHERE id = ?
                """,
                (utcnow_iso(), status, attempted_games, completed_games, error_count, run_id),
            )

    def record_error(self, run_id: int, appid: int, game_name: str, error_message: str) -> None:
        with self.output_conn() as connection:
            connection.execute(
                """
                INSERT INTO noncanon_errors (run_id, appid, game_name, error_message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, appid, game_name, error_message[:2000], utcnow_iso()),
            )

    def load_existing_appids(self) -> set[int]:
        with self.output_conn() as connection:
            rows = connection.execute("SELECT appid FROM raw_game_semantics").fetchall()
        return {int(row["appid"]) for row in rows}

    def load_games(self, limit: Optional[int] = None) -> List[sqlite3.Row]:
        query = """
            SELECT appid, name
            FROM games
            WHERE has_store_data = 1
            ORDER BY appid
        """
        params: List[object] = []
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self.metadata_conn() as connection:
            rows = list(connection.execute(query, params))

        existing_appids = self.load_existing_appids()
        filtered_rows = [row for row in rows if int(row["appid"]) not in existing_appids]
        return filtered_rows

    def count_existing_profiles(self) -> int:
        with self.output_conn() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM raw_game_semantics").fetchone()
        return int(row["count"])

    def store_profile(self, appid: int, game_name: str, profile: Dict) -> None:
        self.store_profiles(
            [
                {
                    "appid": appid,
                    "game_name": game_name,
                    "profile": profile,
                }
            ]
        )

    def store_profiles(self, profiles: List[Dict]) -> None:
        if not profiles:
            return

        timestamp = utcnow_iso()
        rows = [
            (
                int(entry["appid"]),
                str(entry["game_name"]),
                json.dumps(entry["profile"]["review_samples"], ensure_ascii=True, sort_keys=True),
                json.dumps(entry["profile"]["vectors"], ensure_ascii=True, sort_keys=True),
                json.dumps(entry["profile"]["metadata"], ensure_ascii=True, sort_keys=True),
                timestamp,
                timestamp,
            )
            for entry in profiles
        ]
        with self.output_conn() as connection:
            connection.executemany(
                """
                INSERT INTO raw_game_semantics (
                    appid,
                    name,
                    review_samples_json,
                    vectors_json,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(appid) DO UPDATE SET
                    name = excluded.name,
                    review_samples_json = excluded.review_samples_json,
                    vectors_json = excluded.vectors_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                rows,
            )

    def _worker_loop(
        self,
        task_queue: queue.Queue,
        result_queue: queue.Queue,
        insightful_words: Dict,
        stop_event: threading.Event,
    ) -> None:
        while True:
            try:
                row = task_queue.get(timeout=0.2)
            except queue.Empty:
                if stop_event.is_set():
                    return
                continue

            if row is None:
                task_queue.task_done()
                return

            appid = int(row["appid"])
            game_name = row["name"] or ""

            if stop_event.is_set():
                result_queue.put(
                    {
                        "kind": "skipped",
                        "appid": appid,
                        "game_name": game_name,
                    }
                )
                task_queue.task_done()
                continue

            try:
                profile = build_game_output(str(appid), insightful_words)
                result_queue.put(
                    {
                        "kind": "success",
                        "appid": appid,
                        "game_name": game_name,
                        "profile": profile,
                    }
                )
            except CreditsExhaustedError as exc:
                stop_event.set()
                result_queue.put(
                    {
                        "kind": "quota_exhausted",
                        "appid": appid,
                        "game_name": game_name,
                        "error": str(exc),
                    }
                )
            except Exception as exc:
                result_queue.put(
                    {
                        "kind": "error",
                        "appid": appid,
                        "game_name": game_name,
                        "error": str(exc),
                    }
                )
            finally:
                task_queue.task_done()

    def _build_with_workers(self, rows: List[sqlite3.Row], insightful_words: Dict, run_id: int) -> Dict[str, int | str]:
        task_queue: queue.Queue = queue.Queue()
        result_queue: queue.Queue = queue.Queue()
        stop_event = threading.Event()
        workers: List[threading.Thread] = []

        for row in rows:
            task_queue.put(row)

        worker_count = min(self.max_workers, max(1, len(rows)))
        for _ in range(worker_count):
            task_queue.put(None)
            worker = threading.Thread(
                target=self._worker_loop,
                args=(task_queue, result_queue, insightful_words, stop_event),
                daemon=True,
            )
            worker.start()
            workers.append(worker)

        attempted_games = 0
        completed_games = 0
        error_count = 0
        processed_results = 0
        status = "completed"
        pending_profiles: List[Dict] = []

        def flush_pending_profiles() -> None:
            nonlocal pending_profiles
            if not pending_profiles:
                return
            self.store_profiles(pending_profiles)
            for entry in pending_profiles:
                print(f"Stored {entry['game_name']} ({entry['appid']})")
            pending_profiles = []

        while processed_results < len(rows):
            result = result_queue.get()
            processed_results += 1

            if result["kind"] == "skipped":
                continue

            attempted_games += 1
            appid = int(result["appid"])
            game_name = str(result["game_name"])

            if result["kind"] == "success":
                pending_profiles.append(
                    {
                        "appid": appid,
                        "game_name": game_name,
                        "profile": result["profile"],
                    }
                )
                if len(pending_profiles) >= self.WRITE_BATCH_SIZE:
                    flush_pending_profiles()
                completed_games += 1
                continue

            flush_pending_profiles()
            error_count += 1
            self.record_error(run_id, appid, game_name, str(result["error"]))

            if result["kind"] == "quota_exhausted":
                print(f"Stopping run at {game_name} ({appid}): {result['error']}")
                status = "paused_quota_exhausted"
                continue

            print(f"Skipped {game_name} ({appid}): {result['error']}")

        flush_pending_profiles()
        stop_event.set()
        for worker in workers:
            worker.join()

        return {
            "attempted_games": attempted_games,
            "completed_games": completed_games,
            "error_count": error_count,
            "status": status,
        }

    def build(self, limit: Optional[int] = None, notes: Optional[str] = None) -> Dict:
        self.create_schema()
        insightful_words = load_insightful_words()
        existing_profiles = self.count_existing_profiles()

        run_id = self.start_run(notes=notes)
        attempted_games = 0
        completed_games = 0
        error_count = 0
        status = "completed"

        try:
            rows = self.load_games(limit=limit)
            summary = self._build_with_workers(rows, insightful_words, run_id)
            attempted_games = int(summary["attempted_games"])
            completed_games = int(summary["completed_games"])
            error_count = int(summary["error_count"])
            status = str(summary["status"])
        except Exception:
            status = "failed"
            raise
        finally:
            self.finish_run(
                run_id=run_id,
                status=status,
                attempted_games=attempted_games,
                completed_games=completed_games,
                error_count=error_count,
            )

        return {
            "run_id": run_id,
            "existing_profiles": existing_profiles,
            "attempted_games": attempted_games,
            "completed_games": completed_games,
            "error_count": error_count,
            "output_db_path": str(self.output_db_path),
        }
