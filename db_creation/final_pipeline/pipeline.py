from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict

from db_creation.canon_pipeline.layer_1_normalization import normalize_tag
from db_creation.paths import analysis_dir, final_canon_db_path, initial_noncanon_db_path


BATCH_SIZE = 500
NONCANON_DB_PATH = initial_noncanon_db_path()
OUTPUT_DB_PATH = final_canon_db_path()
ANALYSIS_DIR = analysis_dir()
CANON_GROUPS_CSV_PATH = ANALYSIS_DIR / "canon_groups_v6.csv"
VECTOR_CONTEXTS = {"mechanics", "narrative", "vibe", "structure_loop"}


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _count_rows(db_path: Path) -> int:
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute("SELECT COUNT(*) FROM raw_game_semantics").fetchone()
        return int(row[0]) if row else 0
    finally:
        connection.close()


def _iter_noncanon_batches(db_path: Path, batch_size: int):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        cursor = connection.execute(
            """
            SELECT appid, name, review_samples_json, vectors_json, metadata_json
            FROM raw_game_semantics
            ORDER BY appid
            """
        )
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            yield rows
    finally:
        connection.close()


def _split_members(raw_value: str) -> list[str]:
    if not raw_value.strip():
        return []
    return [member.strip() for member in raw_value.split(" | ") if member.strip()]


def _iter_text_values(raw: object) -> list[str]:
    if isinstance(raw, str):
        text = raw.strip()
        return [text] if text else []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def _canonicalize_single_tag(raw: object, context: str, mapping: Dict[str, Dict[str, str]]) -> str:
    for tag in _iter_text_values(raw):
        return mapping.get(context, {}).get(normalize_tag(tag), tag)
    return ""


def _canonicalize_tag_list(raw: object, context: str, mapping: Dict[str, Dict[str, str]]) -> list[str]:
    canonicalized: list[str] = []
    seen = set()
    for tag in _iter_text_values(raw):
        canonical = mapping.get(context, {}).get(normalize_tag(tag), tag)
        if canonical not in seen:
            seen.add(canonical)
            canonicalized.append(canonical)
    return canonicalized


def _group_family_for_context(context: str) -> str:
    return "vectors" if context in VECTOR_CONTEXTS else "metadata"


def load_group_csv(csv_path: Path) -> dict:
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing canonical groups CSV: {csv_path}")

    groups = []
    mapping: Dict[str, Dict[str, str]] = {}
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            context = row["context"]
            representative = row["final_tag"].strip() or row["canon_tag"].strip()
            if not representative:
                continue
            members = _split_members(row["member_tags"])
            groups.append(
                {
                    "source_family": _group_family_for_context(context),
                    "context": context,
                    "representative_tag": representative,
                    "parent_tag": representative,
                    "specificity_level": 1,
                    "member_count": int(row.get("member_count", 0) or 0),
                    "total_occurrences": int(row.get("total_occurrences", 0) or 0),
                    "members": members,
                }
            )
            context_map = mapping.setdefault(context, {})
            context_map[normalize_tag(representative)] = representative
            for member in members:
                context_map[normalize_tag(member)] = representative

    return {
        "groups": groups,
        "mapping": mapping,
    }


