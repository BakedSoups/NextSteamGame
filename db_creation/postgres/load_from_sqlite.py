#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

from db_creation.paths import final_canon_db_path, metadata_db_path


def log(message: str) -> None:
    print(message, flush=True)


def normalize_search_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(lowered.split())


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_project_env() -> None:
    env_path = project_root() / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip().strip("\"'")
        os.environ[key] = value


load_project_env()


def schema_path() -> Path:
    return Path(__file__).resolve().with_name("schema.sql")


def postgres_dsn() -> str:
    value = os.getenv("STEAM_REC_POSTGRES_DSN")
    if not value:
        raise RuntimeError("STEAM_REC_POSTGRES_DSN is not set")
    return value


def open_sqlite_readonly(path: Path) -> sqlite3.Connection:
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"SQLite database not found: {resolved}")

    # Use immutable read-only mode so Docker bind mounts can be mounted read-only
    # without SQLite trying to create lock or WAL sidecar files inside the container.
    return sqlite3.connect(f"file:{resolved}?mode=ro&immutable=1", uri=True)


def load_preview_rows(connection: sqlite3.Connection) -> dict[int, dict]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT
            appid,
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
            developers_json,
            publishers_json,
            release_date_text
        FROM games
        """
    ).fetchall()
    return {
        int(row["appid"]): dict(row)
        for row in rows
    }


def load_canonical_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    return connection.execute(
        """
        SELECT
            appid,
            name,
            canonical_vectors_json,
            canonical_metadata_json,
            source_review_samples_json,
            source_vectors_json,
            source_metadata_json
        FROM canonical_game_semantics
        ORDER BY appid
        """
    ).fetchall()


def count_canonical_rows(connection: sqlite3.Connection) -> int:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT COUNT(*) AS row_count FROM canonical_game_semantics"
    ).fetchone()
    return int(row["row_count"]) if row else 0


def iter_canonical_rows(
    connection: sqlite3.Connection, *, batch_size: int = 500
) -> list[sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    cursor = connection.execute(
        """
        SELECT
            appid,
            name,
            canonical_vectors_json,
            canonical_metadata_json,
            source_review_samples_json,
            source_vectors_json,
            source_metadata_json
        FROM canonical_game_semantics
        ORDER BY appid
        """
    )
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        yield rows


def load_tag_groups(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    return connection.execute(
        """
        SELECT
            id,
            source_family,
            context,
            representative_tag,
            parent_tag,
            specificity_level,
            member_count,
            total_occurrences
        FROM canonical_tag_groups
        ORDER BY id
        """
    ).fetchall()


def load_tag_members(connection: sqlite3.Connection) -> dict[int, list[str]]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT group_id, member_tag
        FROM canonical_tag_members
        ORDER BY group_id, member_tag
        """
    ).fetchall()
    members: dict[int, list[str]] = {}
    for row in rows:
        members.setdefault(int(row["group_id"]), []).append(str(row["member_tag"]))
    return members


def load_screenshots(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    return connection.execute(
        """
        SELECT appid, screenshot_id, path_thumbnail, path_full
        FROM game_screenshots
        ORDER BY appid, screenshot_id
        """
    ).fetchall()


def count_screenshots(connection: sqlite3.Connection) -> int:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT COUNT(*) AS row_count FROM game_screenshots"
    ).fetchone()
    return int(row["row_count"]) if row else 0


def iter_screenshots(
    connection: sqlite3.Connection, *, batch_size: int = 5000
) -> list[sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    cursor = connection.execute(
        """
        SELECT appid, screenshot_id, path_thumbnail, path_full
        FROM game_screenshots
        ORDER BY appid, screenshot_id
        """
    )
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        yield rows


def _coerce_single_genre_value(raw: object) -> str:
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, list):
        for item in raw:
            text = str(item).strip()
            if text:
                return text
    return ""


