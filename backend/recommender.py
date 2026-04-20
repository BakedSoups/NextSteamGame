from __future__ import annotations

from math import log10
from typing import Iterable


VECTOR_CONTEXT_MULTIPLIERS = {
    "mechanics": 1.35,
    "narrative": 0.20,
    "vibe": 0.35,
    "structure_loop": 1.20,
    "uniqueness": 0.55,
}
SOUNDTRACK_CONTEXT_MULTIPLIER = 0.41

VECTOR_CONTEXT_ORDER = tuple(VECTOR_CONTEXT_MULTIPLIERS.keys())
CONTENT_CONTEXT_ORDER = VECTOR_CONTEXT_ORDER + ("music",)
APPEAL_AXIS_ORDER = (
    "challenge",
    "complexity",
    "pace",
    "narrative_focus",
    "social_energy",
    "creativity",
)

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
    "sub_sub": 0.95,
    "traits": 1.0,
}

VECTOR_SCORE_WEIGHT = 0.55
GENRE_SCORE_WEIGHT = 0.30
APPEAL_SCORE_WEIGHT = 0.15
SOUNDTRACK_SCORE_WEIGHT = 0.10
COMPONENT_ORDER = ("vector", "genre", "appeal", "music")


def default_component_percentages() -> dict[str, int]:
    raw = {
        "vector": VECTOR_SCORE_WEIGHT * 100.0,
        "genre": GENRE_SCORE_WEIGHT * 100.0,
        "appeal": APPEAL_SCORE_WEIGHT * 100.0,
        "music": SOUNDTRACK_SCORE_WEIGHT * 100.0,
    }
    rounded = {component: int(round(value)) for component, value in raw.items()}
    delta = 100 - sum(rounded.values())
    if delta != 0:
        ranked = sorted(raw, key=lambda component: raw[component] - rounded[component], reverse=(delta > 0))
        for component in ranked[: abs(delta)]:
            rounded[component] += 1 if delta > 0 else -1
    return rounded


def component_percentages_to_weights(percentages: dict[str, float | int] | None) -> dict[str, float]:
    if not percentages:
        return {
            "vector": VECTOR_SCORE_WEIGHT,
            "genre": GENRE_SCORE_WEIGHT,
            "appeal": APPEAL_SCORE_WEIGHT,
            "music": SOUNDTRACK_SCORE_WEIGHT,
        }
    total = sum(float(value) for value in percentages.values())
    if total <= 0:
        return component_percentages_to_weights(None)
    return {
        component: float(percentages.get(component, 0.0)) / total
        for component in COMPONENT_ORDER
    }


def default_context_percentages() -> dict[str, int]:
    raw_weights = {
        **VECTOR_CONTEXT_MULTIPLIERS,
        "music": SOUNDTRACK_CONTEXT_MULTIPLIER,
    }
    total = sum(raw_weights.values()) or 1.0
    raw = {
        context: (weight / total) * 100.0
        for context, weight in raw_weights.items()
    }
    rounded = {context: int(round(value)) for context, value in raw.items()}
    delta = 100 - sum(rounded.values())
    if delta != 0:
        ranked = sorted(raw, key=lambda context: raw[context] - rounded[context], reverse=(delta > 0))
        for context in ranked[: abs(delta)]:
            rounded[context] += 1 if delta > 0 else -1
    return rounded


def context_percentages_to_multipliers(percentages: dict[str, float | int]) -> dict[str, float]:
    if not percentages:
        return {
            **VECTOR_CONTEXT_MULTIPLIERS,
            "music": SOUNDTRACK_CONTEXT_MULTIPLIER,
        }
    total = sum(float(value) for value in percentages.values())
    if total <= 0:
        return {
            **VECTOR_CONTEXT_MULTIPLIERS,
            "music": SOUNDTRACK_CONTEXT_MULTIPLIER,
        }
    context_count = max(len(CONTENT_CONTEXT_ORDER), 1)
    return {
        context: (float(percentages.get(context, 0.0)) / total) * context_count
        for context in CONTENT_CONTEXT_ORDER
    }


