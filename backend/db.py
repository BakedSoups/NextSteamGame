from __future__ import annotations

import json
import sqlite3
from difflib import SequenceMatcher
from pathlib import Path
import re


class FinalGameStore:
    def __init__(self, db_path: Path, metadata_db_path: Path | None = None) -> None:
        self.db_path = db_path
        self.metadata_db_path = metadata_db_path or db_path
        self._search_index = self._load_search_index()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _connect_metadata(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.metadata_db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _load_search_index(self) -> list[dict]:
        with self._connect_metadata() as connection:
            rows = connection.execute(
                """
                SELECT appid, name
                FROM games
                WHERE has_store_data = 1
                  AND name IS NOT NULL
                  AND trim(name) <> ''
                ORDER BY appid
                """
            ).fetchall()
        return [
            {
                "appid": int(row["appid"]),
                "name": row["name"],
                "normalized_name": self._normalize_search_text(row["name"]),
            }
            for row in rows
        ]

    @staticmethod
    def _normalize_search_text(text: str) -> str:
        lowered = text.lower()
        lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
        return " ".join(lowered.split())

    def _score_search_match(self, query: str, normalized_query: str, candidate: dict) -> float:
        name = candidate["name"]
        normalized_name = candidate["normalized_name"]

        if normalized_name == normalized_query:
            return 10_000.0

        score = 0.0
        if normalized_name.startswith(normalized_query):
            score += 500.0
        if normalized_query in normalized_name:
            score += 250.0

        query_tokens = normalized_query.split()
        name_tokens = normalized_name.split()
        token_hits = sum(1 for token in query_tokens if token in name_tokens)
        partial_hits = sum(1 for token in query_tokens if token and token in normalized_name)
        score += token_hits * 80.0
        score += partial_hits * 35.0

        ratio = SequenceMatcher(None, normalized_query, normalized_name).ratio()
        score += ratio * 100.0

        compact_ratio = SequenceMatcher(None, query.lower(), name.lower()).ratio()
        score += compact_ratio * 40.0

        score -= len(name) * 0.03
        return score

    def search_games(self, query: str, limit: int = 12) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        normalized_query = self._normalize_search_text(query)
        if not normalized_query:
            return []

        scored = []
        for candidate in self._search_index:
            score = self._score_search_match(query, normalized_query, candidate)
            if score <= 0:
                continue
            scored.append((score, candidate))

        scored.sort(key=lambda item: (-item[0], len(item[1]["name"]), item[1]["name"].lower()))
        return [
            {"appid": candidate["appid"], "name": candidate["name"]}
            for _, candidate in scored[:limit]
        ]

    def get_game(self, appid: int) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT appid, name, canonical_vectors_json, canonical_metadata_json
                FROM canonical_game_semantics
                WHERE appid = ?
                """,
                (appid,),
            ).fetchone()
        if row is None:
            return None
        return {
            "appid": int(row["appid"]),
            "name": row["name"],
            "vectors": json.loads(row["canonical_vectors_json"]),
            "metadata": json.loads(row["canonical_metadata_json"]),
        }

    def load_all_games(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT appid, name, canonical_vectors_json, canonical_metadata_json
                FROM canonical_game_semantics
                ORDER BY appid
                """
            ).fetchall()
        return [
            {
                "appid": int(row["appid"]),
                "name": row["name"],
                "vectors": json.loads(row["canonical_vectors_json"]),
                "metadata": json.loads(row["canonical_metadata_json"]),
            }
            for row in rows
        ]
