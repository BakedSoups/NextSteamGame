from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import psycopg as pg_dialect
from sqlalchemy.exc import IntegrityError

from backend.pg_store import PostgresGameStore, diagnostics


ATTACK = "x'); DROP TABLE games; --"


class BoundParameterTests(unittest.TestCase):
    def test_search_and_tag_values_are_bound(self):
        store = PostgresGameStore("host=unused")
        self.addCleanup(store.engine.dispose)
        connection = MagicMock()
        with patch.object(store, "_connect", return_value=connection):
            store.search_games(ATTACK)
            search = connection.__enter__.return_value.execute.call_args.args[0]
            compiled = search.compile(dialect=pg_dialect.dialect())
            self.assertNotIn(ATTACK, str(compiled))
            self.assertIn(ATTACK, compiled.params.values())

            store.prescreen_candidate_appids(
                {"appid": 1, "metadata": {}},
                tag_boosts={"identity": {ATTACK: 100}, "setting": {ATTACK: 50}},
                soundtrack_boosts={ATTACK: 80},
            )
            statement = connection.__enter__.return_value.execute.call_args.args[0]
            compiled = statement.compile(dialect=pg_dialect.dialect())
            self.assertNotIn(ATTACK, str(compiled))
            self.assertIn([ATTACK], compiled.params.values())