def _canonicalize_metadata(metadata: Dict, mapping: Dict[str, Dict[str, str]]) -> Dict:
    status = str(metadata.get("status", "")).strip()
    canon_micro = _canonicalize_tag_list(metadata.get("micro_tags", []), "micro_tags", mapping)
    canon_niche_anchors = _canonicalize_tag_list(metadata.get("niche_anchors", []), "niche_anchors", mapping)
    canon_identity_tags = _canonicalize_tag_list(metadata.get("identity_tags", []), "identity_tags", mapping)
    canon_setting_tags = _canonicalize_tag_list(metadata.get("setting_tags", []), "setting_tags", mapping)

    genre_tree = metadata.get("genre_tree", {})
    canon_tree = {
        "primary": _canonicalize_single_tag(genre_tree.get("primary"), "genre_tree.primary", mapping),
        "sub": _canonicalize_single_tag(genre_tree.get("sub"), "genre_tree.sub", mapping),
        "sub_sub": _canonicalize_single_tag(genre_tree.get("sub_sub"), "genre_tree.sub_sub", mapping),
    }

    raw_signature_tag = str(metadata.get("signature_tag", "")).strip()
    canonical_signature_tag = ""
    if raw_signature_tag:
        canonical_signature_tag = mapping.get("signature_tag", {}).get(
            normalize_tag(raw_signature_tag),
            raw_signature_tag,
        )
    music_primary = _canonicalize_single_tag(metadata.get("music_primary"), "music_primary", mapping)
    music_secondary = _canonicalize_single_tag(metadata.get("music_secondary"), "music_secondary", mapping)
    if not music_primary and not music_secondary:
        legacy_soundtrack = _canonicalize_tag_list(metadata.get("soundtrack_tags", []), "music_primary", mapping)
        if legacy_soundtrack:
            music_primary = legacy_soundtrack[0]
        if len(legacy_soundtrack) > 1:
            music_secondary = legacy_soundtrack[1]
    appeal_axes = dict(metadata.get("appeal_axes") or {})

    canonical_metadata = {
        "micro_tags": canon_micro,
        "signature_tag": canonical_signature_tag,
        "niche_anchors": canon_niche_anchors,
        "identity_tags": canon_identity_tags,
        "setting_tags": canon_setting_tags,
        "music_primary": music_primary,
        "music_secondary": music_secondary,
        "appeal_axes": appeal_axes,
        "genre_tree": canon_tree,
    }
    if status:
        canonical_metadata["status"] = status
    return canonical_metadata


