#!/usr/bin/env python3
"""
Database build entrypoint.

Builds both SQLite and ChromaDB from the analysis pipeline.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from db_creation.database.stage2_db_converter import Stage2DBConverter
else:
    from .stage2_db_converter import Stage2DBConverter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build SQLite and ChromaDB from Steam review analysis."
    )
    parser.add_argument(
        "appids",
        nargs="*",
        type=int,
        default=[1687950],
        help="Steam app IDs to process. Defaults to Persona 3 Reload (1687950).",
    )
    parser.add_argument(
        "--num-reviews",
        type=int,
        default=10,
        help="Number of insightful reviews to analyze per game.",
    )
    parser.add_argument(
        "--sqlite-db",
        default="game_vectors.db",
        help="Path to the SQLite database file.",
    )
    parser.add_argument(
        "--chroma-db",
        default="./chroma_vectors",
        help="Path to the ChromaDB persistence directory.",
    )
    return parser.parse_args()


def build_databases(appids: List[int], num_reviews: int, sqlite_db: str, chroma_db: str) -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not set")
        print("Set it with: export OPENAI_API_KEY='your-key'")
        return 1

    converter = Stage2DBConverter(sqlite_db_path=sqlite_db, chroma_db_path=chroma_db)
    converter.setup_databases()

    print(f"\n🔄 Building databases for {len(appids)} game(s)...")

    success_count = 0
    for appid in appids:
        if converter.process_game(appid, num_reviews=num_reviews):
            success_count += 1

    print(f"\n✅ Build complete: {success_count}/{len(appids)} games processed")

    stats = converter.get_database_stats()
    print(f"\n📊 Database Statistics:")
    print(f"  SQLite Database: {converter.sqlite_db_path}")
    print(f"  ChromaDB Path: {converter.chroma_db_path}")
    print(f"  Total games: {stats['total_games']}")
    print(f"  Games with gameplay vectors: {stats['games_with_gameplay']}")
    print(f"  Games with music vectors: {stats['games_with_music']}")
    print(f"  Games with vibes vectors: {stats['games_with_vibes']}")
    print(f"  ChromaDB gameplay vectors: {stats['gameplay_vectors']}")
    print(f"  ChromaDB music vectors: {stats['music_vectors']}")
    print(f"  ChromaDB vibes vectors: {stats['vibes_vectors']}")

    return 0 if success_count == len(appids) else 2


def main() -> int:
    args = parse_args()

    if args.num_reviews < 1:
        print("❌ Error: --num-reviews must be at least 1")
        return 1

    return build_databases(
        appids=args.appids,
        num_reviews=args.num_reviews,
        sqlite_db=args.sqlite_db,
        chroma_db=args.chroma_db,
    )


if __name__ == "__main__":
    sys.exit(main())