@unittest.skipUnless(os.getenv("STEAM_REC_TEST_POSTGRES_DSN"), "test PostgreSQL DSN not set")
class PostgresGameStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["STEAM_REC_TEST_POSTGRES_DSN"]
        cls.schema = "test_store_" + uuid4().hex
        with psycopg.connect(cls.dsn, autocommit=True) as connection:
            connection.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public")
            connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(cls.schema)))
        cls.addClassCleanup(cls.drop_schema)
        cls.test_dsn = make_conninfo(cls.dsn, options=f"-csearch_path={cls.schema},public")
        with psycopg.connect(cls.test_dsn) as connection:
            connection.execute(Path("db_creation/postgres/schema.sql").read_text())
        cls.store = PostgresGameStore(cls.test_dsn)
        cls.addClassCleanup(cls.store.engine.dispose)
        cls.store.ensure_diagnostics_table()
        cls.store.ensure_precomputed_candidates_table()
        cls.store.ensure_recommendation_indexes()

    @classmethod
    def drop_schema(cls):
        with psycopg.connect(cls.dsn, autocommit=True) as connection:
            connection.execute(psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(cls.schema)))

    def setUp(self):
        with psycopg.connect(self.test_dsn) as connection:
            connection.execute("TRUNCATE games, ui_diagnostics CASCADE")
            for appid, name, metadata, reviews in (
                (1, "Portal", {"signature_tag": "puzzle"}, 100),
                (2, "Portal 2", {"signature_tag": "puzzle", "genre_tree": {"primary": ["action"]}}, 200),
                (3, "Space Quest", {"genre_tree": {"primary": "action"}, "identity_tags": ["adventure"]}, 300),
                (4, "Music World", {"music_primary": "jazz", "setting_tags": ["space"]}, None),
            ):
                connection.execute("""
                    INSERT INTO games (appid, name, normalized_name, canonical_metadata,
                        canonical_vectors, source_review_samples, source_vectors, source_metadata,
                        recommendations_total)
                    VALUES (%s, %s, %s, %s, '{}', '{}', '{}', '{}', %s)
                """, (appid, name, name.lower(), Jsonb(metadata), reviews))
            for appid in (1, 2):
                for screenshot_id in (4, 2, 1, 3):
                    connection.execute(
                        "INSERT INTO game_screenshots (appid, screenshot_id, path_full) VALUES (%s, %s, %s)",
                        (appid, screenshot_id, f"https://example.com/{appid}/{screenshot_id}.jpg"),
                    )

    def test_startup_ddl_is_idempotent(self):
        self.store.ensure_diagnostics_table()
        self.store.ensure_precomputed_candidates_table()
        self.store.ensure_recommendation_indexes()
        self.assertEqual(self.store.list_game_appids(), [1, 2, 3, 4])

    def test_search_ranking_limits_and_empty_queries(self):
        self.assertEqual([row["appid"] for row in self.store.search_games("Portal")], [1, 2])
        self.assertEqual([row["appid"] for row in self.store.search_games("PORTAL", limit=1)], [1])
        self.assertEqual(self.store.search_games("   "), [])
        self.assertEqual(self.store.search_games("!!!"), [])
        self.assertEqual(self.store.search_games(ATTACK), [])
        self.assertEqual(self.store.list_game_appids(), [1, 2, 3, 4])

    def test_hydration_preserves_order_and_limits_screenshots(self):
        games = self.store.load_games_by_appids([2, "1", 2, "invalid", 999])
        self.assertEqual([game["appid"] for game in games], [2, 1])
        self.assertEqual(games[0]["screenshots"], [f"https://example.com/2/{i}.jpg" for i in (1, 2, 3)])
        self.assertEqual(games[1], self.store.get_game(1))
        self.assertEqual(games[1]["metadata"], {"signature_tag": "puzzle"})
        self.assertIsNone(self.store.get_game(999))
        self.assertEqual(self.store.load_games_by_appids([]), [])

    def test_screenshot_limit_per_game(self):
        result = self.store._load_screenshots_for_appids([1, 2], limit_per_game=1)
        self.assertEqual(result, {1: ["https://example.com/1/1.jpg"], 2: ["https://example.com/2/1.jpg"]})

    def test_candidate_replacement_and_rollback(self):
        self.store.replace_precomputed_candidates(1, [1, 3, 2, 3, "invalid"], source=ATTACK)
        self.assertEqual(self.store.load_precomputed_candidate_appids(1), [3, 2])
        self.assertEqual(self.store.load_precomputed_candidate_appids(1, limit=1), [3])
        with self.assertRaises(IntegrityError):
            self.store.replace_precomputed_candidates(1, [4, 999])
        self.assertEqual(self.store.load_precomputed_candidate_appids(1), [3, 2])
        self.store.replace_precomputed_candidates(1, [])
        self.assertEqual(self.store.load_precomputed_candidate_appids(1), [])

    def test_prescreen_signature_and_scalar_or_array_genres(self):
        self.assertEqual(self.store.prescreen_candidate_appids(self.store.get_game(1)), [2])
        base = {"appid": 1, "metadata": {"genre_tree": {"primary": ["action"]}}}
        self.assertEqual(self.store.prescreen_candidate_appids(base), [3, 2])
        self.assertEqual(self.store.prescreen_candidate_appids(base, limit=1), [3])
        base["metadata"]["genre_tree"]["primary"] = "action"
        self.assertEqual(self.store.prescreen_candidate_appids(base), [3, 2])

    def test_prescreen_boosts_and_missing_metadata(self):
        base = {"appid": 1, "metadata": {}}
        self.assertEqual(self.store.prescreen_candidate_appids(base), [3, 2, 4])
        self.assertEqual(self.store.prescreen_candidate_appids(base, tag_boosts={"identity": {"adventure": 80}}), [3])
        self.assertEqual(self.store.prescreen_candidate_appids(base, tag_boosts={"setting": {"space": 80}}), [4])
        self.assertEqual(self.store.prescreen_candidate_appids(base, soundtrack_boosts={"jazz": 80}), [4])
        self.assertEqual(self.store.prescreen_candidate_appids(base, tag_boosts={"identity": {ATTACK: 80}}), [])
        self.assertEqual(self.store.list_game_appids(), [1, 2, 3, 4])

    def test_diagnostics_round_trip_untrusted_text_and_json(self):
        details = {"message": ATTACK, "nested": ["quotes'", '"', "雪"]}
        self.store.record_ui_diagnostic(event_type=ATTACK, game_name=ATTACK, details=details)
        with self.store.engine.connect() as connection:
            row = connection.execute(select(diagnostics)).mappings().one()
        self.assertEqual(row["details"], details)
        self.assertEqual(row["game_name"], ATTACK)
        self.assertEqual(row["event_type"], ATTACK)
        self.assertIsNone(row["appid"])
        self.assertEqual(self.store.list_game_appids(), [1, 2, 3, 4])
