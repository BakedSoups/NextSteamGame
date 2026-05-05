#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.pg_store import PostgresGameStore, postgres_dsn_from_env
from backend.recommender import (  # noqa: E402
    default_appeal_axes,
    default_component_percentages,
    default_context_percentages,
    recommend_games,
)
from backend.retrieval import CandidateRetriever  # noqa: E402
from db_creation.paths import chroma_dir_path  # noqa: E402


ALLOWED_CONTEXTS = {
    "mechanics",
    "narrative",
    "vibe",
    "structure_loop",
    "identity",
    "setting",
    "music",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe live recommendation behavior without the frontend."
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--appid", type=int, help="Base Steam appid")
    target.add_argument("--game", help="Game name lookup via /api/search-like path")

    parser.add_argument(
        "--boost",
        action="append",
        default=[],
        help="Boost in the format context:tag=value. Example: structure_loop:roguelike progression=100",
    )
    parser.add_argument("--limit", type=int, default=20, help="Final recommendation count")
    parser.add_argument("--chroma-limit", type=int, default=300)
    parser.add_argument("--prescreen-limit", type=int, default=450)
    parser.add_argument("--merged-limit", type=int, default=300)
    parser.add_argument("--show-candidates", type=int, default=10, help="How many final results to print")
    return parser.parse_args()


def parse_boosts(raw_boosts: list[str]) -> tuple[dict[str, dict[str, float]], dict[str, float]]:
    vector_boosts: dict[str, dict[str, float]] = {}
    soundtrack_boosts: dict[str, float] = {}

    for raw in raw_boosts:
        if "=" not in raw or ":" not in raw:
            raise ValueError(f"Invalid boost format: {raw!r}. Expected context:tag=value")
        left, raw_value = raw.rsplit("=", 1)
        context, tag = left.split(":", 1)
        context = context.strip()
        tag = tag.strip()
        if context not in ALLOWED_CONTEXTS:
            raise ValueError(f"Unsupported boost context: {context!r}")
        if not tag:
            raise ValueError(f"Missing tag name in boost: {raw!r}")
        try:
            value = max(0.0, float(raw_value))
        except ValueError as exc:
            raise ValueError(f"Invalid boost value in: {raw!r}") from exc

        if context == "music":
            soundtrack_boosts[tag] = value
        else:
            vector_boosts.setdefault(context, {})[tag] = value

    return vector_boosts, soundtrack_boosts


def resolve_game(store: PostgresGameStore, *, appid: int | None, game_name: str | None) -> dict[str, Any]:
    if appid is not None:
        game = store.get_game(appid)
        if game is None:
            raise SystemExit(f"Game not found for appid={appid}")
        return game

    matches = store.search_games(game_name or "", limit=8)
    if not matches:
        raise SystemExit(f"No game search results for {game_name!r}")

    selected_appid = int(matches[0]["appid"])
    game = store.get_game(selected_appid)
    if game is None:
        raise SystemExit(f"Top search hit could not be loaded: appid={selected_appid}")
    return game


def print_base_game(game: dict[str, Any]) -> None:
    metadata = game.get("metadata") or {}
    print("Base game")
    print(f"  appid: {game['appid']}")
    print(f"  name: {game.get('name')}")
    print(f"  signature: {metadata.get('signature_tag', '')}")
    print(f"  niche anchors: {metadata.get('niche_anchors', [])}")
    print(f"  identity tags: {metadata.get('identity_tags', [])}")
    print(f"  micro tags: {metadata.get('micro_tags', [])}")
    print(f"  setting tags: {metadata.get('setting_tags', [])}")
    print(
        "  music: "
        f"{metadata.get('music_primary', '')} / {metadata.get('music_secondary', '')}"
    )


def print_result(index: int, result: dict[str, Any]) -> None:
    matched = result.get("matched_tags", {}) or {}
    breakdown = result.get("vector_context_percentages", {}) or {}
    print(f"{index}. {result.get('name')} [{result.get('appid')}]")
    print(
        "   score="
        f"{result.get('total_score', 0.0):.4f} "
        f"vector={result.get('vector_score', 0.0):.4f} "
        f"genre={result.get('genre_score', 0.0):.4f} "
        f"appeal={result.get('appeal_score', 0.0):.4f} "
        f"music={result.get('soundtrack_score', 0.0):.4f}"
    )
    print(f"   signature={result.get('metadata', {}).get('signature_tag', '')}")
    print(
        "   matched identity="
        f"{matched.get('identity', [])} "
        f"setting={matched.get('setting', [])} "
        f"music={matched.get('music', [])}"
    )
    print(
        "   matched vector="
        f"mechanics={matched.get('mechanics', [])} "
        f"narrative={matched.get('narrative', [])} "
        f"vibe={matched.get('vibe', [])} "
        f"structure_loop={matched.get('structure_loop', [])}"
    )
    print(
        "   context hit="
        f"mechanics={breakdown.get('mechanics', 0.0):.1f} "
        f"narrative={breakdown.get('narrative', 0.0):.1f} "
        f"vibe={breakdown.get('vibe', 0.0):.1f} "
        f"structure_loop={breakdown.get('structure_loop', 0.0):.1f} "
        f"identity={breakdown.get('identity', 0.0):.1f} "
        f"setting={breakdown.get('setting', 0.0):.1f}"
    )


def main() -> int:
    args = parse_args()
    dsn = postgres_dsn_from_env()
    if not dsn:
        raise SystemExit("STEAM_REC_POSTGRES_DSN must be set")

    vector_boosts, soundtrack_boosts = parse_boosts(args.boost)
    store = PostgresGameStore(dsn)
    retriever = CandidateRetriever(chroma_dir=chroma_dir_path(), store=store)

    base_game = resolve_game(store, appid=args.appid, game_name=args.game)
    context_percentages = default_context_percentages()
    component_percentages = default_component_percentages()
    appeal_axes = default_appeal_axes(base_game["metadata"])

    print_base_game(base_game)
    print()
    print("Boosts")
    print(f"  vector boosts: {vector_boosts}")
    print(f"  soundtrack boosts: {soundtrack_boosts}")
    print()

    started = time.perf_counter()
    candidate_games = retriever.retrieve_candidates(
        base_game,
        chroma_limit=args.chroma_limit,
        prescreen_limit=args.prescreen_limit,
        merged_limit=args.merged_limit,
        context_percentages=context_percentages,
        tag_boosts=vector_boosts,
        soundtrack_boosts=soundtrack_boosts,
    )
    retrieval_elapsed = time.perf_counter() - started

    started = time.perf_counter()
    recommendations = recommend_games(
        base_game,
        candidate_games,
        extra_vector_boosts=vector_boosts,
        extra_soundtrack_boosts=soundtrack_boosts,
        context_percentages=context_percentages,
        component_percentages=component_percentages,
        appeal_axes=appeal_axes,
        added_genres={"primary": [], "sub": [], "sub_sub": []},
        removed_genres={"primary": [], "sub": [], "sub_sub": []},
        limit=args.limit,
    )
    rerank_elapsed = time.perf_counter() - started

    print("Timings")
    print(f"  retrieval: {retrieval_elapsed:.3f}s")
    print(f"  rerank: {rerank_elapsed:.3f}s")
    print()
    print("Candidate summary")
    print(f"  hydrated candidates: {len(candidate_games)}")
    print(f"  final recommendations: {len(recommendations)}")
    print()

    for index, result in enumerate(recommendations[: args.show_candidates], start=1):
        print_result(index, result)
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
