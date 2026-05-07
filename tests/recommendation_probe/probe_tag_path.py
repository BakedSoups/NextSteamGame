#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.pg_store import PostgresGameStore, postgres_dsn_from_env  # noqa: E402
from backend.recommender import (  # noqa: E402
    default_appeal_axes,
    default_component_percentages,
    default_context_percentages,
    recommend_games,
)
from backend.retrieval import CandidateRetriever  # noqa: E402
from db_creation.paths import chroma_dir_path, final_canon_db_path  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect how a specific niche tag from a base game landed in canon groups and recommendations."
    )
    parser.add_argument("--game", required=True, help="Base game search text")
    parser.add_argument(
        "--needle",
        required=True,
        help="Substring to look for in the base game's niche/identity/micro/vector tags. Example: automation",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=12,
        help="Final recommendation count when simulating the UI-style boost",
    )
    return parser.parse_args()


def resolve_game(store: PostgresGameStore, game_name: str) -> dict[str, Any]:
    matches = store.search_games(game_name, limit=8)
    if not matches:
        raise SystemExit(f"No game search results for {game_name!r}")
    appid = int(matches[0]["appid"])
    game = store.get_game(appid)
    if game is None:
        raise SystemExit(f"Top search hit could not be loaded: appid={appid}")
    return game


def find_base_tag_hits(game: dict[str, Any], needle: str) -> list[dict[str, str]]:
    lowered = needle.lower()
    hits: list[dict[str, str]] = []
    metadata = game.get("metadata") or {}
    vectors = game.get("vectors") or {}

    def add_hit(lane: str, source: str, value: str) -> None:
        if lowered in value.lower():
            hits.append({"lane": lane, "source": source, "tag": value})

    for field in ("signature_tag", "music_primary", "music_secondary"):
        raw = str(metadata.get(field, "")).strip()
        if raw:
            lane = "music" if field.startswith("music_") else "identity"
            add_hit(lane, field, raw)

    for field in ("niche_anchors", "identity_tags", "micro_tags", "setting_tags"):
        lane = "setting" if field == "setting_tags" else "identity"
        for raw in metadata.get(field, []) or []:
            text = str(raw).strip()
            if text:
                add_hit(lane, field, text)

    for context, weighted_tags in vectors.items():
        if not isinstance(weighted_tags, dict):
            continue
        for tag in weighted_tags:
            text = str(tag).strip()
            if text:
                add_hit(context, context, text)

    return hits


def inspect_sqlite_groups(needle: str, exact_tags: list[str]) -> list[dict[str, Any]]:
    connection = sqlite3.connect(final_canon_db_path())
    connection.row_factory = sqlite3.Row
    lowered = needle.lower()
    try:
        rows = connection.execute(
            """
            SELECT
                g.context,
                g.representative_tag,
                g.parent_tag,
                g.specificity_level,
                g.member_count,
                g.total_occurrences,
                m.member_tag
            FROM canonical_tag_groups g
            LEFT JOIN canonical_tag_members m ON m.group_id = g.id
            WHERE
                lower(g.representative_tag) LIKE ?
                OR lower(g.parent_tag) LIKE ?
                OR lower(COALESCE(m.member_tag, '')) LIKE ?
            ORDER BY g.context, g.representative_tag, m.member_tag
            """,
            (f"%{lowered}%", f"%{lowered}%", f"%{lowered}%"),
        ).fetchall()

        exact = {tag.lower() for tag in exact_tags}
        grouped: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str, str]] = set()
        for row in rows:
            member_tag = str(row["member_tag"] or "")
            key = (str(row["context"]), str(row["representative_tag"]), member_tag)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            grouped.append(
                {
                    "context": str(row["context"]),
                    "representative_tag": str(row["representative_tag"]),
                    "parent_tag": str(row["parent_tag"]),
                    "specificity_level": int(row["specificity_level"]),
                    "member_count": int(row["member_count"]),
                    "total_occurrences": int(row["total_occurrences"]),
                    "member_tag": member_tag,
                    "is_exact_match": member_tag.lower() in exact or str(row["representative_tag"]).lower() in exact,
                }
            )
        return grouped
    finally:
        connection.close()


