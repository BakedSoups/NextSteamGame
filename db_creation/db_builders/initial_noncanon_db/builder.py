#!/usr/bin/env python3
"""
Build the initial non-canonical semantic database for Steam games.

This stage stores the raw output of the current vectorizer pipeline:
- selected review samples
- semantic vectors
- metadata (genre spine + identity metadata)

Later stages can read this database and build canonical tag mappings on top of
it without losing the original model output.
"""

from __future__ import annotations

import json
import os
import queue
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from noncanon_pipeline.pipeline import build_game_output, build_skipped_profile, load_insightful_words
from noncanon_pipeline.llm.errors import CreditsExhaustedError, NoReviewsError
from noncanon_pipeline.llm.game_semantics import get_semantics_retry_stats, reset_semantics_retry_stats
from noncanon_pipeline.progress import advance_appid, complete_appid, fail_appid, log_banner, log_stage, update_status


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class InitialNoncanonDbBuilder:
    WRITE_BATCH_SIZE = 20
    WRITE_IDLE_FLUSH_SECONDS = 3.0
    RESULT_QUEUE_MAXSIZE = 500

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
        runtime_state: Dict[str, int],
        runtime_lock: threading.Lock,
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
                with runtime_lock:
                    runtime_state["active_workers"] += 1
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
            except NoReviewsError as exc:
                result_queue.put(
                    {
                        "kind": "no_reviews",
                        "appid": appid,
                        "game_name": game_name,
                        "error": str(exc),
                        "status": exc.status,
                        "profile": {
                            "appid": appid,
                            **build_skipped_profile(exc.status),
                        },
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
                with runtime_lock:
                    runtime_state["active_workers"] = max(0, runtime_state["active_workers"] - 1)
                task_queue.task_done()

    def _writer_loop(
        self,
        result_queue: queue.Queue,
        writer_summary: Dict[str, int],
        writer_errors: List[BaseException],
        runtime_state: Dict[str, int],
        runtime_lock: threading.Lock,
    ) -> None:
        pending_profiles: List[Dict] = []
        last_flush_at = time.monotonic()

        def flush_pending_profiles() -> None:
            nonlocal pending_profiles, last_flush_at
            if not pending_profiles:
                return
            log_stage("sqlite", detail=f"writing batch size={len(pending_profiles)}")
            with runtime_lock:
                runtime_state["sqlite_pending"] = len(pending_profiles)
            for entry in pending_profiles:
                advance_appid(entry["appid"], "sqlite", "arrived at sqlite writer")
            self.store_profiles(pending_profiles)
            for entry in pending_profiles:
                complete_appid(entry["appid"], detail=entry["game_name"])
            pending_profiles = []
            last_flush_at = time.monotonic()
            with runtime_lock:
                runtime_state["sqlite_pending"] = 0

        try:
            while True:
                try:
                    result = result_queue.get(timeout=1.0)
                except queue.Empty:
                    if pending_profiles and (time.monotonic() - last_flush_at) >= self.WRITE_IDLE_FLUSH_SECONDS:
                        flush_pending_profiles()
                    continue
                try:
                    if result is None:
                        flush_pending_profiles()
                        return

                    writer_summary["processed_results"] += 1

                    if result["kind"] == "skipped":
                        continue

                    if result["kind"] == "no_reviews":
                        log_stage("skip", appid=result["appid"], detail=f"{result['game_name']} :: {result['error']}")
                        writer_summary["attempted_games"] += 1
                        writer_summary["completed_games"] += 1
                        writer_summary["skip_count"] += 1
                        writer_summary["no_review_count"] += 1
                        status = str(result.get("status", "")).strip()
                        if status == "no_reviews":
                            writer_summary["no_reviews_count"] += 1
                        elif status == "no_reviews_after_filtering":
                            writer_summary["no_reviews_after_filtering_count"] += 1
                        elif status == "no_insightful_reviews":
                            writer_summary["no_insightful_reviews_count"] += 1
                        pending_profiles.append(
                            {
                                "appid": int(result["appid"]),
                                "game_name": str(result["game_name"]),
                                "profile": result["profile"],
                            }
                        )
                        if len(pending_profiles) >= self.WRITE_BATCH_SIZE:
                            flush_pending_profiles()
                        continue

                    writer_summary["attempted_games"] += 1
                    appid = int(result["appid"])
                    game_name = str(result["game_name"])

                    if result["kind"] == "success":
                        log_stage("queue", appid=appid, detail="ready for sqlite")
                        profile_status = str(
                            ((result.get("profile") or {}).get("metadata") or {}).get("status", "")
                        ).strip()
                        if profile_status:
                            writer_summary["skip_count"] += 1
                            if profile_status == "no_steam_review":
                                writer_summary["no_steam_review_count"] += 1
                        pending_profiles.append(
                            {
                                "appid": appid,
                                "game_name": game_name,
                                "profile": result["profile"],
                            }
                        )
                        writer_summary["completed_games"] += 1
                        if len(pending_profiles) >= self.WRITE_BATCH_SIZE:
                            flush_pending_profiles()
                        continue

                    flush_pending_profiles()
                    writer_summary["error_count"] += 1

                    if result["kind"] == "quota_exhausted":
                        writer_summary["status"] = "paused_quota_exhausted"
                        log_stage("quota", appid=appid, detail=f"{game_name} :: {result['error']}")
                        fail_appid(appid, detail=f"quota_exhausted :: {game_name}")
                    else:
                        log_stage("error", appid=appid, detail=f"{game_name} :: {result['error']}")
                        fail_appid(appid, detail=f"error :: {game_name}")

                    self.record_error(writer_summary["run_id"], appid, game_name, str(result["error"]))
                finally:
                    result_queue.task_done()
        except BaseException as exc:
            writer_errors.append(exc)

    def _build_with_workers(self, rows: List[sqlite3.Row], insightful_words: Dict, run_id: int) -> Dict[str, int | str]:
        task_queue: queue.Queue = queue.Queue()
        result_queue: queue.Queue = queue.Queue(maxsize=self.RESULT_QUEUE_MAXSIZE)
        stop_event = threading.Event()
        monitor_stop_event = threading.Event()
        workers: List[threading.Thread] = []
        writer_errors: List[BaseException] = []
        runtime_lock = threading.Lock()
        runtime_state: Dict[str, int] = {
            "active_workers": 0,
            "sqlite_pending": 0,
        }
        writer_summary: Dict[str, int | str] = {
            "run_id": run_id,
            "attempted_games": 0,
            "completed_games": 0,
            "error_count": 0,
            "skip_count": 0,
            "no_review_count": 0,
            "no_reviews_count": 0,
            "no_reviews_after_filtering_count": 0,
            "no_insightful_reviews_count": 0,
            "no_steam_review_count": 0,
            "processed_results": 0,
            "status": "completed",
        }

        for row in rows:
            task_queue.put(row)

        worker_count = min(self.max_workers, max(1, len(rows)))
        log_stage("setup", detail=f"starting worker pool with {worker_count} workers")
        for _ in range(worker_count):
            task_queue.put(None)
            worker = threading.Thread(
                target=self._worker_loop,
                args=(task_queue, result_queue, insightful_words, stop_event, runtime_state, runtime_lock),
                daemon=True,
            )
            worker.start()
            workers.append(worker)

        log_stage("setup", detail="starting SQLite writer thread")
        writer = threading.Thread(
            target=self._writer_loop,
            args=(result_queue, writer_summary, writer_errors, runtime_state, runtime_lock),
            daemon=True,
        )
        writer.start()

        def monitor_loop() -> None:
            while not monitor_stop_event.is_set():
                with runtime_lock:
                    active_workers = runtime_state["active_workers"]
                    sqlite_pending = runtime_state["sqlite_pending"]
                retry_stats = get_semantics_retry_stats()
                update_status(
                    "remaining="
                    f"{task_queue.qsize()} "
                    f"in_flight={active_workers} "
                    f"writer_queue={result_queue.qsize()} "
                    f"sqlite_pending={sqlite_pending} "
                    f"stored={writer_summary['completed_games']} "
                    f"skips={writer_summary['skip_count']} "
                    f"no_reviews={writer_summary['no_reviews_count']} "
                    f"filtered_out={writer_summary['no_reviews_after_filtering_count']} "
                    f"no_insight={writer_summary['no_insightful_reviews_count']} "
                    f"no_steam={writer_summary['no_steam_review_count']} "
                    f"sem_retries={retry_stats.get('total', 0)} "
                    f"errors={writer_summary['error_count']}"
                )
                time.sleep(1.0)

        monitor = threading.Thread(target=monitor_loop, daemon=True)
        monitor.start()

        for worker in workers:
            worker.join()
        stop_event.set()

        result_queue.put(None)
        writer.join()
        monitor_stop_event.set()
        monitor.join(timeout=1.0)

        if writer_errors:
            raise writer_errors[0]

        return {
            "attempted_games": int(writer_summary["attempted_games"]),
            "completed_games": int(writer_summary["completed_games"]),
            "error_count": int(writer_summary["error_count"]),
            "skip_count": int(writer_summary["skip_count"]),
            "no_review_count": int(writer_summary["no_review_count"]),
            "no_reviews_count": int(writer_summary["no_reviews_count"]),
            "no_reviews_after_filtering_count": int(writer_summary["no_reviews_after_filtering_count"]),
            "no_insightful_reviews_count": int(writer_summary["no_insightful_reviews_count"]),
            "no_steam_review_count": int(writer_summary["no_steam_review_count"]),
            "semantics_retry_count": int(get_semantics_retry_stats().get("total", 0)),
            "status": str(writer_summary["status"]),
        }

    def build(self, limit: Optional[int] = None, notes: Optional[str] = None) -> Dict:
        log_banner("Initial Non-Canonical DB Build")
        log_stage("setup", detail="preparing non-canon DB schema")
        self.create_schema()
        log_stage("setup", detail="loading insightful words")
        insightful_words = load_insightful_words()
        reset_semantics_retry_stats()
        log_stage("setup", detail="counting existing stored profiles")
        existing_profiles = self.count_existing_profiles()

        log_stage("setup", detail="starting run record")
        run_id = self.start_run(notes=notes)
        attempted_games = 0
        completed_games = 0
        error_count = 0
        status = "completed"

        try:
            log_stage("setup", detail="loading candidate games from metadata DB")
            rows = self.load_games(limit=limit)
            log_stage("setup", detail=f"queued {len(rows)} games after resume filtering")
            if not rows:
                log_stage("setup", detail="no new games to process")
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
            "skip_count": int(summary["skip_count"]) if 'summary' in locals() else 0,
            "no_review_count": int(summary["no_review_count"]) if 'summary' in locals() else 0,
            "no_reviews_count": int(summary["no_reviews_count"]) if 'summary' in locals() else 0,
            "no_reviews_after_filtering_count": int(summary["no_reviews_after_filtering_count"]) if 'summary' in locals() else 0,
            "no_insightful_reviews_count": int(summary["no_insightful_reviews_count"]) if 'summary' in locals() else 0,
            "no_steam_review_count": int(summary["no_steam_review_count"]) if 'summary' in locals() else 0,
            "semantics_retry_count": int(summary["semantics_retry_count"]) if 'summary' in locals() else 0,
            "output_db_path": str(self.output_db_path),
        }