def default_appeal_axes(metadata: dict) -> dict[str, int]:
    stored = dict(metadata.get("appeal_axes") or {})
    return {
        axis: max(0, min(100, int(stored.get(axis, 50))))
        for axis in APPEAL_AXIS_ORDER
    }


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
    context_multipliers: dict[str, float] | None = None,
) -> dict[str, dict[str, float]]:
    boosts = extra_boosts or {}
    multipliers = context_multipliers or VECTOR_CONTEXT_MULTIPLIERS
    preferences: dict[str, dict[str, float]] = {}
    for context, tag_weights in vectors.items():
        override_weights = boosts.get(context, {})
        normalized = _normalize_weights(override_weights or tag_weights)
        context_multiplier = multipliers.get(context, 1.0)
        adjusted: dict[str, float] = {}
        for tag, weight in normalized.items():
            adjusted_weight = weight * context_multiplier
            adjusted_weight *= DEFAULT_VECTOR_BOOSTS.get(context, {}).get(tag, 1.0)
            adjusted[tag] = adjusted_weight
        preferences[context] = adjusted
    return preferences


def _build_genre_preferences(
    metadata: dict,
    added_genres: dict[str, list[str]] | None = None,
    removed_genres: dict[str, list[str]] | None = None,
) -> dict[str, dict[str, float]]:
    genre_tree = metadata.get("genre_tree", {})
    added = added_genres or {"primary": [], "sub": [], "sub_sub": [], "traits": []}
    removed = removed_genres or {"primary": [], "sub": [], "sub_sub": [], "traits": []}
    preferences: dict[str, dict[str, float]] = {}
    for branch in ("primary", "sub", "sub_sub", "traits"):
        branch_tags = set(genre_tree.get(branch, []))
        branch_tags.update(added.get(branch, []))
        branch_tags.difference_update(removed.get(branch, []))
        preferences[branch] = {
            tag: GENRE_BRANCH_WEIGHTS[branch]
            for tag in sorted(branch_tags)
        }
    return preferences


def _build_soundtrack_preferences(
    metadata: dict,
    extra_boosts: dict[str, float] | None = None,
    soundtrack_multiplier: float = 1.0,
) -> dict[str, float]:
    boosts = extra_boosts or {}
    tags = metadata.get("soundtrack_tags", [])
    if not tags:
        return {}

    normalized = _normalize_weights(boosts or {tag: 1 for tag in tags})
    preferences: dict[str, float] = {}
    for tag, weight in normalized.items():
        preferences[tag] = weight * soundtrack_multiplier
    return preferences


def _appeal_match_score(candidate_metadata: dict, target_axes: dict[str, int]) -> float:
    if not target_axes:
        return 0.0
    candidate_axes = default_appeal_axes(candidate_metadata)
    total = 0.0
    for axis, target in target_axes.items():
        candidate = candidate_axes.get(axis, 50)
        total += max(0.0, 1.0 - (abs(candidate - target) / 100.0))
    return total / max(len(target_axes), 1)


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


def _vector_context_breakdown(
    candidate_vectors: dict[str, dict[str, int]],
    preferences: dict[str, dict[str, float]],
) -> dict[str, float]:
    breakdown: dict[str, float] = {}
    for context, preferred_weights in preferences.items():
        if not preferred_weights:
            continue
        candidate_weights = _normalize_weights(candidate_vectors.get(context, {}))
        overlap = 0.0
        for tag, preferred_weight in preferred_weights.items():
            overlap += min(preferred_weight, candidate_weights.get(tag, 0.0))
        breakdown[context] = overlap
    return breakdown


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


