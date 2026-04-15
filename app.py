#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.db import FinalGameStore
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
from db_creation.paths import chroma_dir_path, final_canon_db_path, metadata_db_path


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8000

store = FinalGameStore(final_canon_db_path(), metadata_db_path())
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


def _build_tag_weights(game: dict) -> dict[str, dict[str, int]]:
    tags: dict[str, dict[str, int]] = {}
    for context, tag_weights in (game.get("vectors") or {}).items():
        tags[context] = _vector_weight_map(tag_weights)

    soundtrack_tags = game["metadata"].get("soundtrack_tags", [])
    if soundtrack_tags:
        base = 100 // len(soundtrack_tags)
        spill = 100 - (base * len(soundtrack_tags))
        music_weights: dict[str, int] = {}
        for index, tag in enumerate(soundtrack_tags):
            normalized = str(tag).replace(" ", "_").replace("-", "_").lower()
            music_weights[normalized] = base + (1 if index < spill else 0)
        tags["music"] = music_weights
    else:
        tags["music"] = {}
    return tags


def _serialize_game(game: dict) -> dict[str, Any]:
    metadata = game.get("metadata", {})
    genre_tree = metadata.get("genre_tree", {})
    vector_tags = {
        context: _vector_tag_names((game.get("vectors", {}) or {}).get(context))
        for context in ("mechanics", "narrative", "vibe", "structure_loop", "uniqueness")
    }
    vector_tags["music"] = list(metadata.get("soundtrack_tags", []) or [])
    assets = {
        "header": str(game.get("header_image", "")),
        "capsule": str(game.get("capsule_image", "")),
        "capsuleV5": str(game.get("capsule_imagev5", "")),
        "background": str(game.get("background_image", "")),
        "backgroundRaw": str(game.get("background_image_raw", "")),
        "logo": str(game.get("logo_image", "")),
        "icon": str(game.get("icon_image", "")),
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
        "genres": {
            "primary": list(genre_tree.get("primary", []) or []),
            "sub": list(genre_tree.get("sub", []) or []),
            "sub_sub": list(genre_tree.get("sub_sub", []) or []),
            "traits": list(genre_tree.get("traits", []) or []),
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
    genre_tree = metadata.get("genre_tree", {})
    assets = {
        "header": str(item.get("header_image", "")),
        "capsule": str(item.get("capsule_image", "")),
        "capsuleV5": str(item.get("capsule_imagev5", "")),
        "background": str(item.get("background_image", "")),
        "backgroundRaw": str(item.get("background_image_raw", "")),
        "logo": str(item.get("logo_image", "")),
        "icon": str(item.get("icon_image", "")),
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
        "genres": {
            "primary": list(genre_tree.get("primary", []) or []),
            "sub": list(genre_tree.get("sub", []) or []),
            "sub_sub": list(genre_tree.get("sub_sub", []) or []),
            "traits": list(genre_tree.get("traits", []) or []),
        },
        "tags": {
            "mechanics": _vector_tag_names((item.get("vectors", {}) or {}).get("mechanics")),
            "narrative": _vector_tag_names((item.get("vectors", {}) or {}).get("narrative")),
            "vibe": _vector_tag_names((item.get("vectors", {}) or {}).get("vibe")),
            "structure_loop": _vector_tag_names((item.get("vectors", {}) or {}).get("structure_loop")),
            "uniqueness": _vector_tag_names((item.get("vectors", {}) or {}).get("uniqueness")),
            "music": list(metadata.get("soundtrack_tags", []) or []),
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
            "uniqueness": float(item.get("vector_context_percentages", {}).get("uniqueness", 0.0)),
            "music": float(item.get("active_context_percentages", {}).get("music", 0.0)),
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
    return {"query": q, "results": [_serialize_game(store.get_game(item["appid"]) or item) for item in results if store.get_game(item["appid"]) is not None]}


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
    added_genres = {branch: sorted(set(genres.get(branch, [])) - set(base_tree.get(branch, []))) for branch in ("primary", "sub", "sub_sub", "traits")}
    removed_genres = {branch: sorted(set(base_tree.get(branch, [])) - set(genres.get(branch, []))) for branch in ("primary", "sub", "sub_sub", "traits")}

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
