from __future__ import annotations

from typing import Iterable


VECTOR_CONTEXT_MULTIPLIERS = {
    "mechanics": 1.35,
    "narrative": 0.20,
    "vibe": 0.35,
    "structure_loop": 1.20,
    "uniqueness": 0.55,
}

DEFAULT_VECTOR_BOOSTS = {
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

GENRE_BRANCH_WEIGHTS = {
    "primary": 0.8,
    "sub": 0.9,
    "traits": 1.0,
}

VECTOR_SCORE_WEIGHT = 0.55
GENRE_SCORE_WEIGHT = 0.45


def _top_branch_tags(metadata: dict, branch: str, limit: int) -> list[str]:
    tags = metadata.get("genre_tree", {}).get(branch, [])
    return [tag for tag in tags[:limit] if tag]


def _normalize_weights(tag_weights: dict[str, int | float]) -> dict[str, float]:
    total = sum(float(value) for value in tag_weights.values())
    if total <= 0:
        return {}
    return {tag: float(value) / total for tag, value in tag_weights.items()}


def _build_vector_preferences(
    vectors: dict[str, dict[str, int]],
    extra_boosts: dict[str, dict[str, float]] | None = None,
) -> dict[str, dict[str, float]]:
    boosts = extra_boosts or {}
    preferences: dict[str, dict[str, float]] = {}
    for context, tag_weights in vectors.items():
        normalized = _normalize_weights(tag_weights)
        context_multiplier = VECTOR_CONTEXT_MULTIPLIERS.get(context, 1.0)
        adjusted: dict[str, float] = {}
        for tag, weight in normalized.items():
            adjusted_weight = weight * context_multiplier
            adjusted_weight *= DEFAULT_VECTOR_BOOSTS.get(context, {}).get(tag, 1.0)
            adjusted_weight *= boosts.get(context, {}).get(tag, 1.0)
            adjusted[tag] = adjusted_weight
        preferences[context] = adjusted
    return preferences


def _build_genre_preferences(
    metadata: dict,
    added_genres: dict[str, list[str]] | None = None,
    removed_genres: dict[str, list[str]] | None = None,
) -> dict[str, dict[str, float]]:
    genre_tree = metadata.get("genre_tree", {})
    added = added_genres or {"primary": [], "sub": [], "traits": []}
    removed = removed_genres or {"primary": [], "sub": [], "traits": []}
    preferences: dict[str, dict[str, float]] = {}
    for branch in ("primary", "sub", "traits"):
        branch_tags = set(genre_tree.get(branch, []))
        branch_tags.update(added.get(branch, []))
        branch_tags.difference_update(removed.get(branch, []))
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


def _apply_penalties(total_score: float, base_metadata: dict, candidate_metadata: dict) -> float:
    base_tree = base_metadata.get("genre_tree", {})
    genre_tree = candidate_metadata.get("genre_tree", {})
    base_primary = set(base_tree.get("primary", []))
    base_sub = set(base_tree.get("sub", []))
    base_traits = set(base_tree.get("traits", []))
    primary_tags = set(genre_tree.get("primary", []))
    sub_tags = set(genre_tree.get("sub", []))
    trait_tags = set(genre_tree.get("traits", []))

    primary_overlap = len(base_primary & primary_tags)
    sub_overlap = len(base_sub & sub_tags)
    trait_overlap = len(base_traits & trait_tags)

    if base_primary and primary_overlap == 0:
        total_score *= 0.82
    if base_sub and sub_overlap == 0:
        total_score *= 0.88
    if base_traits and trait_overlap == 0:
        total_score *= 0.94

    if base_primary:
        contradictory_primary = primary_tags - base_primary
        if len(contradictory_primary) >= 3 and primary_overlap == 0:
            total_score *= 0.88

    if base_sub:
        contradictory_sub = sub_tags - base_sub
        if len(contradictory_sub) >= 3 and sub_overlap == 0:
            total_score *= 0.90

    base_anchor_primary = set(_top_branch_tags(base_metadata, "primary", 2))
    base_anchor_sub = set(_top_branch_tags(base_metadata, "sub", 3))
    base_anchor_traits = set(_top_branch_tags(base_metadata, "traits", 4))

    if base_anchor_primary and (base_anchor_primary & primary_tags):
        total_score *= 1.08
    if base_anchor_sub and (base_anchor_sub & sub_tags):
        total_score *= 1.12
    if base_anchor_traits and (base_anchor_traits & trait_tags):
        total_score *= 1.05

    return total_score


def recommend_games(
    base_game: dict,
    candidate_games: Iterable[dict],
    *,
    extra_vector_boosts: dict[str, dict[str, float]] | None = None,
    added_genres: dict[str, list[str]] | None = None,
    removed_genres: dict[str, list[str]] | None = None,
    limit: int = 15,
) -> list[dict]:
    vector_preferences = _build_vector_preferences(base_game["vectors"], extra_vector_boosts)
    genre_preferences = _build_genre_preferences(base_game["metadata"], added_genres, removed_genres)

    scored = []
    for game in candidate_games:
        if int(game["appid"]) == int(base_game["appid"]):
            continue

        vector_score = _vector_match_score(game["vectors"], vector_preferences)
        genre_score = _genre_match_score(game["metadata"], genre_preferences)
        total_score = (vector_score * VECTOR_SCORE_WEIGHT) + (genre_score * GENRE_SCORE_WEIGHT)
        total_score = _apply_penalties(total_score, base_game["metadata"], game["metadata"])

        scored.append(
            {
                "appid": int(game["appid"]),
                "name": game["name"],
                "total_score": total_score,
                "vector_score": vector_score,
                "genre_score": genre_score,
                "vectors": game["vectors"],
                "metadata": game["metadata"],
            }
        )

    scored.sort(key=lambda item: (-item["total_score"], -item["vector_score"], item["name"].lower()))
    return scored[:limit]