def _soundtrack_match_score(candidate_metadata: dict, preferences: dict[str, float]) -> float:
    if not preferences:
        return 0.0
    candidate_tags = set(candidate_metadata.get("soundtrack_tags", []))
    total_weight = sum(preferences.values()) or 1.0
    matched_weight = sum(weight for tag, weight in preferences.items() if tag in candidate_tags)
    return matched_weight / total_weight


def _apply_penalties(total_score: float, base_metadata: dict, candidate_metadata: dict) -> float:
    base_tree = base_metadata.get("genre_tree", {})
    genre_tree = candidate_metadata.get("genre_tree", {})
    base_primary = set(base_tree.get("primary", []))
    base_sub = set(base_tree.get("sub", []))
    base_sub_sub = set(base_tree.get("sub_sub", []))
    base_traits = set(base_tree.get("traits", []))
    primary_tags = set(genre_tree.get("primary", []))
    sub_tags = set(genre_tree.get("sub", []))
    sub_sub_tags = set(genre_tree.get("sub_sub", []))
    trait_tags = set(genre_tree.get("traits", []))

    primary_overlap = len(base_primary & primary_tags)
    sub_overlap = len(base_sub & sub_tags)
    sub_sub_overlap = len(base_sub_sub & sub_sub_tags)
    trait_overlap = len(base_traits & trait_tags)

    if base_primary and primary_overlap == 0:
        total_score *= 0.82
    if base_sub and sub_overlap == 0:
        total_score *= 0.88
    if base_sub_sub and sub_sub_overlap == 0:
        total_score *= 0.91
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
    base_anchor_sub_sub = set(_top_branch_tags(base_metadata, "sub_sub", 3))
    base_anchor_traits = set(_top_branch_tags(base_metadata, "traits", 4))

    if base_anchor_primary and (base_anchor_primary & primary_tags):
        total_score *= 1.08
    if base_anchor_sub and (base_anchor_sub & sub_tags):
        total_score *= 1.12
    if base_anchor_sub_sub and (base_anchor_sub_sub & sub_sub_tags):
        total_score *= 1.08
    if base_anchor_traits and (base_anchor_traits & trait_tags):
        total_score *= 1.05

    return total_score


def _metadata_confidence_multiplier(game: dict) -> float:
    signals = game.get("signals") or {}
    review_count = int(
        signals.get("estimated_review_count")
        or signals.get("recommendations_total")
        or 0
    )
    owners = int(signals.get("steamspy_owner_estimate") or 0)
    ccu = int(signals.get("steamspy_ccu") or 0)
    positive = int(signals.get("positive") or 0)
    negative = int(signals.get("negative") or 0)
    metacritic = signals.get("metacritic_score")

    review_confidence = min(log10(review_count + 1) / 4.0, 1.0) if review_count > 0 else 0.0
    owner_confidence = min(log10(owners + 1) / 7.0, 1.0) if owners > 0 else 0.0
    ccu_confidence = min(log10(ccu + 1) / 5.0, 1.0) if ccu > 0 else 0.0

    multiplier = 0.70
    multiplier += review_confidence * 0.20
    multiplier += owner_confidence * 0.10
    multiplier += ccu_confidence * 0.05

    total_reviews = positive + negative
    if total_reviews >= 20:
        positive_ratio = positive / total_reviews
        multiplier *= 0.85 + (positive_ratio * 0.30)
    else:
        multiplier *= 0.75 + (review_confidence * 0.25)

    if isinstance(metacritic, int) and metacritic > 0:
        multiplier *= 0.95 + (min(metacritic, 100) / 100.0 * 0.15)

    return max(0.55, min(1.20, multiplier))


def _percent_breakdown(values: dict[str, float]) -> dict[str, float]:
    total = sum(max(float(value), 0.0) for value in values.values())
    if total <= 0:
        return {key: 0.0 for key in values}
    return {
        key: (max(float(value), 0.0) / total) * 100.0
        for key, value in values.items()
    }


