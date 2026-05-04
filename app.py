#!/usr/bin/env python3

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.pg_store import PostgresGameStore, postgres_dsn_from_env
from backend.recommender import (
    APPEAL_AXIS_ORDER,
    COMPONENT_ORDER,
    CONTENT_CONTEXT_ORDER,
    default_appeal_axes,
    default_component_percentages,
    default_context_percentages,
    recommend_games,
)
from backend.retrieval import CandidateRetriever
from db_creation.paths import chroma_dir_path


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8000


def load_project_env() -> None:
    env_path = ROOT / ".env"
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
        os.environ[key] = value.strip().strip("\"'")


load_project_env()

postgres_dsn = postgres_dsn_from_env()
if not postgres_dsn:
    raise RuntimeError("STEAM_REC_POSTGRES_DSN must be set. SQLite fallback has been removed.")

store = PostgresGameStore(postgres_dsn)
retriever = CandidateRetriever(
    chroma_dir=chroma_dir_path(),
    fallback_games=store.load_all_games(),
)

app = FastAPI(title="Steam Recommendation API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _vector_tag_names(raw: Any) -> list[str]:
    if isinstance(raw, dict):
        return [str(tag) for tag in raw.keys()]
    if isinstance(raw, list):
        return [str(tag) for tag in raw]
    if isinstance(raw, str):
        return [raw]
    return []


def _vector_weight_map(raw: Any) -> dict[str, int]:
    if isinstance(raw, dict):
        cleaned: dict[str, int] = {}
        for tag, weight in raw.items():
            try:
                numeric_weight = int(weight)
            except (TypeError, ValueError):
                numeric_weight = 0
            cleaned[str(tag).replace(" ", "_").replace("-", "_").lower()] = numeric_weight
        return cleaned
    if isinstance(raw, list):
        normalized_tags = [str(tag).replace(" ", "_").replace("-", "_").lower() for tag in raw if str(tag).strip()]
        if not normalized_tags:
            return {}
        base = 100 // len(normalized_tags)
        spill = 100 - (base * len(normalized_tags))
        return {
            tag: base + (1 if index < spill else 0)
            for index, tag in enumerate(normalized_tags)
        }
    if isinstance(raw, str) and raw.strip():
        normalized = raw.replace(" ", "_").replace("-", "_").lower()
        return {normalized: 100}
    return {}


def _genre_branch_values(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(tag) for tag in raw if str(tag).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _single_genre_value(raw: Any) -> str:
    values = _genre_branch_values(raw)
    return values[0] if values else ""


def _music_tags(metadata: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for field in ("music_primary", "music_secondary"):
        value = str(metadata.get(field, "")).strip()
        if value and value not in tags:
            tags.append(value)
    return tags


def _identity_tags(metadata: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    signature_tag = str(metadata.get("signature_tag", "")).strip()
    if signature_tag:
        tags.append(signature_tag)
    for field in ("niche_anchors", "identity_tags", "micro_tags"):
        for tag in metadata.get(field, []) or []:
            text = str(tag).strip()
            if text and text not in tags:
                tags.append(text)
    return tags


def _setting_tags(metadata: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for tag in metadata.get("setting_tags", []) or []:
        text = str(tag).strip()
        if text and text not in tags:
            tags.append(text)
    return tags


def _serialize_genre_tree(metadata: dict[str, Any]) -> dict[str, str]:
    genre_tree = metadata.get("genre_tree", {}) or {}
    return {
        "primary": _single_genre_value(genre_tree.get("primary")),
        "sub": _single_genre_value(genre_tree.get("sub")),
        "sub_sub": _single_genre_value(genre_tree.get("sub_sub")),
    }


def _serialize_focus_vectors(game: dict) -> dict[str, dict[str, int]]:
    vectors = game.get("vectors", {}) or {}
    return {
        context: dict(vectors.get(context) or {})
        for context in ("mechanics", "narrative", "vibe", "structure_loop")
    }


def _serialize_identity(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "signatureTag": str(metadata.get("signature_tag", "")).strip(),
        "nicheAnchors": [str(tag).strip() for tag in metadata.get("niche_anchors", []) or [] if str(tag).strip()],
        "identityTags": [str(tag).strip() for tag in metadata.get("identity_tags", []) or [] if str(tag).strip()],
        "microTags": [str(tag).strip() for tag in metadata.get("micro_tags", []) or [] if str(tag).strip()],
        "settingTags": _setting_tags(metadata),
        "musicPrimary": str(metadata.get("music_primary", "")).strip(),
        "musicSecondary": str(metadata.get("music_secondary", "")).strip(),
    }


def _build_tag_weights(game: dict) -> dict[str, dict[str, int]]:
    tags: dict[str, dict[str, int]] = {}
    for context, tag_weights in (game.get("vectors") or {}).items():
        tags[context] = _vector_weight_map(tag_weights)

    tags["identity"] = _vector_weight_map(_identity_tags(game["metadata"]))
    tags["setting"] = _vector_weight_map(_setting_tags(game["metadata"]))
    tags["music"] = _vector_weight_map(_music_tags(game["metadata"]))
    return tags


def _serialize_game(game: dict) -> dict[str, Any]:
    metadata = game.get("metadata", {})
    genre_tree = _serialize_genre_tree(metadata)
    focus_vectors = _serialize_focus_vectors(game)
    identity = _serialize_identity(metadata)
    vector_tags = {
        context: _vector_tag_names(focus_vectors.get(context))
        for context in ("mechanics", "narrative", "vibe", "structure_loop")
    }
    vector_tags["identity"] = _identity_tags(metadata)
    vector_tags["setting"] = _setting_tags(metadata)
    vector_tags["music"] = _music_tags(metadata)
    assets = {
        "header": str(game.get("header_image", "")),
        "capsule": str(game.get("capsule_image", "")),
        "capsuleV5": str(game.get("capsule_imagev5", "")),
        "background": str(game.get("background_image", "")),
        "backgroundRaw": str(game.get("background_image_raw", "")),
        "logo": str(game.get("logo_image", "")),
        "libraryHero": str(game.get("library_hero_image", "")),
        "libraryCapsule": str(game.get("library_capsule_image", "")),
    }
    return {
        "id": int(game["appid"]),
        "appId": str(game["appid"]),
        "title": str(game.get("name", "")),
        "description": str(game.get("short_description", "")),
        "releaseDate": str(game.get("release_date_text", "")),
        "category": str(metadata.get("signature_tag", "")),
        "image": str(game.get("capsule_image", "")),
        "headerImage": str(game.get("header_image", "")),
        "assets": assets,
        "genreTree": genre_tree,
        "focusVectors": focus_vectors,
        "identity": identity,
        "genres": {
            "primary": _genre_branch_values(genre_tree["primary"]),
            "sub": _genre_branch_values(genre_tree["sub"]),
            "sub_sub": _genre_branch_values(genre_tree["sub_sub"]),
            "traits": [],
        },
        "tags": vector_tags,
        "weights": {
            "appeal": default_appeal_axes(metadata),
            "context": default_context_percentages(),
            "match": default_component_percentages(),
            "tags": _build_tag_weights(game),
        },
        "metadata": metadata,
    }


def _serialize_recommendation(item: dict) -> dict[str, Any]:
    metadata = item.get("metadata", {})
    signals = item.get("signals", {}) or {}
    genre_tree = _serialize_genre_tree(metadata)
    focus_vectors = _serialize_focus_vectors(item)
    identity = _serialize_identity(metadata)
    assets = {
        "header": str(item.get("header_image", "")),
        "capsule": str(item.get("capsule_image", "")),
        "capsuleV5": str(item.get("capsule_imagev5", "")),
        "background": str(item.get("background_image", "")),
        "backgroundRaw": str(item.get("background_image_raw", "")),
        "logo": str(item.get("logo_image", "")),
        "libraryHero": str(item.get("library_hero_image", "")),
        "libraryCapsule": str(item.get("library_capsule_image", "")),
    }
    return {
        "id": int(item["appid"]),
        "appId": str(item["appid"]),
        "title": str(item.get("name", "")),
        "description": str(item.get("short_description", "")),
        "releaseDate": "",
        "category": str(item.get("signature_tag", "")),
        "image": str(item.get("capsule_image", "")),
        "headerImage": str(item.get("header_image", "")),
        "assets": assets,
        "genreTree": genre_tree,
        "focusVectors": focus_vectors,
        "identity": identity,
        "genres": {
            "primary": _genre_branch_values(genre_tree["primary"]),
            "sub": _genre_branch_values(genre_tree["sub"]),
            "sub_sub": _genre_branch_values(genre_tree["sub_sub"]),
            "traits": [],
        },
        "tags": {
            "mechanics": _vector_tag_names(focus_vectors.get("mechanics")),
            "narrative": _vector_tag_names(focus_vectors.get("narrative")),
            "vibe": _vector_tag_names(focus_vectors.get("vibe")),
            "structure_loop": _vector_tag_names(focus_vectors.get("structure_loop")),
            "identity": _identity_tags(metadata),
            "setting": _setting_tags(metadata),
            "music": _music_tags(metadata),
        },
        "matchedTags": {
            "mechanics": [str(tag) for tag in (item.get("matched_tags", {}) or {}).get("mechanics", [])],
            "narrative": [str(tag) for tag in (item.get("matched_tags", {}) or {}).get("narrative", [])],
            "vibe": [str(tag) for tag in (item.get("matched_tags", {}) or {}).get("vibe", [])],
            "structure_loop": [str(tag) for tag in (item.get("matched_tags", {}) or {}).get("structure_loop", [])],
            "identity": [str(tag) for tag in (item.get("matched_tags", {}) or {}).get("identity", [])],
            "setting": [str(tag) for tag in (item.get("matched_tags", {}) or {}).get("setting", [])],
            "music": [str(tag) for tag in (item.get("matched_tags", {}) or {}).get("music", [])],
        },
        "matchScore": float(item.get("total_score", 0.0)),
        "confidence": float(item.get("confidence_multiplier", 1.0)),
        "scores": {
            "total": float(item.get("total_score", 0.0)),
            "vector": float(item.get("weighted_components", {}).get("vector", 0.0)),
            "genre": float(item.get("weighted_components", {}).get("genre", 0.0)),
            "appeal": float(item.get("weighted_components", {}).get("appeal", 0.0)),
            "music": float(item.get("weighted_components", {}).get("music", 0.0)),
        },
        "scorePercentages": dict(item.get("weighted_component_percentages", {})),
        "contextScores": {
            "mechanics": float(item.get("vector_context_percentages", {}).get("mechanics", 0.0)),
            "narrative": float(item.get("vector_context_percentages", {}).get("narrative", 0.0)),
            "vibe": float(item.get("vector_context_percentages", {}).get("vibe", 0.0)),
            "structure_loop": float(item.get("vector_context_percentages", {}).get("structure_loop", 0.0)),
            "identity": float(item.get("vector_context_percentages", {}).get("identity", 0.0)),
            "setting": float(item.get("vector_context_percentages", {}).get("setting", 0.0)),
            "music": float(item.get("active_context_percentages", {}).get("music", 0.0)),
        },
        "reviewStats": {
            "positive": int(signals.get("positive") or 0),
            "negative": int(signals.get("negative") or 0),
            "reviewCount": int(
                signals.get("estimated_review_count")
                or signals.get("recommendations_total")
                or (int(signals.get("positive") or 0) + int(signals.get("negative") or 0))
                or 0
            ),
        },
    }


def _normalize_tag_weight_map(payload: dict[str, Any] | None) -> tuple[dict[str, dict[str, float]], dict[str, float]]:
    payload = payload or {}
    vector_weights: dict[str, dict[str, float]] = {}
    soundtrack_weights: dict[str, float] = {}
    for context, entries in payload.items():
        if not isinstance(entries, dict):
            continue
        cleaned = {
            str(tag).replace("_", " "): max(0.0, float(value))
            for tag, value in entries.items()
        }
        if context == "music":
            soundtrack_weights = cleaned
        else:
            vector_weights[context] = cleaned
    return vector_weights, soundtrack_weights


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config/defaults")
def defaults() -> dict[str, Any]:
    return {
        "componentOrder": COMPONENT_ORDER,
        "contentContextOrder": CONTENT_CONTEXT_ORDER,
        "appealAxisOrder": APPEAL_AXIS_ORDER,
        "defaultMatchWeights": default_component_percentages(),
        "defaultContextWeights": default_context_percentages(),
    }


@app.get("/api/search")
def search_games(q: str = Query("", alias="q"), limit: int = Query(8, ge=1, le=25)) -> dict[str, Any]:
    results = store.search_games(q, limit=limit)
    serialized_results: list[dict[str, Any]] = []
    for item in results:
        game = store.get_game(item["appid"])
        if game is None:
            continue
        serialized_results.append(_serialize_game(game))
    return {"query": q, "results": serialized_results}


@app.get("/api/games/{appid}")
def get_game(appid: int) -> dict[str, Any]:
    game = store.get_game(appid)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return _serialize_game(game)


@app.post("/api/recommendations")
def get_recommendations(payload: dict[str, Any]) -> JSONResponse:
    appid = payload.get("appid")
    if appid is None:
        raise HTTPException(status_code=400, detail="Missing appid")

    game = store.get_game(int(appid))
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    component_percentages = payload.get("weights", {}).get("match") or default_component_percentages()
    context_percentages = payload.get("weights", {}).get("context") or default_context_percentages()
    appeal_axes = payload.get("weights", {}).get("appeal") or default_appeal_axes(game["metadata"])
    tag_weights, soundtrack_weights = _normalize_tag_weight_map((payload.get("weights") or {}).get("tags"))
    genres = (payload.get("weights") or {}).get("genres") or game["metadata"].get("genre_tree", {})

    base_tree = game["metadata"].get("genre_tree", {})
    added_genres = {
        branch: sorted(set(_genre_branch_values(genres.get(branch))) - set(_genre_branch_values(base_tree.get(branch))))
        for branch in ("primary", "sub", "sub_sub")
    }
    removed_genres = {
        branch: sorted(set(_genre_branch_values(base_tree.get(branch))) - set(_genre_branch_values(genres.get(branch))))
        for branch in ("primary", "sub", "sub_sub")
    }

    candidate_games = retriever.retrieve_candidates(game, limit=400)
    recommendations = recommend_games(
        game,
        candidate_games,
        extra_vector_boosts=tag_weights,
        extra_soundtrack_boosts=soundtrack_weights,
        context_percentages=context_percentages,
        component_percentages=component_percentages,
        appeal_axes=appeal_axes,
        added_genres=added_genres,
        removed_genres=removed_genres,
        limit=int(payload.get("limit", 20)),
    )

    return JSONResponse(
        {
            "baseGame": _serialize_game(game),
            "results": [_serialize_recommendation(item) for item in recommendations],
        }
    )


def main() -> int:
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
