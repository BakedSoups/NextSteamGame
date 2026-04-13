#!/usr/bin/env python3

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


FINAL_DB_PATH = Path("data/steam_final_canon.db")
BASE_GAME_QUERY = "Counter-Strike"
RESULT_LIMIT = 15

# Prototype user adjustments on top of the selected game's profile.
# For now:
# - ignore micro_tags
# - use genre_tree only
# - broader genre levels get a 10% penalty each step back
VECTOR_CONTEXT_MULTIPLIERS = {
    "mechanics": 1.35,
    "narrative": 0.20,
    "vibe": 0.35,
    "structure_loop": 1.20,
    "uniqueness": 0.55,
}

VECTOR_TAG_MULTIPLIERS = {
    "mechanics": {
        "teamplay": 1.30,
        "strategy": 1.20,
        "shooting": 1.15,
    },
    "structure_loop": {
        "matches": 1.20,
        "rounds": 1.25,
        "skill progression": 1.10,
    },
}

ADDED_GENRE_TREE = {
    "primary": [],
    "sub": [],
    "traits": ["Team Based", "Competitive"],
}

REMOVED_GENRE_TREE = {
    "primary": [],
    "sub": [],
    "traits": [],
}

GENRE_BRANCH_WEIGHTS = {
    "primary": 0.8,
    "sub": 0.9,
    "traits": 1.0,
}

VECTOR_SCORE_WEIGHT = 0.55
GENRE_SCORE_WEIGHT = 0.45


def _load_games(db_path: Path) -> list[sqlite3.Row]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(
            """
            SELECT appid, name, canonical_vectors_json, canonical_metadata_json
            FROM canonical_game_semantics
            ORDER BY appid
            """
        ).fetchall()
    finally:
        connection.close()


def _find_base_game(rows: list[sqlite3.Row], query: str) -> sqlite3.Row:
    lowered = query.lower()
    exact = [row for row in rows if row["name"] and row["name"].lower() == lowered]
    if exact:
        return exact[0]
    partial = [row for row in rows if row["name"] and lowered in row["name"].lower()]
    if partial:
        return partial[0]
    raise RuntimeError(f"Could not find a game matching {query!r}")


def _normalize_weights(tag_weights: dict[str, int | float]) -> dict[str, float]:
    total = sum(float(value) for value in tag_weights.values())
    if total <= 0:
        return {}
    return {tag: float(value) / total for tag, value in tag_weights.items()}


def _build_vector_preferences(vectors: dict[str, dict[str, int]]) -> dict[str, dict[str, float]]:
    preferences: dict[str, dict[str, float]] = {}
    for context, tag_weights in vectors.items():
        normalized = _normalize_weights(tag_weights)
        context_multiplier = VECTOR_CONTEXT_MULTIPLIERS.get(context, 1.0)
        adjusted: dict[str, float] = {}
        for tag, weight in normalized.items():
            adjusted_weight = weight * context_multiplier
            adjusted_weight *= VECTOR_TAG_MULTIPLIERS.get(context, {}).get(tag, 1.0)
            adjusted[tag] = adjusted_weight
        preferences[context] = adjusted
    return preferences


def _build_genre_preferences(metadata: dict) -> dict[str, dict[str, float]]:
    genre_tree = metadata.get("genre_tree", {})
    preferences: dict[str, dict[str, float]] = {}
    for branch in ("primary", "sub", "traits"):
        branch_tags = set(genre_tree.get(branch, []))
        branch_tags.update(ADDED_GENRE_TREE.get(branch, []))
        branch_tags.difference_update(REMOVED_GENRE_TREE.get(branch, []))
        preferences[branch] = {
            tag: GENRE_BRANCH_WEIGHTS[branch]
            for tag in sorted(branch_tags)
        }
    return preferences


def _vector_match_score(
    candidate_vectors: dict[str, dict[str, int]],
    preferences: dict[str, dict[str, float]],
) -> float:
    total = 0.0
    contexts_seen = 0
    for context, preferred_weights in preferences.items():
        if not preferred_weights:
            continue
        candidate_weights = _normalize_weights(candidate_vectors.get(context, {}))
        overlap = 0.0
        for tag, preferred_weight in preferred_weights.items():
            overlap += min(preferred_weight, candidate_weights.get(tag, 0.0))
        total += overlap
        contexts_seen += 1
    return total / max(contexts_seen, 1)