def recommend_games(
    base_game: dict,
    candidate_games: Iterable[dict],
    *,
    extra_vector_boosts: dict[str, dict[str, float]] | None = None,
    extra_soundtrack_boosts: dict[str, float] | None = None,
    context_percentages: dict[str, float | int] | None = None,
    component_percentages: dict[str, float | int] | None = None,
    appeal_axes: dict[str, int] | None = None,
    added_genres: dict[str, list[str]] | None = None,
    removed_genres: dict[str, list[str]] | None = None,
    limit: int = 15,
) -> list[dict]:
    context_multipliers = context_percentages_to_multipliers(context_percentages or default_context_percentages())
    component_weights = component_percentages_to_weights(component_percentages or default_component_percentages())
    vector_preferences = _build_vector_preferences(
        base_game["vectors"],
        extra_vector_boosts,
        context_multipliers=context_multipliers,
    )
    genre_preferences = _build_genre_preferences(base_game["metadata"], added_genres, removed_genres)
    soundtrack_preferences = _build_soundtrack_preferences(
        base_game["metadata"],
        extra_soundtrack_boosts,
        soundtrack_multiplier=context_multipliers.get("music", 1.0),
    )
    target_appeal_axes = appeal_axes or default_appeal_axes(base_game["metadata"])

    scored = []
    for game in candidate_games:
        if int(game["appid"]) == int(base_game["appid"]):
            continue

        vector_score = _vector_match_score(game["vectors"], vector_preferences)
        vector_breakdown = _vector_context_breakdown(game["vectors"], vector_preferences)
        genre_score = _genre_match_score(game["metadata"], genre_preferences)
        appeal_score = _appeal_match_score(game["metadata"], target_appeal_axes)
        soundtrack_score = _soundtrack_match_score(game["metadata"], soundtrack_preferences)
        weighted_components = {
            "vector": vector_score * component_weights["vector"],
            "genre": genre_score * component_weights["genre"],
            "appeal": appeal_score * component_weights["appeal"],
            "music": soundtrack_score * component_weights["music"],
        }
        component_percentages = _percent_breakdown(weighted_components)
        vector_component_weights = {
            context: value * context_multipliers.get(context, 1.0)
            for context, value in vector_breakdown.items()
        }
        vector_component_percentages = _percent_breakdown(vector_component_weights)
        total_score = (
            weighted_components["vector"]
            + weighted_components["genre"]
            + weighted_components["appeal"]
            + weighted_components["music"]
        )
        total_score = _apply_penalties(total_score, base_game["metadata"], game["metadata"])
        confidence_multiplier = _metadata_confidence_multiplier(game)
        total_score *= confidence_multiplier

        scored.append(
            {
                "appid": int(game["appid"]),
                "name": game["name"],
                "total_score": total_score,
                "vector_score": vector_score,
                "genre_score": genre_score,
                "appeal_score": appeal_score,
                "soundtrack_score": soundtrack_score,
                "vector_context_breakdown": vector_breakdown,
                "weighted_component_percentages": component_percentages,
                "vector_context_percentages": vector_component_percentages,
                "weighted_components": weighted_components,
                "confidence_multiplier": confidence_multiplier,
                "active_context_percentages": {
                    context: int(round(float((context_percentages or default_context_percentages()).get(context, 0))))
                    for context in CONTENT_CONTEXT_ORDER
                },
                "active_component_percentages": {
                    component: int(round(float((component_percentages or default_component_percentages()).get(component, 0))))
                    for component in COMPONENT_ORDER
                },
                "vectors": game["vectors"],
                "metadata": game["metadata"],
                "header_image": game.get("header_image", ""),
                "capsule_image": game.get("capsule_image", ""),
                "short_description": game.get("short_description", ""),
                "signature_tag": game.get("signature_tag", ""),
                "signals": game.get("signals", {}),
            }
        )

    scored.sort(key=lambda item: (-item["total_score"], -item["vector_score"], item["name"].lower()))
    return scored[:limit]
