from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Dict, Iterator

from .defaults import METADATA_CONTEXTS, VECTOR_CONTEXTS


def count_rows(db_path: Path) -> int:
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute("SELECT COUNT(*) FROM raw_game_semantics").fetchone()
        return int(row[0]) if row else 0
    finally:
        connection.close()


def iter_row_batches(db_path: Path, batch_size: int) -> Iterator[list[sqlite3.Row]]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        cursor = connection.execute(
            """
            SELECT appid, name, vectors_json, metadata_json
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


def empty_metadata_counters() -> Dict[str, Counter]:
    return {context: Counter() for context in METADATA_CONTEXTS}


def empty_vector_counters() -> Dict[str, Counter]:
    return {context: Counter() for context in VECTOR_CONTEXTS}


def collect_batch_counters(rows: list[sqlite3.Row]) -> tuple[Dict[str, Counter], Dict[str, Counter]]:
    metadata_counters = empty_metadata_counters()
    vector_counters = empty_vector_counters()

    for row in rows:
        metadata = json.loads(row["metadata_json"] or "{}")
        vectors = json.loads(row["vectors_json"] or "{}")

        for tag in metadata.get("micro_tags", []) or []:
            metadata_counters["micro_tags"][str(tag).strip()] += 1
        signature_tag = str(metadata.get("signature_tag", "")).strip()
        if signature_tag:
            metadata_counters["signature_tag"][signature_tag] += 1
        for tag in metadata.get("niche_anchors", []) or []:
            metadata_counters["niche_anchors"][str(tag).strip()] += 1
        for tag in metadata.get("identity_tags", []) or []:
            metadata_counters["identity_tags"][str(tag).strip()] += 1
        for tag in metadata.get("setting_tags", []) or []:
            metadata_counters["setting_tags"][str(tag).strip()] += 1
        for field in ("music_primary", "music_secondary"):
            value = str(metadata.get(field, "")).strip()
            if value:
                metadata_counters[field][value] += 1

        genre_tree = metadata.get("genre_tree") or {}
        for branch in ("primary", "sub", "sub_sub"):
            value = str(genre_tree.get(branch, "")).strip()
            if value:
                metadata_counters[f"genre_tree.{branch}"][value] += 1

        for context in VECTOR_CONTEXTS:
            weights = vectors.get(context) or {}
            if not isinstance(weights, dict):
                continue
            for tag in weights:
                vector_counters[context][str(tag).strip()] += 1

    return metadata_counters, vector_counters


def merge_counter_maps(target: Dict[str, Counter], source: Dict[str, Counter]) -> None:
    for context, counter in source.items():
        target[context].update(counter)