def count_postgres_hits(store: PostgresGameStore, tag: str) -> dict[str, int]:
    sql = """
        SELECT
            COUNT(*) FILTER (WHERE canonical_metadata ->> 'signature_tag' = %s) AS signature_hits,
            COUNT(*) FILTER (WHERE COALESCE(canonical_metadata -> 'niche_anchors', '[]'::jsonb) ? %s) AS anchor_hits,
            COUNT(*) FILTER (WHERE COALESCE(canonical_metadata -> 'identity_tags', '[]'::jsonb) ? %s) AS identity_hits,
            COUNT(*) FILTER (WHERE COALESCE(canonical_metadata -> 'micro_tags', '[]'::jsonb) ? %s) AS micro_hits,
            COUNT(*) FILTER (WHERE COALESCE(canonical_metadata -> 'setting_tags', '[]'::jsonb) ? %s) AS setting_hits,
            COUNT(*) FILTER (WHERE canonical_metadata ->> 'music_primary' = %s OR canonical_metadata ->> 'music_secondary' = %s) AS music_hits,
            COUNT(*) FILTER (WHERE COALESCE(canonical_vectors -> 'mechanics', '{}'::jsonb) ? %s) AS mechanics_hits,
            COUNT(*) FILTER (WHERE COALESCE(canonical_vectors -> 'narrative', '{}'::jsonb) ? %s) AS narrative_hits,
            COUNT(*) FILTER (WHERE COALESCE(canonical_vectors -> 'vibe', '{}'::jsonb) ? %s) AS vibe_hits,
            COUNT(*) FILTER (WHERE COALESCE(canonical_vectors -> 'structure_loop', '{}'::jsonb) ? %s) AS structure_loop_hits
        FROM games
    """
    with store._connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, (tag, tag, tag, tag, tag, tag, tag, tag, tag, tag, tag))
            row = cursor.fetchone()
    return {key: int(value or 0) for key, value in dict(row).items()}


def simulate_ui_boost(
    store: PostgresGameStore,
    retriever: CandidateRetriever,
    game: dict[str, Any],
    lane: str,
    tag: str,
    limit: int,
) -> list[dict[str, Any]]:
    context_percentages = default_context_percentages()
    component_percentages = default_component_percentages()
    appeal_axes = default_appeal_axes(game["metadata"])
    vector_boosts = {} if lane == "music" else {lane: {tag: 100.0}}
    soundtrack_boosts = {tag: 100.0} if lane == "music" else {}

    started = time.perf_counter()
    candidate_games = retriever.retrieve_candidates(
        game,
        chroma_limit=300,
        prescreen_limit=450,
        merged_limit=300,
        context_percentages=context_percentages,
        tag_boosts=vector_boosts,
        soundtrack_boosts=soundtrack_boosts,
    )
    retrieval_elapsed = time.perf_counter() - started

    started = time.perf_counter()
    recommendations = recommend_games(
        game,
        candidate_games,
        extra_vector_boosts=vector_boosts,
        extra_soundtrack_boosts=soundtrack_boosts,
        context_percentages=context_percentages,
        component_percentages=component_percentages,
        appeal_axes=appeal_axes,
        added_genres={"primary": [], "sub": [], "sub_sub": []},
        removed_genres={"primary": [], "sub": [], "sub_sub": []},
        limit=limit,
    )
    rerank_elapsed = time.perf_counter() - started
    print()
    print("UI-style simulation")
    print(f"  boost lane: {lane}")
    print(f"  boost tag: {tag}")
    print(f"  retrieval: {retrieval_elapsed:.3f}s")
    print(f"  rerank: {rerank_elapsed:.3f}s")
    print(f"  hydrated candidates: {len(candidate_games)}")
    return recommendations


def main() -> int:
    args = parse_args()
    dsn = postgres_dsn_from_env()
    if not dsn:
        raise SystemExit("STEAM_REC_POSTGRES_DSN must be set")

    store = PostgresGameStore(dsn)
    retriever = CandidateRetriever(chroma_dir=chroma_dir_path(), store=store)
    game = resolve_game(store, args.game)
    hits = find_base_tag_hits(game, args.needle)

    print("Base game")
    print(f"  appid: {game['appid']}")
    print(f"  name: {game['name']}")
    print(f"  needle: {args.needle}")
    print()

    if not hits:
        print("No matching tags found on the base game.")
        return 0

    print("Base-game tag hits")
    for hit in hits:
        print(f"  lane={hit['lane']:<14} source={hit['source']:<16} tag={hit['tag']}")

    exact_tags = [hit["tag"] for hit in hits]
    group_rows = inspect_sqlite_groups(args.needle, exact_tags)
    print()
    print("Canonical group hits from final SQLite")
    if not group_rows:
        print("  none")
    else:
        for row in group_rows[:50]:
            marker = " exact" if row["is_exact_match"] else ""
            print(
                "  "
                f"context={row['context']:<18} rep={row['representative_tag']:<28} "
                f"member={row['member_tag']:<32} level={row['specificity_level']} "
                f"members={row['member_count']}{marker}"
            )

    print()
    print("Postgres exact-tag counts")
    for tag in exact_tags:
        counts = count_postgres_hits(store, tag)
        print(f"  tag={tag}")
        print(f"    {json.dumps(counts, sort_keys=True)}")

    chosen = hits[0]
    recommendations = simulate_ui_boost(
        store,
        retriever,
        game,
        lane=chosen["lane"],
        tag=chosen["tag"],
        limit=args.limit,
    )

    print()
    print("Top results")
    for index, result in enumerate(recommendations[:10], start=1):
        matched = result.get("matched_tags", {}) or {}
        print(
            f"{index}. {result['name']} [{result['appid']}] "
            f"score={result['total_score']:.4f} "
            f"identity={matched.get('identity', [])} "
            f"mechanics={matched.get('mechanics', [])} "
            f"struct={matched.get('structure_loop', [])}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