def _canonicalize_vectors(vectors: Dict, mapping: Dict[str, Dict[str, str]]) -> Dict:
    canonical_vectors: Dict[str, Dict[str, int]] = {}
    status = str(vectors.get("status", "")).strip()
    for context, tag_weights in vectors.items():
        if context not in VECTOR_CONTEXTS or not isinstance(tag_weights, dict):
            continue
        merged: Dict[str, int] = {}
        for tag, weight in tag_weights.items():
            canonical = mapping.get(context, {}).get(normalize_tag(tag), tag)
            try:
                merged[canonical] = merged.get(canonical, 0) + int(weight)
            except (TypeError, ValueError):
                continue
        canonical_vectors[context] = dict(
            sorted(merged.items(), key=lambda item: (-item[1], item[0]))
        )
    if status:
        canonical_vectors["status"] = status
    return canonical_vectors


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS final_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            processed_rows INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS canonical_tag_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            source_family TEXT NOT NULL,
            context TEXT NOT NULL,
            representative_tag TEXT NOT NULL,
            parent_tag TEXT NOT NULL,
            specificity_level INTEGER NOT NULL DEFAULT 1,
            member_count INTEGER NOT NULL,
            total_occurrences INTEGER NOT NULL,
            FOREIGN KEY (run_id) REFERENCES final_runs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS canonical_tag_members (
            group_id INTEGER NOT NULL,
            member_tag TEXT NOT NULL,
            PRIMARY KEY (group_id, member_tag),
            FOREIGN KEY (group_id) REFERENCES canonical_tag_groups(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS canonical_game_semantics (
            appid INTEGER PRIMARY KEY,
            name TEXT,
            canonical_vectors_json TEXT NOT NULL,
            canonical_metadata_json TEXT NOT NULL,
            source_review_samples_json TEXT NOT NULL,
            source_vectors_json TEXT NOT NULL,
            source_metadata_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )


def _ensure_schema_columns(connection: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(canonical_tag_groups)")
    }
    if "parent_tag" not in columns:
        connection.execute(
            "ALTER TABLE canonical_tag_groups ADD COLUMN parent_tag TEXT NOT NULL DEFAULT ''"
        )
    if "specificity_level" not in columns:
        connection.execute(
            "ALTER TABLE canonical_tag_groups ADD COLUMN specificity_level INTEGER NOT NULL DEFAULT 1"
        )


def _start_run(connection: sqlite3.Connection) -> int:
    cursor = connection.execute(
        "INSERT INTO final_runs (started_at, status) VALUES (?, 'running')",
        (utcnow_iso(),),
    )
    return int(cursor.lastrowid)


def _finish_run(connection: sqlite3.Connection, run_id: int, status: str, processed_rows: int) -> None:
    connection.execute(
        """
        UPDATE final_runs
        SET finished_at = ?, status = ?, processed_rows = ?
        WHERE id = ?
        """,
        (utcnow_iso(), status, processed_rows, run_id),
    )


def _store_loaded_groups(connection: sqlite3.Connection, run_id: int, loaded: dict) -> None:
    for group in loaded["groups"]:
        cursor = connection.execute(
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                group["source_family"],
                group["context"],
                group["representative_tag"],
                group["parent_tag"],
                group["specificity_level"],
                group["member_count"],
                group["total_occurrences"],
            ),
        )
        group_id = int(cursor.lastrowid)
        connection.executemany(
            """
            INSERT INTO canonical_tag_members (group_id, member_tag)
            VALUES (?, ?)
            """,
            [(group_id, member) for member in group["members"]],
        )


def _store_games(
    connection: sqlite3.Connection,
    noncanon_db_path: Path,
    batch_size: int,
    metadata_mapping: Dict[str, Dict[str, str]],
    vector_mapping: Dict[str, Dict[str, str]],
    progress: Callable[[dict], None] | None = None,
) -> int:
    processed_rows = 0
    total_rows = _count_rows(noncanon_db_path)

    for batch_number, rows in enumerate(_iter_noncanon_batches(noncanon_db_path, batch_size), start=1):
        timestamp = utcnow_iso()
        payload = []
        for row in rows:
            source_vectors = json.loads(row["vectors_json"])
            source_metadata = json.loads(row["metadata_json"])
            payload.append(
                (
                    int(row["appid"]),
                    row["name"],
                    json.dumps(
                        _canonicalize_vectors(source_vectors, vector_mapping),
                        ensure_ascii=True,
                        sort_keys=True,
                    ),
                    json.dumps(
                        _canonicalize_metadata(source_metadata, metadata_mapping),
                        ensure_ascii=True,
                        sort_keys=True,
                    ),
                    row["review_samples_json"] or "{}",
                    row["vectors_json"],
                    row["metadata_json"],
                    timestamp,
                    timestamp,
                )
            )

        connection.executemany(
            """
            INSERT INTO canonical_game_semantics (
                appid,
                name,
                canonical_vectors_json,
                canonical_metadata_json,
                source_review_samples_json,
                source_vectors_json,
                source_metadata_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(appid) DO UPDATE SET
                name = excluded.name,
                canonical_vectors_json = excluded.canonical_vectors_json,
                canonical_metadata_json = excluded.canonical_metadata_json,
                source_review_samples_json = excluded.source_review_samples_json,
                source_vectors_json = excluded.source_vectors_json,
                source_metadata_json = excluded.source_metadata_json,
                updated_at = excluded.updated_at
            """,
            payload,
        )
        connection.commit()
        processed_rows += len(rows)
        if progress is not None:
            progress(
                {
                    "batch_number": batch_number,
                    "processed_rows": processed_rows,
                    "total_rows": total_rows,
                }
            )

    return processed_rows


def run_final_db_build(
    noncanon_db_path: Path = NONCANON_DB_PATH,
    output_db_path: Path = OUTPUT_DB_PATH,
    canon_groups_csv_path: Path = CANON_GROUPS_CSV_PATH,
    batch_size: int = BATCH_SIZE,
    progress: Callable[[dict], None] | None = None,
) -> dict:
    loaded_groups = load_group_csv(canon_groups_csv_path)

    output_db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(output_db_path)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        create_schema(connection)
        _ensure_schema_columns(connection)
        run_id = _start_run(connection)
        status = "completed"
        processed_rows = 0
        try:
            connection.execute("DELETE FROM canonical_tag_members")
            connection.execute("DELETE FROM canonical_tag_groups")
            connection.execute("DELETE FROM canonical_game_semantics")
            _store_loaded_groups(connection, run_id, loaded_groups)
            connection.commit()
            processed_rows = _store_games(
                connection,
                noncanon_db_path,
                batch_size,
                loaded_groups["mapping"],
                loaded_groups["mapping"],
                progress=progress,
            )
        except Exception:
            status = "failed"
            raise
        finally:
            _finish_run(connection, run_id, status, processed_rows)
            connection.commit()
    finally:
        connection.close()

    return {
        "run_id": run_id,
        "status": status,
        "processed_rows": processed_rows,
        "canon_groups": len(loaded_groups["groups"]),
        "output_db_path": str(output_db_path),
    }