def _clean_canonical_vectors(raw_json: str | None) -> dict:
    try:
        vectors = json.loads(raw_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(vectors, dict):
        return {}

    cleaned: dict[str, object] = {}
    status = str(vectors.get("status", "")).strip()
    if status:
        cleaned["status"] = status

    for context in ("mechanics", "narrative", "vibe", "structure_loop"):
        tag_weights = vectors.get(context)
        if isinstance(tag_weights, dict):
            cleaned[context] = {
                str(tag): int(weight)
                for tag, weight in tag_weights.items()
                if str(tag).strip()
                and isinstance(weight, (int, float))
                and int(weight) > 0
            }
        else:
            cleaned[context] = {}
    return cleaned


def _clean_canonical_metadata(raw_json: str | None) -> dict:
    try:
        metadata = json.loads(raw_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(metadata, dict):
        return {}

    def clean_list(name: str) -> list[str]:
        raw = metadata.get(name, [])
        if not isinstance(raw, list):
            return []
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in raw:
            text = str(item).strip()
            lowered = text.lower()
            if not text or lowered in seen:
                continue
            seen.add(lowered)
            cleaned.append(text)
        return cleaned

    cleaned: dict[str, object] = {
        "micro_tags": clean_list("micro_tags"),
        "niche_anchors": clean_list("niche_anchors"),
        "identity_tags": clean_list("identity_tags"),
        "setting_tags": clean_list("setting_tags"),
        "signature_tag": str(metadata.get("signature_tag", "")).strip(),
        "music_primary": str(metadata.get("music_primary", "")).strip(),
        "music_secondary": str(metadata.get("music_secondary", "")).strip(),
        "appeal_axes": dict(metadata.get("appeal_axes") or {}),
        "genre_tree": {
            "primary": _coerce_single_genre_value((metadata.get("genre_tree") or {}).get("primary")),
            "sub": _coerce_single_genre_value((metadata.get("genre_tree") or {}).get("sub")),
            "sub_sub": _coerce_single_genre_value((metadata.get("genre_tree") or {}).get("sub_sub")),
        },
    }
    status = str(metadata.get("status", "")).strip()
    if status:
        cleaned["status"] = status
    return cleaned


def ensure_postgres_schema(cursor) -> None:
    cursor.execute(
        """
        ALTER TABLE canonical_tag_groups
        ADD COLUMN IF NOT EXISTS parent_tag TEXT NOT NULL DEFAULT ''
        """
    )
    cursor.execute(
        """
        ALTER TABLE canonical_tag_groups
        ADD COLUMN IF NOT EXISTS specificity_level INTEGER NOT NULL DEFAULT 1
        """
    )


def reset_postgres_tables(cursor, *, reset_all: bool = False) -> None:
    cursor.execute("DROP TABLE IF EXISTS precomputed_candidates")
    cursor.execute("DROP TABLE IF EXISTS game_screenshots")
    cursor.execute("DROP TABLE IF EXISTS canonical_tag_members")
    cursor.execute("DROP TABLE IF EXISTS canonical_tag_groups")
    cursor.execute("DROP TABLE IF EXISTS games")
    cursor.execute("DROP TABLE IF EXISTS pipeline_runs")
    if reset_all:
        cursor.execute("DROP TABLE IF EXISTS ui_diagnostics")


def insert_game_batch(cursor, game_payload: list[tuple]) -> None:
    cursor.executemany(
        """
        INSERT INTO games (
            appid,
            name,
            normalized_name,
            canonical_vectors,
            canonical_metadata,
            source_review_samples,
            source_vectors,
            source_metadata,
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
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        game_payload,
    )


def insert_screenshot_batch(cursor, screenshot_payload: list[tuple]) -> None:
    cursor.executemany(
        """
        INSERT INTO game_screenshots (
            appid,
            screenshot_id,
            path_thumbnail,
            path_full
        )
        VALUES (%s, %s, %s, %s)
        """,
        screenshot_payload,
    )


def main(*, reset_all: bool = False) -> int:
    try:
        import psycopg
        from psycopg.types.json import Jsonb
    except ImportError as exc:
        raise RuntimeError(
            "Postgres support requires psycopg. Install dependencies from requirements.txt."
        ) from exc

    log("Starting SQLite -> Postgres import")
    log(f"Metadata DB: {metadata_db_path()}")
    log(f"Final canon DB: {final_canon_db_path()}")
    log(f"Postgres target: {postgres_dsn()}")

    with schema_path().open("r", encoding="utf-8") as handle:
        schema_sql = handle.read()

    metadata_sqlite = open_sqlite_readonly(metadata_db_path())
    final_sqlite = open_sqlite_readonly(final_canon_db_path())

    try:
        log("Reading preview rows from metadata SQLite")
        preview_rows = load_preview_rows(metadata_sqlite)
        log(f"Loaded preview rows: {len(preview_rows)}")

        log("Counting canonical rows from final SQLite")
        canonical_row_count = count_canonical_rows(final_sqlite)
        log(f"Loaded canonical rows: {canonical_row_count}")

        log("Reading canonical tag groups from final SQLite")
        tag_groups = load_tag_groups(final_sqlite)
        log(f"Loaded tag groups: {len(tag_groups)}")

        log("Reading canonical tag members from final SQLite")
        tag_members = load_tag_members(final_sqlite)
        log(
            "Loaded tag members: "
            f"{sum(len(members) for members in tag_members.values())}"
        )

        log("Counting screenshots from final SQLite")
        screenshot_count = count_screenshots(final_sqlite)
        log(f"Loaded screenshots: {screenshot_count}")

        log("Connecting to Postgres")
        with psycopg.connect(postgres_dsn()) as pg_connection:
            with pg_connection.cursor() as cursor:
                log("Resetting Postgres tables")
                reset_postgres_tables(cursor, reset_all=reset_all)
                log("Applying schema")
                cursor.execute(schema_sql)
                ensure_postgres_schema(cursor)
                log("Creating pipeline run record")
                cursor.execute(
                    "INSERT INTO pipeline_runs (status) VALUES ('running') RETURNING id"
                )
                run_id = int(cursor.fetchone()[0])
                log(f"Pipeline run id: {run_id}")

                group_id_map: dict[int, int] = {}
                log("Inserting canonical tag groups")
                for group in tag_groups:
                    cursor.execute(
                        """
                        INSERT INTO canonical_tag_groups (
                            run_id,
                            source_family,
                            context,
                            representative_tag,
                            parent_tag,
                            specificity_level,
                            member_count,
                            total_occurrences
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            run_id,
                            group["source_family"],
                            group["context"],
                            group["representative_tag"],
                            group["parent_tag"],
                            int(group["specificity_level"]),
                            int(group["member_count"]),
                            int(group["total_occurrences"]),
                        ),
                    )
                    group_id_map[int(group["id"])] = int(cursor.fetchone()[0])
                log(f"Inserted canonical tag groups: {len(group_id_map)}")

                log("Inserting canonical tag members")
                for old_group_id, members in tag_members.items():
                    new_group_id = group_id_map.get(old_group_id)
                    if new_group_id is None:
                        continue
                    cursor.executemany(
                        """
                        INSERT INTO canonical_tag_members (group_id, member_tag)
                        VALUES (%s, %s)
                        """,
                        [(new_group_id, member) for member in members],
                    )
                log(
                    "Inserted canonical tag members: "
                    f"{sum(len(members) for members in tag_members.values())}"
                )

                log("Preparing and inserting games in batches")
                inserted_games = 0
                for canonical_batch in iter_canonical_rows(final_sqlite):
                    game_payload = []
                    for row in canonical_batch:
                        preview = preview_rows.get(int(row["appid"]), {})
                        canonical_vectors = _clean_canonical_vectors(row["canonical_vectors_json"])
                        canonical_metadata = _clean_canonical_metadata(row["canonical_metadata_json"])
                        game_payload.append(
                            (
                                int(row["appid"]),
                                row["name"],
                                normalize_search_text(row["name"] or ""),
                                Jsonb(canonical_vectors),
                                Jsonb(canonical_metadata),
                                Jsonb(json.loads(row["source_review_samples_json"] or "{}")),
                                Jsonb(json.loads(row["source_vectors_json"] or "{}")),
                                Jsonb(json.loads(row["source_metadata_json"] or "{}")),
                                preview.get("metacritic_score"),
                                preview.get("recommendations_total"),
                                preview.get("steamspy_owner_estimate"),
                                preview.get("steamspy_ccu"),
                                preview.get("positive"),
                                preview.get("negative"),
                                preview.get("estimated_review_count"),
                                preview.get("release_date_parsed"),
                                (preview.get("short_description") or "").strip(),
                                preview.get("header_image") or "",
                                preview.get("capsule_image") or "",
                                preview.get("capsule_imagev5") or "",
                                preview.get("background_image") or "",
                                preview.get("background_image_raw") or "",
                                preview.get("logo_image") or "",
                                preview.get("library_hero_image") or "",
                                preview.get("library_capsule_image") or "",
                                Jsonb(json.loads(preview.get("developers_json") or "[]")),
                                Jsonb(json.loads(preview.get("publishers_json") or "[]")),
                                preview.get("release_date_text") or "",
                            )
                        )
                    insert_game_batch(cursor, game_payload)
                    inserted_games += len(game_payload)
                    log(f"Inserted games: {inserted_games}/{canonical_row_count}")

                log("Preparing and inserting screenshots in batches")
                inserted_screenshots = 0
                for screenshot_batch in iter_screenshots(final_sqlite):
                    screenshot_payload = [
                        (
                            int(row["appid"]),
                            int(row["screenshot_id"]),
                            str(row["path_thumbnail"] or ""),
                            str(row["path_full"] or ""),
                        )
                        for row in screenshot_batch
                    ]
                    insert_screenshot_batch(cursor, screenshot_payload)
                    inserted_screenshots += len(screenshot_payload)
                    log(
                        "Inserted screenshots: "
                        f"{inserted_screenshots}/{screenshot_count}"
                    )

                log("Marking pipeline run complete")
                cursor.execute(
                    """
                    UPDATE pipeline_runs
                    SET finished_at = NOW(), status = 'completed', processed_rows = %s
                    WHERE id = %s
                    """,
                    (canonical_row_count, run_id),
                )
            pg_connection.commit()
            log("Postgres import committed")
    except Exception:
        log("Import failed; attempting to mark pipeline run as failed")
        with psycopg.connect(postgres_dsn()) as pg_connection:
            with pg_connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.pipeline_runs')")
                pipeline_runs_table = cursor.fetchone()[0]
                if not pipeline_runs_table:
                    pg_connection.commit()
                    raise
                cursor.execute(
                    """
                    UPDATE pipeline_runs
                    SET finished_at = NOW(), status = 'failed'
                    WHERE id = (SELECT max(id) FROM pipeline_runs)
                    """
                )
            pg_connection.commit()
        raise
    finally:
        metadata_sqlite.close()
        final_sqlite.close()
        log("SQLite connections closed")

    log("SQLite -> Postgres import complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
