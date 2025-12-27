#!/usr/bin/env python3
"""
Simplified Steam Database Builder
Uses the clean steam_review_analyzer library
"""

import sys
import os
from pathlib import Path
from simple_db_builder import build_steam_database, export_to_chromadb
from chromadb_integration import SteamChromaDB


def main():
    """Main entry point for database builder"""

    # Check for OpenAI API key
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        print("Please set it using: export OPENAI_API_KEY='your-api-key'")
        print("Or create a .env file with: OPENAI_API_KEY=your-api-key")
        sys.exit(1)

    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "--help" or command == "-h":
            print_help()

        elif command == "build":
            # Build SQLite database
            max_games = int(sys.argv[2]) if len(sys.argv) > 2 else 100
            print(f"🚀 Building database with {max_games} games...")
            build_steam_database(max_games)
            print("✅ SQLite database built successfully!")

        elif command == "chromadb":
            # Export to ChromaDB
            print("🔄 Exporting to ChromaDB format...")
            documents = export_to_chromadb()

            # Optionally load into ChromaDB
            if "--load" in sys.argv:
                print("📦 Loading into ChromaDB...")
                db = SteamChromaDB()
                for doc in documents:
                    db.add_game(
                        appid=doc["metadata"]["appid"],
                        name=doc["metadata"]["name"]
                    )
                print(f"✅ Loaded {len(documents)} games into ChromaDB")

        elif command == "all":
            # Build everything
            max_games = int(sys.argv[2]) if len(sys.argv) > 2 else 100

            print(f"🏗️ Full pipeline: Building database with {max_games} games")

            # Step 1: Build SQLite
            print("\n📊 Step 1: Building SQLite database...")
            build_steam_database(max_games)

            # Step 2: Export to ChromaDB
            print("\n🔄 Step 2: Exporting to ChromaDB...")
            documents = export_to_chromadb()

            # Step 3: Load into ChromaDB
            print("\n📦 Step 3: Loading into ChromaDB...")
            db = SteamChromaDB()
            for doc in documents:
                db.add_game(
                    appid=doc["metadata"]["appid"],
                    name=doc["metadata"]["name"]
                )

            print(f"\n✨ Complete! Built database with {max_games} games")
            print(f"   - SQLite: steam_games.db")
            print(f"   - ChromaDB: ./chroma_db/")

        else:
            print(f"❌ Unknown command: {command}")
            print_help()
    else:
        # Default: show help
        print_help()


def print_help():
    """Print help message"""
    print("""
Steam Database Builder - Simplified Version
==========================================

Build a database of Steam games with insightful reviews

Commands:
  python database_builder.py build [max_games]
    Build SQLite database with Steam games and reviews
    Default: 100 games

  python database_builder.py chromadb [--load]
    Export SQLite to ChromaDB format (JSON)
    --load: Also load into ChromaDB vector database

  python database_builder.py all [max_games]
    Run complete pipeline: SQLite → ChromaDB
    Default: 100 games

Examples:
  python database_builder.py build 500        # Build with 500 games
  python database_builder.py chromadb --load  # Export and load to ChromaDB
  python database_builder.py all 1000         # Full pipeline with 1000 games

Requirements:
  - Set OPENAI_API_KEY environment variable
  - Install dependencies: pip install -r requirements.txt
""")


if __name__ == "__main__":
    main()