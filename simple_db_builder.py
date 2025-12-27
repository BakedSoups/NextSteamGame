"""
Simplified Database Builder using the Steam Review Analyzer library
Builds SQLite database and prepares data for ChromaDB
"""

import sqlite3
import json
import os
from typing import List, Dict, Optional
from datetime import datetime
import requests
from steam_review_analyzer import SteamReviewAnalyzer


class SimpleDatabaseBuilder:
    """Simple database builder focused on Steam games and reviews"""

    def __init__(self, db_path: str = "steam_games.db"):
        self.db_path = db_path
        self.analyzer = SteamReviewAnalyzer()
        self.steamspy_api = "https://steamspy.com/api.php"
        self.steam_api = "https://store.steampowered.com/api"

    def build_games_database(self, max_games: int = 1000):
        """
        Build SQLite database with Steam games and their insightful reviews

        Args:
            max_games: Maximum number of games to process
        """
        print(f"Building database with up to {max_games} games...")

        # Create database schema
        self._create_schema()

        # Fetch games from SteamSpy
        games = self._fetch_popular_games(max_games)
        print(f"Fetched {len(games)} games from SteamSpy")

        # Process each game
        for i, (appid, game_data) in enumerate(games.items(), 1):
            if i > max_games:
                break

            print(f"Processing {i}/{min(len(games), max_games)}: {game_data['name']}")

            # Get insightful reviews
            reviews_text = self.analyzer.pull_insightful_reviews(int(appid))

            # Get review insights
            insights = self.analyzer.get_review_insights(int(appid))

            # Store in database
            self._store_game_data(appid, game_data, reviews_text, insights)

            if i % 10 == 0:
                print(f"Checkpoint: Processed {i} games")

        print(f"Database built successfully: {self.db_path}")

    def get_game_with_reviews(self, appid: int) -> Dict:
        """
        Get game data with insightful reviews from database

        Args:
            appid: Steam app ID

        Returns:
            Dictionary with game data and reviews
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM games WHERE appid = ?
        """, (appid,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return {}

    def export_for_chromadb(self) -> List[Dict]:
        """
        Export data in format ready for ChromaDB

        Returns:
            List of documents with metadata for ChromaDB
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT appid, name, insightful_reviews, sentiment_score, key_themes
            FROM games
            WHERE insightful_reviews IS NOT NULL AND insightful_reviews != ''
        """)

        documents = []
        for row in cursor.fetchall():
            doc = {
                "id": str(row["appid"]),
                "text": row["insightful_reviews"],
                "metadata": {
                    "appid": row["appid"],
                    "name": row["name"],
                    "sentiment": row["sentiment_score"],
                    "themes": json.loads(row["key_themes"]) if row["key_themes"] else []
                }
            }
            documents.append(doc)

        conn.close()
        return documents

    def _create_schema(self):
        """Create simple database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Drop existing table if it exists
        cursor.execute("DROP TABLE IF EXISTS games")

        # Create games table
        cursor.execute("""
            CREATE TABLE games (
                appid INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                owners TEXT,
                positive_reviews INTEGER,
                negative_reviews INTEGER,
                insightful_reviews TEXT,
                sentiment_score REAL,
                key_themes TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def _fetch_popular_games(self, limit: int) -> Dict:
        """Fetch popular games from SteamSpy"""
        try:
            # Get top games by owners
            response = requests.get(
                self.steamspy_api,
                params={"request": "top100in2weeks"},
                timeout=10
            )
            games = response.json()

            # If we need more, get all games
            if len(games) < limit:
                response = requests.get(
                    self.steamspy_api,
                    params={"request": "all", "page": "0"},
                    timeout=10
                )
                all_games = response.json()
                games.update(all_games)

            return dict(list(games.items())[:limit])

        except Exception as e:
            print(f"Error fetching games: {e}")
            return {}

    def _store_game_data(self, appid: str, game_data: Dict, reviews_text: str, insights: Dict):
        """Store game data in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO games
                (appid, name, owners, positive_reviews, negative_reviews,
                 insightful_reviews, sentiment_score, key_themes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(appid),
                game_data.get("name", "Unknown"),
                game_data.get("owners", "0"),
                game_data.get("positive", 0),
                game_data.get("negative", 0),
                reviews_text,
                insights.get("average_sentiment", 0),
                json.dumps(insights.get("key_themes", []))
            ))

            conn.commit()
        except Exception as e:
            print(f"Error storing game {appid}: {e}")
        finally:
            conn.close()


# Simple usage functions
def build_steam_database(max_games: int = 100):
    """
    Build a Steam games database with insightful reviews

    Args:
        max_games: Number of games to process
    """
    builder = SimpleDatabaseBuilder()
    builder.build_games_database(max_games)


def get_reviews_for_game(appid: int) -> str:
    """
    Get insightful reviews for a specific game

    Args:
        appid: Steam app ID

    Returns:
        String of insightful reviews
    """
    analyzer = SteamReviewAnalyzer()
    return analyzer.pull_insightful_reviews(appid)


def export_to_chromadb():
    """Export database to ChromaDB format"""
    builder = SimpleDatabaseBuilder()
    documents = builder.export_for_chromadb()

    # Save to JSON file
    with open("chromadb_documents.json", "w") as f:
        json.dump(documents, f, indent=2)

    print(f"Exported {len(documents)} documents to chromadb_documents.json")
    return documents


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "build":
            # Build database
            max_games = int(sys.argv[2]) if len(sys.argv) > 2 else 100
            build_steam_database(max_games)

        elif command == "review":
            # Get reviews for specific game
            if len(sys.argv) > 2:
                appid = int(sys.argv[2])
                reviews = get_reviews_for_game(appid)
                print(f"Reviews for {appid}:")
                print(reviews)
            else:
                print("Usage: python simple_db_builder.py review <appid>")

        elif command == "export":
            # Export to ChromaDB format
            export_to_chromadb()

        else:
            print("Unknown command:", command)
    else:
        print("Usage:")
        print("  python simple_db_builder.py build [max_games]  # Build database")
        print("  python simple_db_builder.py review <appid>     # Get reviews for game")
        print("  python simple_db_builder.py export             # Export to ChromaDB format")