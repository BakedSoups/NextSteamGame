#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from backend.db import FinalGameStore
from backend.recommender import recommend_games


FINAL_DB_PATH = Path("data/steam_final_canon.db")
BASE_GAME_QUERY = "Counter-Strike"
RESULT_LIMIT = 15

EXTRA_VECTOR_BOOSTS = {
    "mechanics": {
        "teamplay": 1.20,
        "strategy": 1.10,
        "shooting": 1.10,
    },
    "vibe": {
        "competitive": 1.05,
    },
}

ADDED_GENRES = {
    "primary": [],
    "sub": [],
    "traits": ["Team Based", "Competitive"],
}

REMOVED_GENRES = {
    "primary": [],
    "sub": [],
    "traits": [],
}


def main() -> int:
    store = FinalGameStore(FINAL_DB_PATH)
    all_games = store.load_all_games()
    matches = store.search_games(BASE_GAME_QUERY, limit=5)
    if not matches:
        raise RuntimeError(f"Could not find a game matching {BASE_GAME_QUERY!r}")

    base_game = store.get_game(matches[0]["appid"])
    if base_game is None:
        raise RuntimeError("Failed to load base game")

    recommendations = recommend_games(
        base_game,
        all_games,
        extra_vector_boosts=EXTRA_VECTOR_BOOSTS,
        added_genres=ADDED_GENRES,
        removed_genres=REMOVED_GENRES,
        limit=RESULT_LIMIT,
    )

    print(f"Base game: {base_game['name']} ({base_game['appid']})")
    print("\nBase vectors:")
    print(json.dumps(base_game["vectors"], indent=2, sort_keys=True))
    print("\nBase genre tree:")
    print(json.dumps(base_game["metadata"].get("genre_tree", {}), indent=2, sort_keys=True))
    print("\nTop matches:")
    for rank, item in enumerate(recommendations, start=1):
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
