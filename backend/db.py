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
        self._metadata_signals = self._load_metadata_signals()
        self._preview_metadata = self._load_preview_metadata()
        self._canonical_preview = self._load_canonical_preview()
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
        query = """
            SELECT appid, name, canonical_vectors_json
            FROM canonical_game_semantics
            WHERE name IS NOT NULL
              AND trim(name) <> ''
            ORDER BY appid
        """

        try:
            with self._connect() as connection:
                rows = connection.execute(query).fetchall()
        except sqlite3.Error:
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
        index: list[dict] = []
        for row in rows:
            try:
                vectors = json.loads(row["canonical_vectors_json"])
            except (TypeError, ValueError, json.JSONDecodeError, KeyError):
                continue
            if not isinstance(vectors, dict):
                continue
            has_tags = any(
                (isinstance(value, dict) and len(value) > 0)
                or (isinstance(value, list) and len(value) > 0)
                or (isinstance(value, str) and value.strip())
                for value in vectors.values()
            )
            if not has_tags:
                continue
            index.append(
                {
                    "appid": int(row["appid"]),
                    "name": row["name"],
                    "normalized_name": self._normalize_search_text(row["name"]),
                }
            )
        return index

    def _load_metadata_signals(self) -> dict[int, dict]:
        query = """
            SELECT
                appid,
                metacritic_score,
                recommendations_total,
                steamspy_owner_estimate,
                steamspy_ccu,
                positive,
                negative,
                estimated_review_count,
                release_date_parsed
            FROM games
        """
        try:
            with self._connect_metadata() as connection:
                rows = connection.execute(query).fetchall()
        except sqlite3.Error:
            return {}

        return {
            int(row["appid"]): {
                "metacritic_score": row["metacritic_score"],
                "recommendations_total": row["recommendations_total"],
                "steamspy_owner_estimate": row["steamspy_owner_estimate"],
                "steamspy_ccu": row["steamspy_ccu"],
                "positive": row["positive"],
                "negative": row["negative"],
                "estimated_review_count": row["estimated_review_count"],
                "release_date_parsed": row["release_date_parsed"],
            }
            for row in rows
        }

    def _load_preview_metadata(self) -> dict[int, dict]:
        query = """
            SELECT
                appid,
                short_description,
                header_image,
                capsule_image,
                capsule_imagev5,
                background_image,
                background_image_raw,
                logo_image,
                icon_image,
                library_hero_image,
                library_capsule_image,
                developers_json,
                publishers_json,
                release_date_text
            FROM games
        """
        try:
            with self._connect_metadata() as connection:
                rows = connection.execute(query).fetchall()
        except sqlite3.Error:
            return {}

        previews: dict[int, dict] = {}
        for row in rows:
            def _load_json_list(raw: str | None) -> list[str]:
                if not raw:
                    return []
                try:
                    parsed = json.loads(raw)
                except (TypeError, ValueError, json.JSONDecodeError):
                    return []
                return [str(item) for item in parsed if str(item).strip()]

            previews[int(row["appid"])] = {
                "short_description": (row["short_description"] or "").strip(),
                "header_image": row["header_image"] or "",
                "capsule_image": row["capsule_image"] or "",
                "capsule_imagev5": row["capsule_imagev5"] or "",
                "background_image": row["background_image"] or "",
                "background_image_raw": row["background_image_raw"] or "",
                "logo_image": row["logo_image"] or "",
                "icon_image": row["icon_image"] or "",
                "library_hero_image": row["library_hero_image"] or "",
                "library_capsule_image": row["library_capsule_image"] or "",
                "developers": _load_json_list(row["developers_json"]),
                "publishers": _load_json_list(row["publishers_json"]),
                "release_date_text": row["release_date_text"] or "",
            }
        return previews

    def _load_canonical_preview(self) -> dict[int, dict]:
        query = """
            SELECT appid, canonical_metadata_json
            FROM canonical_game_semantics
        """
        try:
            with self._connect() as connection:
                rows = connection.execute(query).fetchall()
        except sqlite3.Error:
            return {}

        previews: dict[int, dict] = {}
        for row in rows:
            try:
                metadata = json.loads(row["canonical_metadata_json"])
            except (TypeError, ValueError, json.JSONDecodeError):
                metadata = {}
            previews[int(row["appid"])] = {
                "signature_tag": metadata.get("signature_tag", ""),
                "soundtrack_tags": metadata.get("soundtrack_tags", []) or [],
            }
        return previews

    @staticmethod
    def _row_to_game(row: sqlite3.Row, signals: dict | None = None, preview: dict | None = None) -> dict:
        payload = {
            "appid": int(row["appid"]),
            "name": row["name"],
            "vectors": json.loads(row["canonical_vectors_json"]),
            "metadata": json.loads(row["canonical_metadata_json"]),
            "signals": signals or {},
        }
        if preview:
            payload.update(preview)
        return payload

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
        results = []
        for _, candidate in scored[:limit]:
            preview = dict(self._preview_metadata.get(candidate["appid"], {}))
            canonical = self._canonical_preview.get(candidate["appid"], {})
            results.append(
                {
                    "appid": candidate["appid"],
                    "name": candidate["name"],
                    "signature_tag": canonical.get("signature_tag", ""),
                    "soundtrack_tags": canonical.get("soundtrack_tags", []),
                    **preview,
                }
            )
        return results

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
        appid = int(row["appid"])
        return self._row_to_game(
            row,
            self._metadata_signals.get(appid),
            {
                **self._preview_metadata.get(appid, {}),
                **self._canonical_preview.get(appid, {}),
            },
        )

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
            self._row_to_game(
                row,
                self._metadata_signals.get(int(row["appid"])),
                {
                    **self._preview_metadata.get(int(row["appid"]), {}),
                    **self._canonical_preview.get(int(row["appid"]), {}),
                },
            )
            for row in rows
        ]