def _genre_match_score(
    candidate_metadata: dict,
    preferences: dict[str, dict[str, float]],
) -> float:
    genre_tree = candidate_metadata.get("genre_tree", {})
    total_weight = sum(sum(branch.values()) for branch in preferences.values()) or 1.0
    matched_weight = 0.0
    for branch, tag_weights in preferences.items():
        candidate_tags = set(genre_tree.get(branch, []))
        for tag, weight in tag_weights.items():
            if tag in candidate_tags:
                matched_weight += weight
    return matched_weight / total_weight


def _score_candidates(rows: list[sqlite3.Row], base_row: sqlite3.Row) -> list[dict]:
    base_vectors = json.loads(base_row["canonical_vectors_json"])
    base_metadata = json.loads(base_row["canonical_metadata_json"])
    vector_preferences = _build_vector_preferences(base_vectors)
    genre_preferences = _build_genre_preferences(base_metadata)

    scored = []
    for row in rows:
        if int(row["appid"]) == int(base_row["appid"]):
            continue
        candidate_vectors = json.loads(row["canonical_vectors_json"])
        candidate_metadata = json.loads(row["canonical_metadata_json"])
        candidate_genre_tree = candidate_metadata.get("genre_tree", {})

        vector_score = _vector_match_score(candidate_vectors, vector_preferences)
        genre_score = _genre_match_score(candidate_metadata, genre_preferences)
        total_score = (vector_score * VECTOR_SCORE_WEIGHT) + (genre_score * GENRE_SCORE_WEIGHT)

        primary_tags = set(candidate_genre_tree.get("primary", []))
        sub_tags = set(candidate_genre_tree.get("sub", []))

        if "Shooter" not in primary_tags:
            total_score *= 0.75

        if not (
            {"First Person Shooter", "Tactical Shooter", "Multiplayer Shooter", "Team Shooter"} & sub_tags
        ):
            total_score *= 0.80

        if {"Sports", "Party Game", "Fighting", "VR"} & primary_tags:
            total_score *= 0.78

        scored.append(
            {
                "appid": int(row["appid"]),
                "name": row["name"],
                "total_score": total_score,
                "vector_score": vector_score,
                "genre_score": genre_score,
                "metadata": candidate_metadata,
                "vectors": candidate_vectors,
            }
        )

    scored.sort(key=lambda item: (-item["total_score"], -item["vector_score"], item["name"].lower()))
    return scored


def main() -> int:
    rows = _load_games(FINAL_DB_PATH)
    base_row = _find_base_game(rows, BASE_GAME_QUERY)
    base_vectors = json.loads(base_row["canonical_vectors_json"])
    base_metadata = json.loads(base_row["canonical_metadata_json"])
    genre_preferences = _build_genre_preferences(base_metadata)
    scored = _score_candidates(rows, base_row)

    print(f"Base game: {base_row['name']} ({base_row['appid']})")
    print("\nBase vectors:")
    print(json.dumps(base_vectors, indent=2, sort_keys=True))
    print("\nBase genre tree:")
    print(json.dumps(base_metadata.get("genre_tree", {}), indent=2, sort_keys=True))
    print("\nPrototype adjusted genre preferences:")
    print(json.dumps(genre_preferences, indent=2, sort_keys=True))
    print("\nTop matches:")
    for rank, item in enumerate(scored[:RESULT_LIMIT], start=1):
        primary = item["metadata"].get("genre_tree", {}).get("primary", [])
        sub = item["metadata"].get("genre_tree", {}).get("sub", [])
        print(
            f"{rank:02d}. {item['name']} ({item['appid']}) "
            f"score={item['total_score']:.4f} "
            f"vector={item['vector_score']:.4f} "
            f"genre={item['genre_score']:.4f}"
        )
        print(f"    primary={primary[:3]} sub={sub[:3]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
