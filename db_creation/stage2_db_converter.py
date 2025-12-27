#!/usr/bin/env python3
"""
Stage 2: Database Converter
Converts vector analysis results to SQLite + ChromaDB
"""

import sys
import json
import sqlite3
import os
from pathlib import Path
from typing import Dict, List, Optional

# Add analyzers path
sys.path.append(str(Path(__file__).parent / 'analyzers'))

from vector_analyzer import VectorAnalyzer
import chromadb
from chromadb.utils import embedding_functions


class Stage2DBConverter:
    """Converts vector analysis to SQLite + ChromaDB"""

    def __init__(self, sqlite_db_path: str = "game_vectors.db", chroma_db_path: str = "./chroma_vectors"):
        self.sqlite_db_path = sqlite_db_path
        self.chroma_db_path = chroma_db_path
        self.analyzer = VectorAnalyzer()

        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=chroma_db_path)
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

    def setup_databases(self):
        """Initialize SQLite schema and ChromaDB collection"""
        print("🏗️ Setting up databases...")

        # Setup SQLite
        self._create_sqlite_schema()

        # Setup ChromaDB collections
        self._create_chroma_collections()

        print("✅ Database setup complete")

    def _create_sqlite_schema(self):
        """Create SQLite database schema for game metadata"""
        conn = sqlite3.connect(self.sqlite_db_path)
        cursor = conn.cursor()

        # Main games table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            appid INTEGER PRIMARY KEY,
            name TEXT,
            consensus TEXT,
            num_reviews_analyzed INTEGER,
            analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Gameplay vector table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS gameplay_vectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appid INTEGER,
            element_type TEXT,  -- 'main' or 'sub'
            element_name TEXT,
            percentage INTEGER,
            description TEXT,
            FOREIGN KEY (appid) REFERENCES games (appid)
        )
        """)

        # Music vector table (hierarchical)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS music_vectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appid INTEGER,
            genre_type TEXT,     -- 'main' or 'sub'
            genre_name TEXT,
            parent_genre TEXT,   -- For sub-genres
            percentage INTEGER,
            description TEXT,
            FOREIGN KEY (appid) REFERENCES games (appid)
        )
        """)

        # Vibes vector table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS vibes_vectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appid INTEGER,
            vibe_type TEXT,      -- 'main' or 'sub'
            vibe_name TEXT,
            percentage INTEGER,
            description TEXT,
            FOREIGN KEY (appid) REFERENCES games (appid)
        )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gameplay_appid ON gameplay_vectors(appid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_music_appid ON music_vectors(appid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vibes_appid ON vibes_vectors(appid)")

        conn.commit()
        conn.close()

    def _create_chroma_collections(self):
        """Create ChromaDB collections for vector storage"""

        # Delete existing collections if they exist
        try:
            self.chroma_client.delete_collection("gameplay_vectors")
            self.chroma_client.delete_collection("music_vectors")
            self.chroma_client.delete_collection("vibes_vectors")
        except:
            pass

        # Create collections
        self.gameplay_collection = self.chroma_client.create_collection(
            name="gameplay_vectors",
            embedding_function=self.embedding_function,
            metadata={"description": "Gameplay element vectors"}
        )

        self.music_collection = self.chroma_client.create_collection(
            name="music_vectors",
            embedding_function=self.embedding_function,
            metadata={"description": "Music genre vectors"}
        )

        self.vibes_collection = self.chroma_client.create_collection(
            name="vibes_vectors",
            embedding_function=self.embedding_function,
            metadata={"description": "Vibes and atmosphere vectors"}
        )

    def process_game(self, appid: int, num_reviews: int = 10) -> bool:
        """Process a single game and store in databases"""
        print(f"🎮 Processing AppID {appid}...")

        try:
            # Get vector analysis
            results = self.analyzer.analyze_game_vectors(appid, num_reviews)

            if "error" in results:
                print(f"❌ Error analyzing {appid}: {results['error']}")
                return False

            # Store in SQLite
            self._store_in_sqlite(results)

            # Store vectors in ChromaDB
            self._store_in_chromadb(results)

            print(f"✅ Stored AppID {appid} in databases")
            return True

        except Exception as e:
            print(f"❌ Error processing {appid}: {e}")
            return False

    def _store_in_sqlite(self, results: Dict):
        """Store game metadata and vectors in SQLite"""
        conn = sqlite3.connect(self.sqlite_db_path)
        cursor = conn.cursor()

        appid = results["appid"]

        try:
            # Store main game info
            cursor.execute("""
                INSERT OR REPLACE INTO games (appid, name, consensus, num_reviews_analyzed)
                VALUES (?, ?, ?, ?)
            """, (
                appid,
                f"Game_{appid}",  # We don't have name from analysis
                results.get("consensus", ""),
                results.get("num_reviews_analyzed", 0)
            ))

            # Clear existing vectors for this game
            cursor.execute("DELETE FROM gameplay_vectors WHERE appid = ?", (appid,))
            cursor.execute("DELETE FROM music_vectors WHERE appid = ?", (appid,))
            cursor.execute("DELETE FROM vibes_vectors WHERE appid = ?", (appid,))

            # Store gameplay vectors
            gameplay = results.get("gameplay_vector", {})
            description = gameplay.get("description", "")

            for element, percentage in gameplay.get("main", {}).items():
                cursor.execute("""
                    INSERT INTO gameplay_vectors (appid, element_type, element_name, percentage, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (appid, "main", element, percentage, description))

            for element, percentage in gameplay.get("sub", {}).items():
                cursor.execute("""
                    INSERT INTO gameplay_vectors (appid, element_type, element_name, percentage, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (appid, "sub", element, percentage, description))

            # Store music vectors (hierarchical)
            music = results.get("music_vector", {})
            music_description = music.get("description", "")

            # Main genres
            for genre, percentage in music.get("main_genres", {}).items():
                cursor.execute("""
                    INSERT INTO music_vectors (appid, genre_type, genre_name, parent_genre, percentage, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (appid, "main", genre, None, percentage, music_description))

            # Sub-genres (hierarchical)
            for parent_genre, subgenres in music.get("genre_subgenres", {}).items():
                for subgenre, percentage in subgenres.items():
                    cursor.execute("""
                        INSERT INTO music_vectors (appid, genre_type, genre_name, parent_genre, percentage, description)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (appid, "sub", subgenre, parent_genre, percentage, music_description))

            # Store vibes vectors
            vibes = results.get("vibes_vector", {})
            vibes_description = vibes.get("description", "")

            for vibe, percentage in vibes.get("main", {}).items():
                cursor.execute("""
                    INSERT INTO vibes_vectors (appid, vibe_type, vibe_name, percentage, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (appid, "main", vibe, percentage, vibes_description))

            for vibe, percentage in vibes.get("sub", {}).items():
                cursor.execute("""
                    INSERT INTO vibes_vectors (appid, vibe_type, vibe_name, percentage, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (appid, "sub", vibe, percentage, vibes_description))

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _store_in_chromadb(self, results: Dict):
        """Store vectors in ChromaDB for similarity search"""
        appid = results["appid"]

        # Create vector representations as text
        gameplay_text = self._create_gameplay_text(results.get("gameplay_vector", {}))
        music_text = self._create_music_text(results.get("music_vector", {}))
        vibes_text = self._create_vibes_text(results.get("vibes_vector", {}))

        # Store in ChromaDB collections
        if gameplay_text:
            self.gameplay_collection.add(
                documents=[gameplay_text],
                ids=[str(appid)],
                metadatas=[{
                    "appid": appid,
                    "type": "gameplay",
                    "consensus": results.get("consensus", "")[:500]  # Truncate
                }]
            )

        if music_text:
            self.music_collection.add(
                documents=[music_text],
                ids=[str(appid)],
                metadatas=[{
                    "appid": appid,
                    "type": "music",
                    "consensus": results.get("consensus", "")[:500]
                }]
            )

        if vibes_text:
            self.vibes_collection.add(
                documents=[vibes_text],
                ids=[str(appid)],
                metadatas=[{
                    "appid": appid,
                    "type": "vibes",
                    "consensus": results.get("consensus", "")[:500]
                }]
            )

    def _create_gameplay_text(self, gameplay_vector: Dict) -> str:
        """Convert gameplay vector to searchable text"""
        parts = []

        # Add main elements
        for element, percentage in gameplay_vector.get("main", {}).items():
            parts.append(f"{element} {percentage}%")

        # Add sub-mechanics
        for mechanic, percentage in gameplay_vector.get("sub", {}).items():
            parts.append(f"{mechanic} {percentage}%")

        # Add description
        if gameplay_vector.get("description"):
            parts.append(gameplay_vector["description"])

        return " ".join(parts)

    def _create_music_text(self, music_vector: Dict) -> str:
        """Convert hierarchical music vector to searchable text"""
        parts = []

        # Add main genres
        for genre, percentage in music_vector.get("main_genres", {}).items():
            parts.append(f"{genre} {percentage}%")

        # Add sub-genres
        for parent_genre, subgenres in music_vector.get("genre_subgenres", {}).items():
            for subgenre, percentage in subgenres.items():
                parts.append(f"{subgenre} {percentage}% {parent_genre}")

        # Add description
        if music_vector.get("description"):
            parts.append(music_vector["description"])

        return " ".join(parts)

    def _create_vibes_text(self, vibes_vector: Dict) -> str:
        """Convert vibes vector to searchable text"""
        parts = []

        # Add main vibes
        for vibe, percentage in vibes_vector.get("main", {}).items():
            parts.append(f"{vibe} {percentage}%")

        # Add sub-moods
        for mood, percentage in vibes_vector.get("sub", {}).items():
            parts.append(f"{mood} {percentage}%")

        # Add description
        if vibes_vector.get("description"):
            parts.append(vibes_vector["description"])

        return " ".join(parts)

    def find_similar_games(self, appid: int, vector_type: str = "gameplay", n_results: int = 5) -> List[Dict]:
        """Find games with similar vectors"""

        collections = {
            "gameplay": self.gameplay_collection,
            "music": self.music_collection,
            "vibes": self.vibes_collection
        }

        if vector_type not in collections:
            raise ValueError(f"Invalid vector_type: {vector_type}")

        collection = collections[vector_type]

        try:
            # Get the target game's document
            results = collection.get(ids=[str(appid)])

            if not results["documents"]:
                return []

            query_text = results["documents"][0]

            # Search for similar games
            search_results = collection.query(
                query_texts=[query_text],
                n_results=n_results + 1  # +1 because it includes itself
            )

            # Format results
            similar_games = []
            for i, game_id in enumerate(search_results["ids"][0]):
                if game_id != str(appid):  # Exclude the query game itself
                    similar_games.append({
                        "appid": int(game_id),
                        "distance": search_results["distances"][0][i] if "distances" in search_results else None,
                        "metadata": search_results["metadatas"][0][i]
                    })

            return similar_games[:n_results]

        except Exception as e:
            print(f"Error finding similar games: {e}")
            return []

    def get_database_stats(self) -> Dict:
        """Get statistics about stored data"""
        conn = sqlite3.connect(self.sqlite_db_path)
        cursor = conn.cursor()

        stats = {}

        # SQLite stats
        cursor.execute("SELECT COUNT(*) FROM games")
        stats["total_games"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT appid) FROM gameplay_vectors")
        stats["games_with_gameplay"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT appid) FROM music_vectors")
        stats["games_with_music"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT appid) FROM vibes_vectors")
        stats["games_with_vibes"] = cursor.fetchone()[0]

        # ChromaDB stats
        stats["gameplay_vectors"] = self.gameplay_collection.count()
        stats["music_vectors"] = self.music_collection.count()
        stats["vibes_vectors"] = self.vibes_collection.count()

        conn.close()
        return stats


def main():
    """Main function for Stage 2 processing"""

    if not os.getenv('OPENAI_API_KEY'):
        print("❌ Error: OPENAI_API_KEY not set")
        print("Set it with: export OPENAI_API_KEY='your-key'")
        sys.exit(1)

    # Initialize converter
    converter = Stage2DBConverter()

    # Setup databases
    converter.setup_databases()

    # Default: Process Persona 3 Reload
    test_games = [1687950]  # Persona 3 Reload

    if len(sys.argv) > 1:
        try:
            # Allow custom appids
            test_games = [int(sys.argv[1])]
        except ValueError:
            print("❌ Invalid AppID")
            sys.exit(1)

    # Process games
    print(f"\n🔄 Stage 2: Processing {len(test_games)} game(s)...")

    success_count = 0
    for appid in test_games:
        if converter.process_game(appid, num_reviews=10):
            success_count += 1

    print(f"\n✅ Stage 2 Complete: {success_count}/{len(test_games)} games processed")

    # Show stats
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

    # Test similarity search
    if success_count > 0:
        test_appid = test_games[0]
        print(f"\n🔍 Testing similarity search for AppID {test_appid}:")

        for vector_type in ["gameplay", "music", "vibes"]:
            similar = converter.find_similar_games(test_appid, vector_type, n_results=3)
            print(f"  {vector_type}: {len(similar)} similar games found")


if __name__ == "__main__":
    main()