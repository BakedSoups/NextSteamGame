from __future__ import annotations

import json
import os
import re
from typing import Any


class PostgresGameStore:
    def __init__(self, dsn: str) -> None:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "Postgres support requires psycopg. Install dependencies from requirements.txt."
            ) from exc

        self._psycopg = psycopg
        self._dict_row = dict_row
        self.dsn = dsn

    def _connect(self):
        return self._psycopg.connect(self.dsn, row_factory=self._dict_row)

    def _load_screenshots_for_appids(self, appids: list[int], limit_per_game: int = 3) -> dict[int, list[str]]:
        if not appids:
            return {}

        sql = """
            SELECT appid, path_full
            FROM (
                SELECT
                    appid,
                    path_full,
                    ROW_NUMBER() OVER (PARTITION BY appid ORDER BY screenshot_id) AS row_num
                FROM game_screenshots
                WHERE appid = ANY(%s)
            ) ranked
            WHERE row_num <= %s
            ORDER BY appid, row_num
        """
        screenshots: dict[int, list[str]] = {}
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, (appids, limit_per_game))
                rows = cursor.fetchall()

        for row in rows:
            appid = int(row["appid"])
            path_full = str(row.get("path_full") or "").strip()
            if not path_full:
                continue
            screenshots.setdefault(appid, []).append(path_full)
        return screenshots

    def ensure_diagnostics_table(self) -> None:
        sql = """
            CREATE TABLE IF NOT EXISTS ui_diagnostics (
                id BIGSERIAL PRIMARY KEY,
                appid INTEGER,
                game_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
            connection.commit()

    @staticmethod
    def _normalize_search_text(text: str) -> str:
        lowered = text.lower()
        lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
        return " ".join(lowered.split())

    @staticmethod
    def _coerce_json(raw: Any) -> dict:
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    @staticmethod
    def _coerce_list(raw: Any) -> list[str]:
        if isinstance(raw, list):
            return [str(item) for item in raw if str(item).strip()]
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                return []
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item).strip()]
        return []

    @staticmethod
    def _metadata_music_tags(metadata: dict[str, Any]) -> list[str]:
        tags: list[str] = []
        for field in ("music_primary", "music_secondary"):
            value = str(metadata.get(field, "")).strip()
            if value and value not in tags:
                tags.append(value)
        return tags

    def _row_to_game(self, row: dict[str, Any], screenshots: list[str] | None = None) -> dict[str, Any]:
        metadata = self._coerce_json(row.get("canonical_metadata"))
        music_tags = self._metadata_music_tags(metadata)
        return {
            "appid": int(row["appid"]),
            "name": row.get("name"),
            "vectors": self._coerce_json(row.get("canonical_vectors")),
            "metadata": metadata,
            "signals": {
                "metacritic_score": row.get("metacritic_score"),
                "recommendations_total": row.get("recommendations_total"),
                "steamspy_owner_estimate": row.get("steamspy_owner_estimate"),
                "steamspy_ccu": row.get("steamspy_ccu"),
                "positive": row.get("positive"),
                "negative": row.get("negative"),
                "estimated_review_count": row.get("estimated_review_count"),
                "release_date_parsed": row.get("release_date_parsed"),
            },
            "short_description": (row.get("short_description") or "").strip(),
            "header_image": row.get("header_image") or "",
            "capsule_image": row.get("capsule_image") or "",
            "capsule_imagev5": row.get("capsule_imagev5") or "",
            "background_image": row.get("background_image") or "",
            "background_image_raw": row.get("background_image_raw") or "",
            "logo_image": row.get("logo_image") or "",
            "library_hero_image": row.get("library_hero_image") or "",
            "library_capsule_image": row.get("library_capsule_image") or "",
            "screenshots": list(screenshots or []),
            "developers": self._coerce_list(row.get("developers")),
            "publishers": self._coerce_list(row.get("publishers")),
            "release_date_text": row.get("release_date_text") or "",
            "signature_tag": metadata.get("signature_tag", ""),
            "music_primary": str(metadata.get("music_primary", "")).strip(),
            "music_secondary": str(metadata.get("music_secondary", "")).strip(),
        }

    def search_games(self, query: str, limit: int = 12) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        normalized_query = self._normalize_search_text(query)
        if not normalized_query:
            return []

        prefix_query = f"{normalized_query}%"
        contains_query = f"%{normalized_query}%"
        sql = """
            WITH ranked AS (
                SELECT
                    g.appid,
                    g.name,
                    g.canonical_metadata,
                    g.short_description,
                    g.header_image,
                    g.capsule_image,
                    g.capsule_imagev5,
                    g.background_image,
                    g.background_image_raw,
                    g.logo_image,
                    g.library_hero_image,
                    g.library_capsule_image,
                    (
                        CASE WHEN g.normalized_name = %s THEN 10000.0 ELSE 0.0 END +
                        CASE WHEN g.normalized_name LIKE %s THEN 500.0 ELSE 0.0 END +
                        CASE WHEN g.normalized_name LIKE %s THEN 250.0 ELSE 0.0 END +
                        CASE WHEN g.search_name @@ plainto_tsquery('simple', %s) THEN 120.0 ELSE 0.0 END +
                        similarity(g.normalized_name, %s) * 100.0 +
                        similarity(lower(g.name), lower(%s)) * 40.0 -
                        length(g.name) * 0.03 +
                        ln(1 + GREATEST(COALESCE(g.recommendations_total, 0), 0)) * 3.0
                    ) AS score
                FROM games g
                WHERE
                    g.normalized_name = %s
                    OR g.normalized_name LIKE %s
                    OR g.normalized_name LIKE %s
                    OR g.search_name @@ plainto_tsquery('simple', %s)
                    OR g.normalized_name %% %s
                ORDER BY score DESC, length(g.name), lower(g.name)
                LIMIT %s
            )
            SELECT
                appid,
                name,
                canonical_metadata,
                short_description,
                header_image,
                capsule_image,
                capsule_imagev5,
                background_image,
                background_image_raw,
                logo_image,
                library_hero_image,
                library_capsule_image,
                score
            FROM ranked
            WHERE score > 0
            ORDER BY score DESC, length(name), lower(name)
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql,
                    (
                        normalized_query,
                        prefix_query,
                        contains_query,
                        query,
                        normalized_query,
                        query,
                        normalized_query,
                        prefix_query,
                        contains_query,
                        query,
                        normalized_query,
                        limit,
                    ),
                )
                rows = cursor.fetchall()

        results = []
        for row in rows:
            metadata = self._coerce_json(row.get("canonical_metadata"))
            music_tags = self._metadata_music_tags(metadata)
            results.append(
                {
                    "appid": int(row["appid"]),
                    "name": row.get("name"),
                    "signature_tag": metadata.get("signature_tag", ""),
                    "music_primary": str(metadata.get("music_primary", "")).strip(),
                    "music_secondary": str(metadata.get("music_secondary", "")).strip(),
                    "short_description": (row.get("short_description") or "").strip(),
                    "header_image": row.get("header_image") or "",
                    "capsule_image": row.get("capsule_image") or "",
                    "capsule_imagev5": row.get("capsule_imagev5") or "",
                    "background_image": row.get("background_image") or "",
                    "background_image_raw": row.get("background_image_raw") or "",
                    "logo_image": row.get("logo_image") or "",
                    "library_hero_image": row.get("library_hero_image") or "",
                    "library_capsule_image": row.get("library_capsule_image") or "",
                }
            )
        return results

    def get_game(self, appid: int) -> dict[str, Any] | None:
        sql = """
            SELECT
                appid,
                name,
                canonical_vectors,
                canonical_metadata,
                metacritic_score,
                recommendations_total,
                steamspy_owner_estimate,
                steamspy_ccu,
                positive,
                negative,
                estimated_review_count,
                release_date_parsed,
                short_description,
                header_image,
                capsule_image,
                capsule_imagev5,
                background_image,
                background_image_raw,
                logo_image,
                library_hero_image,
                library_capsule_image,
                developers,
                publishers,
                release_date_text
            FROM games
            WHERE appid = %s
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, (appid,))
                row = cursor.fetchone()
        if row is None:
            return None
        screenshots_by_appid = self._load_screenshots_for_appids([appid])
        return self._row_to_game(row, screenshots_by_appid.get(appid, []))

    def load_all_games(self) -> list[dict[str, Any]]:
        sql = """
            SELECT
                appid,
                name,
                canonical_vectors,
                canonical_metadata,
                metacritic_score,
                recommendations_total,
                steamspy_owner_estimate,
                steamspy_ccu,
                positive,
                negative,
                estimated_review_count,
                release_date_parsed,
                short_description,
                header_image,
                capsule_image,
                capsule_imagev5,
                background_image,
                background_image_raw,
                logo_image,
                library_hero_image,
                library_capsule_image,
                developers,
                publishers,
                release_date_text
            FROM games
            ORDER BY appid
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
        appids = [int(row["appid"]) for row in rows]
        screenshots_by_appid = self._load_screenshots_for_appids(appids)
        return [
            self._row_to_game(row, screenshots_by_appid.get(int(row["appid"]), []))
            for row in rows
        ]

    def record_ui_diagnostic(
        self,
        *,
        event_type: str,
        game_name: str,
        appid: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        sql = """
            INSERT INTO ui_diagnostics (
                appid,
                game_name,
                event_type,
                details
            )
            VALUES (%s, %s, %s, %s::jsonb)
        """
        payload = json.dumps(details or {})
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql,
                    (
                        appid,
                        game_name,
                        event_type,
                        payload,
                    ),
                )
            connection.commit()


def postgres_dsn_from_env() -> str | None:
    dsn = os.getenv("STEAM_REC_POSTGRES_DSN")
    if dsn and dsn.strip():
        return dsn.strip()
    return None
