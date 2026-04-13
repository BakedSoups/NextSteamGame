from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Dict, Iterator, Sequence


def normalize_tag_text(tag: str) -> str:
    return tag.strip().lower().replace("_", " ").replace("-", " ")


def collapse_normalized_counter(counter: Counter) -> tuple[Counter, Dict[str, Counter]]:
    collapsed = Counter()
    raw_members: Dict[str, Counter] = {}
    for tag, count in counter.items():
        normalized = normalize_tag_text(tag)
        collapsed[normalized] += count
        raw_members.setdefault(normalized, Counter())[tag] += count
    return collapsed, raw_members


def collapse_counter_map(
    counters: Dict[str, Counter],
) -> tuple[Dict[str, Counter], Dict[str, Dict[str, Counter]]]:
    collapsed_map: Dict[str, Counter] = {}
    raw_member_map: Dict[str, Dict[str, Counter]] = {}
    for context, counter in counters.items():
        collapsed_counter, raw_members = collapse_normalized_counter(counter)
        collapsed_map[context] = collapsed_counter
        raw_member_map[context] = raw_members
    return collapsed_map, raw_member_map


def load_rows(db_path: Path, sample_size: int | None = None) -> Sequence[sqlite3.Row]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        query = """
            SELECT appid, name, vectors_json, metadata_json
            FROM raw_game_semantics
        """
        params: tuple[object, ...] = ()
        if sample_size is not None:
            query += " ORDER BY RANDOM() LIMIT ?"
            params = (sample_size,)
        else:
            query += " ORDER BY appid"
        return connection.execute(query, params).fetchall()
    finally:
        connection.close()


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


def collect_vector_counters(rows: Sequence[sqlite3.Row]) -> Dict[str, Counter]:
    counters: Dict[str, Counter] = {}
    for row in rows:
        vectors = json.loads(row["vectors_json"])
        for context, tag_weights in vectors.items():
            bucket = counters.setdefault(context, Counter())
            for tag in tag_weights:
                bucket[tag] += 1
    return counters


def collect_metadata_counters(rows: Sequence[sqlite3.Row]) -> Dict[str, Counter]:
    counters: Dict[str, Counter] = {
        "micro_tags": Counter(),
        "signature_tag": Counter(),
        "soundtrack_tags": Counter(),
        "genre_tree.primary": Counter(),
        "genre_tree.sub": Counter(),
        "genre_tree.traits": Counter(),
    }
    for row in rows:
        metadata = json.loads(row["metadata_json"])
        for tag in metadata.get("micro_tags", []):
            counters["micro_tags"][tag] += 1
        signature_tag = str(metadata.get("signature_tag", "")).strip()
        if signature_tag:
            counters["signature_tag"][signature_tag] += 1
        for tag in metadata.get("soundtrack_tags", []):
            counters["soundtrack_tags"][tag] += 1
        genre_tree = metadata.get("genre_tree", {})
        for branch in ("primary", "sub", "traits"):
            for tag in genre_tree.get(branch, []):
                counters[f"genre_tree.{branch}"][tag] += 1
    return counters


def filter_counters_by_seed_tags(counters: Dict[str, Counter], seed_tags: Sequence[str]) -> Dict[str, Counter]:
    if not seed_tags:
        return counters

    normalized_seeds = [normalize_tag_text(tag) for tag in seed_tags if tag.strip()]
    filtered: Dict[str, Counter] = {}
    for context, counter in counters.items():
        matching = Counter()
        for tag, count in counter.items():
            normalized_tag = normalize_tag_text(tag)
            if any(seed in normalized_tag for seed in normalized_seeds):
                matching[tag] = count
        if matching:
            filtered[context] = matching
    return filtered
