from __future__ import annotations

import os
from contextlib import nullcontext
from typing import Any

from sqlalchemy import (
    BigInteger, Integer, Text, any_, and_, case, cast, column, create_engine,
    delete, func, insert, literal_column, or_, select, table, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR

from backend.coercion import coerce_json_dict, coerce_json_list, normalize_search_text, unique_appids


# Runtime projections of the existing schema; database creation stays in the
# ingestion pipeline. Core expressions bind values without interpolating input.
_GAME_FIELDS = (
    "appid", "name", "canonical_vectors", "canonical_metadata",
    "metacritic_score", "recommendations_total", "steamspy_owner_estimate",
    "steamspy_ccu", "positive", "negative", "estimated_review_count",
    "release_date_parsed", "short_description", "header_image", "capsule_image",
    "capsule_imagev5", "background_image", "background_image_raw", "logo_image",
    "library_hero_image", "library_capsule_image", "developers", "publishers",
    "release_date_text",
)
_SEARCH_FIELDS = (
    "appid", "name", "canonical_metadata", "short_description", "header_image",
    "capsule_image", "capsule_imagev5", "background_image", "background_image_raw",
    "logo_image", "library_hero_image", "library_capsule_image",
)
_JSON_FIELDS = {"canonical_vectors", "canonical_metadata", "developers", "publishers"}
_INTEGER_FIELDS = {
    "appid", "metacritic_score", "recommendations_total", "steamspy_owner_estimate",
    "steamspy_ccu", "positive", "negative", "estimated_review_count",
}
games = table(
    "games",
    *(column(name, JSONB if name in _JSON_FIELDS else BigInteger if name in _INTEGER_FIELDS else Text)
      for name in _GAME_FIELDS),
    column("normalized_name", Text), column("search_name", TSVECTOR),
)
screenshots = table(
    "game_screenshots", column("appid", BigInteger),
    column("screenshot_id", Integer), column("path_full", Text),
)
candidates = table(
    "precomputed_candidates", column("source_appid", BigInteger),
    column("candidate_appid", BigInteger), column("rank", Integer), column("source", Text),
)
diagnostics = table(
    "ui_diagnostics", column("appid", Integer), column("game_name", Text),
    column("event_type", Text), column("details", JSONB),
)


class PostgresGameStore:
    def __init__(self, dsn: str) -> None:
        import psycopg

        self.dsn = dsn
        # Keep accepting both libpq keyword DSNs and PostgreSQL URLs, including
        # their SSL/options settings. SQLAlchemy owns pooling and transactions.
        self.engine = create_engine(
            "postgresql+psycopg://",
            creator=lambda: psycopg.connect(dsn),
            pool_pre_ping=True,
            hide_parameters=True,
        )

    def _connect(self):
        return self.engine.connect()

    def _load_screenshots_for_appids(
        self,
        appids: list[int],
        limit_per_game: int = 3,
        *,
        connection: Any | None = None,
    ) -> dict[int, list[str]]:
        if not appids:
            return {}

        ranked = select(
            screenshots.c.appid,
            screenshots.c.path_full,
            func.row_number().over(
                partition_by=screenshots.c.appid, order_by=screenshots.c.screenshot_id,
            ).label("row_num"),
        ).where(screenshots.c.appid.in_(appids)).subquery("ranked")
        statement = select(ranked.c.appid, ranked.c.path_full).where(
            ranked.c.row_num <= limit_per_game,
        ).order_by(ranked.c.appid, ranked.c.row_num)
        result: dict[int, list[str]] = {}
        connection_manager = nullcontext(connection) if connection is not None else self._connect()
        with connection_manager as active_connection:
            rows = active_connection.execute(statement).mappings().all()

        for row in rows:
            appid = int(row["appid"])
            path_full = str(row.get("path_full") or "").strip()
            if not path_full:
                continue
            result.setdefault(appid, []).append(path_full)
        return result

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
        with self.engine.begin() as connection:
            connection.execute(text(sql))

    def ensure_recommendation_indexes(self) -> None:
        statements = [
            "CREATE INDEX IF NOT EXISTS games_recommendations_total_idx ON games (recommendations_total DESC NULLS LAST)",
            "CREATE INDEX IF NOT EXISTS games_signature_tag_idx ON games ((canonical_metadata ->> 'signature_tag'))",
            "CREATE INDEX IF NOT EXISTS games_music_primary_idx ON games ((canonical_metadata ->> 'music_primary'))",
            "CREATE INDEX IF NOT EXISTS games_music_secondary_idx ON games ((canonical_metadata ->> 'music_secondary'))",
            "CREATE INDEX IF NOT EXISTS games_niche_anchors_gin_idx ON games USING GIN ((COALESCE(canonical_metadata -> 'niche_anchors', '[]'::jsonb)))",
            "CREATE INDEX IF NOT EXISTS games_identity_tags_gin_idx ON games USING GIN ((COALESCE(canonical_metadata -> 'identity_tags', '[]'::jsonb)))",
            "CREATE INDEX IF NOT EXISTS games_micro_tags_gin_idx ON games USING GIN ((COALESCE(canonical_metadata -> 'micro_tags', '[]'::jsonb)))",
            "CREATE INDEX IF NOT EXISTS games_setting_tags_gin_idx ON games USING GIN ((COALESCE(canonical_metadata -> 'setting_tags', '[]'::jsonb)))",
            "CREATE INDEX IF NOT EXISTS games_genre_primary_gin_idx ON games USING GIN ((COALESCE(canonical_metadata -> 'genre_tree' -> 'primary', '[]'::jsonb)))",
            "CREATE INDEX IF NOT EXISTS games_genre_sub_gin_idx ON games USING GIN ((COALESCE(canonical_metadata -> 'genre_tree' -> 'sub', '[]'::jsonb)))",
            "CREATE INDEX IF NOT EXISTS games_genre_sub_sub_gin_idx ON games USING GIN ((COALESCE(canonical_metadata -> 'genre_tree' -> 'sub_sub', '[]'::jsonb)))",
        ]
        with self.engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))

    def ensure_precomputed_candidates_table(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS precomputed_candidates (
                source_appid BIGINT NOT NULL REFERENCES games(appid) ON DELETE CASCADE,
                candidate_appid BIGINT NOT NULL REFERENCES games(appid) ON DELETE CASCADE,
                rank INTEGER NOT NULL,
                source TEXT NOT NULL DEFAULT 'chroma',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (source_appid, candidate_appid)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS precomputed_candidates_source_rank_idx
                ON precomputed_candidates (source_appid, rank)
            """,
        ]
        with self.engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))

    def load_precomputed_candidate_appids(self, source_appid: int, *, limit: int = 300) -> list[int]:
        statement = select(candidates.c.candidate_appid).where(
            candidates.c.source_appid == int(source_appid),
        ).order_by(candidates.c.rank).limit(int(limit))
        with self._connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [int(row["candidate_appid"]) for row in rows if row.get("candidate_appid") is not None]

    def replace_precomputed_candidates(
        self,
        source_appid: int,
        candidate_appids: list[int],
        *,
        source: str = "chroma",
    ) -> None:
        source_appid = int(source_appid)
        normalized_candidates = [appid for appid in unique_appids(candidate_appids) if appid != source_appid]

        # Delete and insert share a transaction: a failed replacement must leave
        # the previous candidate pool available to recommendation requests.
        with self.engine.begin() as connection:
            connection.execute(delete(candidates).where(candidates.c.source_appid == int(source_appid)))
            if normalized_candidates:
                connection.execute(insert(candidates), [
                    {"source_appid": int(source_appid), "candidate_appid": candidate_appid,
                     "rank": rank, "source": source}
                    for rank, candidate_appid in enumerate(normalized_candidates, start=1)
                ])

    def list_game_appids(self) -> list[int]:
        with self._connect() as connection:
            return list(connection.execute(select(games.c.appid).order_by(games.c.appid)).scalars())

    def prescreen_candidate_appids(
        self,
        base_game: dict[str, Any],
        *,
        context_percentages: dict[str, float | int] | None = None,
        tag_boosts: dict[str, dict[str, float]] | None = None,
        soundtrack_boosts: dict[str, float] | None = None,
        limit: int = 2500,
    ) -> list[int]:
        metadata = base_game.get("metadata") or {}
        genre_tree = metadata.get("genre_tree", {}) or {}
        tag_boosts = tag_boosts or {}
        soundtrack_boosts = soundtrack_boosts or {}

        signature_tags = [str(metadata.get("signature_tag", "")).strip()] if str(metadata.get("signature_tag", "")).strip() else []
        niche_anchor_tags = [str(tag).strip() for tag in metadata.get("niche_anchors", []) or [] if str(tag).strip()]
        identity_detail_tags = [
            str(tag).strip()
            for tag in [
                *(metadata.get("identity_tags", []) or []),
                *(metadata.get("micro_tags", []) or []),
            ]
            if str(tag).strip()
        ]
        setting_tags = [str(tag).strip() for tag in metadata.get("setting_tags", []) or [] if str(tag).strip()]
        music_tags = [
            str(tag).strip()
            for tag in [
                metadata.get("music_primary", ""),
                metadata.get("music_secondary", ""),
                *soundtrack_boosts.keys(),
            ]
            if str(tag).strip()
        ]
        primary_genres = [str(tag).strip() for tag in (genre_tree.get("primary") or [])] if isinstance(genre_tree.get("primary"), list) else ([str(genre_tree.get("primary")).strip()] if str(genre_tree.get("primary", "")).strip() else [])
        sub_genres = [str(tag).strip() for tag in (genre_tree.get("sub") or [])] if isinstance(genre_tree.get("sub"), list) else ([str(genre_tree.get("sub")).strip()] if str(genre_tree.get("sub", "")).strip() else [])
        sub_sub_genres = [str(tag).strip() for tag in (genre_tree.get("sub_sub") or [])] if isinstance(genre_tree.get("sub_sub"), list) else ([str(genre_tree.get("sub_sub")).strip()] if str(genre_tree.get("sub_sub", "")).strip() else [])

        boosted_identity_tags = [str(tag).strip() for tag in tag_boosts.get("identity", {}).keys() if str(tag).strip()]
        boosted_setting_tags = [str(tag).strip() for tag in tag_boosts.get("setting", {}).keys() if str(tag).strip()]

        # These keys are fixed application constants, never request values.
        # Keep -> expressions identical to the existing PostgreSQL indexes.
        def metadata_value(*keys, as_text=False):
            value = games.c.canonical_metadata
            for index, key in enumerate(keys):
                operator = "->>" if as_text and index == len(keys) - 1 else "->"
                value = value.op(operator, return_type=Text if operator == "->>" else JSONB)(
                    literal_column("'" + key + "'"),
                )
            return value

        def scalar_matches(keys, tags):
            return metadata_value(*keys, as_text=True) == any_(cast(tags or [""], ARRAY(Text)))

        def array_matches(keys, tags):
            return func.coalesce(metadata_value(*keys), literal_column("'[]'::jsonb", JSONB)).bool_op("?|")(
                cast(tags or [""], ARRAY(Text)),
            )

        def genre_matches(branch, tags):
            keys = ("genre_tree", branch)
            return or_(
                and_(func.jsonb_typeof(metadata_value(*keys)) == "array", array_matches(keys, tags)),
                scalar_matches(keys, tags),
            )

        # These weights choose a cheap candidate pool, not the final UI score.
        # Reuse each condition for both eligibility and ranking so they agree.
        matches = [
            (scalar_matches(("signature_tag",), signature_tags), signature_tags, 18),
            (array_matches(("niche_anchors",), niche_anchor_tags), niche_anchor_tags, 12),
            (array_matches(("identity_tags",), identity_detail_tags), identity_detail_tags, 7),
            (array_matches(("micro_tags",), identity_detail_tags), identity_detail_tags, 3),
            (array_matches(("identity_tags",), boosted_identity_tags), boosted_identity_tags, 5),
            (array_matches(("niche_anchors",), boosted_identity_tags), boosted_identity_tags, 7),
            (array_matches(("setting_tags",), setting_tags), setting_tags, 8),
            (array_matches(("setting_tags",), boosted_setting_tags), boosted_setting_tags, 5),
            (scalar_matches(("music_primary",), music_tags), music_tags, 7),
            (scalar_matches(("music_secondary",), music_tags), music_tags, 5),
            (genre_matches("primary", primary_genres), primary_genres, 10),
            (genre_matches("sub", sub_genres), sub_genres, 7),
            (genre_matches("sub_sub", sub_sub_genres), sub_sub_genres, 4),
        ]
        statement = select(games.c.appid).where(games.c.appid != int(base_game["appid"]))
        filters = [condition for condition, tags, _ in matches if tags]
        if filters:
            statement = statement.where(or_(*filters))
        score = sum(case((condition, weight), else_=0) for condition, _, weight in matches)
        statement = statement.order_by(
            score.desc(), games.c.recommendations_total.desc().nulls_last(), games.c.appid,
        ).limit(limit)
        with self._connect() as connection:
            return list(connection.execute(statement).scalars())

    def _row_to_game(self, row: dict[str, Any], screenshots: list[str] | None = None) -> dict[str, Any]:
        metadata = coerce_json_dict(row.get("canonical_metadata"))
        return {
            "appid": int(row["appid"]),
            "name": row.get("name"),
            "vectors": coerce_json_dict(row.get("canonical_vectors")),
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
            "developers": coerce_json_list(row.get("developers")),
            "publishers": coerce_json_list(row.get("publishers")),
            "release_date_text": row.get("release_date_text") or "",
            "signature_tag": metadata.get("signature_tag", ""),
            "music_primary": str(metadata.get("music_primary", "")).strip(),
            "music_secondary": str(metadata.get("music_secondary", "")).strip(),
        }

    def search_games(self, query: str, limit: int = 12) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        normalized_query = normalize_search_text(query)
        if not normalized_query:
            return []

        prefix_query = f"{normalized_query}%"
        contains_query = f"%{normalized_query}%"
        g = games.c
        # Exact/prefix matches dominate; full-text and trigram similarity recover
        # partial titles and typos. SQLAlchemy binds every request-derived value.
        full_text_match = g.search_name.bool_op("@@")(func.plainto_tsquery("simple", query))
        score = (
            case((g.normalized_name == normalized_query, 10000.0), else_=0.0)
            + case((g.normalized_name.like(prefix_query), 500.0), else_=0.0)
            + case((g.normalized_name.like(contains_query), 250.0), else_=0.0)
            + case((full_text_match, 120.0), else_=0.0)
            + func.similarity(g.normalized_name, normalized_query) * 100.0
            + func.similarity(func.lower(g.name), func.lower(query)) * 40.0
            - func.length(g.name) * 0.03
            + func.ln(1 + func.greatest(func.coalesce(g.recommendations_total, 0), 0)) * 3.0
        ).label("score")
        ranked = select(*(g[name] for name in _SEARCH_FIELDS), score).where(or_(
            g.normalized_name == normalized_query,
            g.normalized_name.like(prefix_query),
            g.normalized_name.like(contains_query),
            full_text_match,
            g.normalized_name.bool_op("%")(normalized_query),
        )).order_by(score.desc(), func.length(g.name), func.lower(g.name)).limit(limit).cte("ranked")
        statement = select(ranked).where(ranked.c.score > 0).order_by(
            ranked.c.score.desc(), func.length(ranked.c.name), func.lower(ranked.c.name),
        )
        with self._connect() as connection:
            rows = connection.execute(statement).mappings().all()

        results = []
        for row in rows:
            metadata = coerce_json_dict(row.get("canonical_metadata"))
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
        statement = select(*(games.c[name] for name in _GAME_FIELDS)).where(games.c.appid == appid)
        with self._connect() as connection:
            row = connection.execute(statement).mappings().first()
            if row is None:
                return None
            screenshots_by_appid = self._load_screenshots_for_appids([appid], connection=connection)
            return self._row_to_game(row, screenshots_by_appid.get(appid, []))

    def load_games_by_appids(self, appids: list[int]) -> list[dict[str, Any]]:
        normalized_appids = unique_appids(appids)

        if not normalized_appids:
            return []

        statement = select(*(games.c[name] for name in _GAME_FIELDS)).where(games.c.appid.in_(normalized_appids))
        with self._connect() as connection:
            rows = connection.execute(statement).mappings().all()
            screenshots_by_appid = self._load_screenshots_for_appids(normalized_appids, connection=connection)
        row_by_appid = {
            int(row["appid"]): self._row_to_game(row, screenshots_by_appid.get(int(row["appid"]), []))
            for row in rows
        }
        # IN queries do not preserve input order; restore the retriever's ranking.
        return [row_by_appid[appid] for appid in normalized_appids if appid in row_by_appid]

    def record_ui_diagnostic(
        self,
        *,
        event_type: str,
        game_name: str,
        appid: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self.engine.begin() as connection:
            connection.execute(insert(diagnostics).values(
                appid=appid, game_name=game_name, event_type=event_type, details=details or {},
            ))


def postgres_dsn_from_env() -> str | None:
    dsn = os.getenv("STEAM_REC_POSTGRES_DSN")
    if dsn and dsn.strip():
        return dsn.strip()
    return None
