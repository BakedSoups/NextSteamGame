#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

from db_creation.paths import final_canon_db_path, metadata_db_path


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


def load_tag_groups(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    return connection.execute(
        """
        SELECT
            id,
            source_family,
            context,
            representative_tag,
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


def main() -> int:
    try:
        import psycopg
        from psycopg.types.json import Jsonb
    except ImportError as exc:
        raise RuntimeError(
            "Postgres support requires psycopg. Install dependencies from requirements.txt."
        ) from exc

    with schema_path().open("r", encoding="utf-8") as handle:
        schema_sql = handle.read()

    metadata_sqlite = sqlite3.connect(metadata_db_path())
    final_sqlite = sqlite3.connect(final_canon_db_path())

    try:
        preview_rows = load_preview_rows(metadata_sqlite)
        canonical_rows = load_canonical_rows(final_sqlite)
        tag_groups = load_tag_groups(final_sqlite)
        tag_members = load_tag_members(final_sqlite)

        with psycopg.connect(postgres_dsn()) as pg_connection:
            with pg_connection.cursor() as cursor:
                cursor.execute(schema_sql)
                cursor.execute(
                    "INSERT INTO pipeline_runs (status) VALUES ('running') RETURNING id"
                )
                run_id = int(cursor.fetchone()[0])

                cursor.execute("DELETE FROM canonical_tag_members")
                cursor.execute("DELETE FROM canonical_tag_groups")
                cursor.execute("DELETE FROM games")

                group_id_map: dict[int, int] = {}
                for group in tag_groups:
                    cursor.execute(
                        """
                        INSERT INTO canonical_tag_groups (
                            run_id,
                            source_family,
                            context,
                            representative_tag,
                            member_count,
                            total_occurrences
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            run_id,
                            group["source_family"],
                            group["context"],
                            group["representative_tag"],
                            int(group["member_count"]),
                            int(group["total_occurrences"]),
                        ),
                    )
                    group_id_map[int(group["id"])] = int(cursor.fetchone()[0])

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

                game_payload = []
                for row in canonical_rows:
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

                cursor.execute(
                    """
                    UPDATE pipeline_runs
                    SET finished_at = NOW(), status = 'completed', processed_rows = %s
                    WHERE id = %s
                    """,
                    (len(game_payload), run_id),
                )
            pg_connection.commit()
    except Exception:
        with psycopg.connect(postgres_dsn()) as pg_connection:
            with pg_connection.cursor() as cursor:
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
