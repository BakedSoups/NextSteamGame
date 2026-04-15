from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Callable


BATCH_SIZE = 500
COLLECTION_NAME = "steam_final_canon"


def _count_rows(db_path: Path) -> int:
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute("SELECT COUNT(*) FROM canonical_game_semantics").fetchone()
        return int(row[0]) if row else 0
    finally:
        connection.close()


def _iter_rows(db_path: Path, batch_size: int):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        cursor = connection.execute(
            """
            SELECT appid, name, canonical_vectors_json, canonical_metadata_json
            FROM canonical_game_semantics
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


def _build_retrieval_document(row: sqlite3.Row) -> str:
    metadata = json.loads(row["canonical_metadata_json"])
    vectors = json.loads(row["canonical_vectors_json"])

    parts = [str(row["name"] or "").strip()]
    signature_tag = str(metadata.get("signature_tag", "")).strip()
    if signature_tag:
        parts.append(signature_tag)

    for branch in ("primary", "sub", "sub_sub", "traits"):
        for tag in metadata.get("genre_tree", {}).get(branch, []):
            if tag:
                parts.append(str(tag))

    for tag in metadata.get("micro_tags", []):
        if tag:
            parts.append(str(tag))

    for tag in metadata.get("soundtrack_tags", []):
        if tag:
            parts.append(str(tag))

    for context, tag_weights in vectors.items():
        for tag in tag_weights:
            if tag:
                parts.append(f"{context}:{tag}")

    return "\n".join(part for part in parts if part)


def _ensure_chroma_client(chroma_dir_path: Path):
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError(
            "Chroma is not installed. Install `chromadb` before running this stage."
        ) from exc

    chroma_dir_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(chroma_dir_path))


def run_chroma_migration(
    *,
    final_db_path: Path,
    chroma_dir_path: Path,
    progress: Callable[[dict], None] | None = None,
) -> dict:
    client = _ensure_chroma_client(chroma_dir_path)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    total_rows = _count_rows(final_db_path)
    processed_rows = 0
    batch_number = 0

    for rows in _iter_rows(final_db_path, batch_size=BATCH_SIZE):
        batch_number += 1
        ids = []
        documents = []
        metadatas = []

        for row in rows:
            metadata = json.loads(row["canonical_metadata_json"])
            ids.append(str(int(row["appid"])))
            documents.append(_build_retrieval_document(row))
            metadatas.append(
                {
                    "appid": int(row["appid"]),
                    "name": str(row["name"] or ""),
                    "signature_tag": str(metadata.get("signature_tag", "")).strip(),
                }
            )

        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        processed_rows += len(rows)

        if progress is not None:
            progress(
                {
                    "batch_number": batch_number,
                    "processed_rows": processed_rows,
                    "total_rows": total_rows,
                }
            )

    return {
        "status": "completed",
        "processed_rows": processed_rows,
        "collection_name": COLLECTION_NAME,
        "chroma_dir_path": str(chroma_dir_path),
    }
