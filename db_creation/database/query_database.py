#!/usr/bin/env python3
"""
Database Query Interface
Query SQLite metadata and ChromaDB vectors
"""

import sys
import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional

import chromadb
from chromadb.utils import embedding_functions


class DatabaseQuery:
    """Query interface for game vector databases"""

    def __init__(self, sqlite_db_path: str = "game_vectors.db", chroma_db_path: str = "./chroma_vectors"):
        self.sqlite_db_path = sqlite_db_path
        self.chroma_db_path = chroma_db_path

        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=chroma_db_path)
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        # Get collections
        try:
            self.gameplay_collection = self.chroma_client.get_collection(
                name="gameplay_vectors",
                embedding_function=self.embedding_function
            )
            self.music_collection = self.chroma_client.get_collection(
                name="music_vectors",
                embedding_function=self.embedding_function
            )
            self.vibes_collection = self.chroma_client.get_collection(
                name="vibes_vectors",
                embedding_function=self.embedding_function
            )
        except Exception as e:
            print(f"⚠️ Warning: ChromaDB collections not found: {e}")
            self.gameplay_collection = None
            self.music_collection = None
            self.vibes_collection = None

    def get_game_info(self, appid: int) -> Optional[Dict]:
        """Get complete game information from SQLite"""

        if not Path(self.sqlite_db_path).exists():
            print(f"❌ Database not found: {self.sqlite_db_path}")
            return None

        conn = sqlite3.connect(self.sqlite_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Get basic game info
            cursor.execute("SELECT * FROM games WHERE appid = ?", (appid,))
            game_row = cursor.fetchone()

            if not game_row:
                return None

            game_info = dict(game_row)

            # Get gameplay vectors
            cursor.execute("""
                SELECT element_type, element_name, percentage, description
                FROM gameplay_vectors WHERE appid = ? ORDER BY percentage DESC
            """, (appid,))

            gameplay_vectors = {"main": {}, "sub": {}, "description": ""}
            for row in cursor.fetchall():
                if row["element_type"] == "main":
                    gameplay_vectors["main"][row["element_name"]] = row["percentage"]
                else:
                    gameplay_vectors["sub"][row["element_name"]] = row["percentage"]
                if row["description"]:
                    gameplay_vectors["description"] = row["description"]

            # Get music vectors (hierarchical)
            cursor.execute("""
                SELECT genre_type, genre_name, parent_genre, percentage, description
                FROM music_vectors WHERE appid = ? ORDER BY percentage DESC
            """, (appid,))

            music_vectors = {"main_genres": {}, "genre_subgenres": {}, "description": ""}
            for row in cursor.fetchall():
                if row["genre_type"] == "main":
                    music_vectors["main_genres"][row["genre_name"]] = row["percentage"]
                else:
                    parent = row["parent_genre"]
                    if parent not in music_vectors["genre_subgenres"]:
                        music_vectors["genre_subgenres"][parent] = {}
                    music_vectors["genre_subgenres"][parent][row["genre_name"]] = row["percentage"]
                if row["description"]:
                    music_vectors["description"] = row["description"]

            # Get vibes vectors
            cursor.execute("""
                SELECT vibe_type, vibe_name, percentage, description
                FROM vibes_vectors WHERE appid = ? ORDER BY percentage DESC
            """, (appid,))

            vibes_vectors = {"main": {}, "sub": {}, "description": ""}
            for row in cursor.fetchall():
                if row["vibe_type"] == "main":
                    vibes_vectors["main"][row["vibe_name"]] = row["percentage"]
                else:
                    vibes_vectors["sub"][row["vibe_name"]] = row["percentage"]
                if row["description"]:
                    vibes_vectors["description"] = row["description"]

            # Combine all data
            game_info["gameplay_vector"] = gameplay_vectors
            game_info["music_vector"] = music_vectors
            game_info["vibes_vector"] = vibes_vectors

            return game_info

        except Exception as e:
            print(f"Error querying game {appid}: {e}")
            return None
        finally:
            conn.close()

    def search_by_gameplay(self, query: str, n_results: int = 5) -> List[Dict]:
        """Search games by gameplay description"""
        if not self.gameplay_collection:
            return []

        try:
            results = self.gameplay_collection.query(
                query_texts=[query],
                n_results=n_results
            )

            games = []
            for i, game_id in enumerate(results["ids"][0]):
                game_info = self.get_game_info(int(game_id))
                if game_info:
                    games.append({
                        "appid": int(game_id),
                        "distance": results["distances"][0][i] if "distances" in results else None,
                        "metadata": results["metadatas"][0][i],
                        "game_info": game_info
                    })

            return games

        except Exception as e:
            print(f"Error searching gameplay: {e}")
            return []

    def search_by_music(self, query: str, n_results: int = 5) -> List[Dict]:
        """Search games by music description"""
        if not self.music_collection:
            return []

        try:
            results = self.music_collection.query(
                query_texts=[query],
                n_results=n_results
            )

            games = []
            for i, game_id in enumerate(results["ids"][0]):
                game_info = self.get_game_info(int(game_id))
                if game_info:
                    games.append({
                        "appid": int(game_id),
                        "distance": results["distances"][0][i] if "distances" in results else None,
                        "metadata": results["metadatas"][0][i],
                        "game_info": game_info
                    })

            return games

        except Exception as e:
            print(f"Error searching music: {e}")
            return []

    def search_by_vibes(self, query: str, n_results: int = 5) -> List[Dict]:
        """Search games by vibes/atmosphere"""
        if not self.vibes_collection:
            return []

        try:
            results = self.vibes_collection.query(
                query_texts=[query],
                n_results=n_results
            )

            games = []
            for i, game_id in enumerate(results["ids"][0]):
                game_info = self.get_game_info(int(game_id))
                if game_info:
                    games.append({
                        "appid": int(game_id),
                        "distance": results["distances"][0][i] if "distances" in results else None,
                        "metadata": results["metadatas"][0][i],
                        "game_info": game_info
                    })

            return games

        except Exception as e:
            print(f"Error searching vibes: {e}")
            return []

    def find_similar_games(self, appid: int, vector_type: str = "gameplay", n_results: int = 5) -> List[Dict]:
        """Find games similar to a given game"""

        collections = {
            "gameplay": self.gameplay_collection,
            "music": self.music_collection,
            "vibes": self.vibes_collection
        }

        if vector_type not in collections or not collections[vector_type]:
            return []

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
                    game_info = self.get_game_info(int(game_id))
                    if game_info:
                        similar_games.append({
                            "appid": int(game_id),
                            "distance": search_results["distances"][0][i] if "distances" in search_results else None,
                            "game_info": game_info
                        })

            return similar_games[:n_results]

        except Exception as e:
            print(f"Error finding similar games: {e}")
            return []

    def list_all_games(self) -> List[Dict]:
        """List all games in the database"""

        if not Path(self.sqlite_db_path).exists():
            return []

        conn = sqlite3.connect(self.sqlite_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT appid, name, consensus FROM games ORDER BY appid")
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error listing games: {e}")
            return []
        finally:
            conn.close()

    def print_game_info(self, game_info: Dict):
        """Pretty print game information"""
        print(f"\n🎮 Game AppID: {game_info['appid']}")
        print("=" * 60)

        print(f"\n✨ Consensus:")
        print(f"{game_info.get('consensus', 'No consensus available')}")

        # Gameplay vector
        gameplay = game_info.get('gameplay_vector', {})
        if gameplay.get('main'):
            print(f"\n🎯 Gameplay Vector:")
            for element, percentage in sorted(gameplay['main'].items(), key=lambda x: x[1], reverse=True):
                print(f"  • {element}: {percentage}%")
            if gameplay.get('sub'):
                print("  Sub-mechanics:")
                for mechanic, percentage in sorted(gameplay['sub'].items(), key=lambda x: x[1], reverse=True):
                    print(f"    - {mechanic}: {percentage}%")

        # Music vector (hierarchical)
        music = game_info.get('music_vector', {})
        if music.get('main_genres'):
            print(f"\n🎵 Music Vector:")
            for genre, percentage in sorted(music['main_genres'].items(), key=lambda x: x[1], reverse=True):
                print(f"  🎼 {genre.upper()}: {percentage}%")
                # Show sub-genres
                subgenres = music.get('genre_subgenres', {}).get(genre, {})
                for subgenre, sub_percent in sorted(subgenres.items(), key=lambda x: x[1], reverse=True):
                    print(f"     └─ {subgenre}: {sub_percent}%")

        # Vibes vector
        vibes = game_info.get('vibes_vector', {})
        if vibes.get('main'):
            print(f"\n✨ Vibes Vector:")
            for vibe, percentage in sorted(vibes['main'].items(), key=lambda x: x[1], reverse=True):
                print(f"  • {vibe}: {percentage}%")


def main():
    """Interactive query interface"""

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m database.query_database info <appid>              # Get game info")
        print("  python -m database.query_database similar <appid> <type>    # Find similar games")
        print("  python -m database.query_database search <type> <query>     # Search by description")
        print("  python -m database.query_database list                      # List all games")
        print("")
        print("Types: gameplay, music, vibes")
        print("")
        print("Examples:")
        print("  python -m database.query_database info 1687950")
        print("  python -m database.query_database similar 1687950 music")
        print("  python -m database.query_database search music 'jazz and rock'")
        print("  python -m database.query_database search gameplay 'turn-based combat'")
        sys.exit(1)

    command = sys.argv[1]
    query = DatabaseQuery()

    if command == "info":
        if len(sys.argv) < 3:
            print("Usage: python -m database.query_database info <appid>")
            sys.exit(1)

        appid = int(sys.argv[2])
        game_info = query.get_game_info(appid)
        if game_info:
            query.print_game_info(game_info)
        else:
            print(f"❌ Game {appid} not found in database")

    elif command == "similar":
        if len(sys.argv) < 4:
            print("Usage: python -m database.query_database similar <appid> <type>")
            print("Types: gameplay, music, vibes")
            sys.exit(1)

        appid = int(sys.argv[2])
        vector_type = sys.argv[3]

        similar_games = query.find_similar_games(appid, vector_type, n_results=5)
        print(f"\n🔍 Games similar to {appid} ({vector_type}):")
        for game in similar_games:
            print(f"  AppID {game['appid']} (distance: {game.get('distance', 'N/A'):.3f})")

    elif command == "search":
        if len(sys.argv) < 4:
            print("Usage: python -m database.query_database search <type> <query>")
            print("Types: gameplay, music, vibes")
            sys.exit(1)

        search_type = sys.argv[2]
        search_query = " ".join(sys.argv[3:])

        if search_type == "gameplay":
            results = query.search_by_gameplay(search_query)
        elif search_type == "music":
            results = query.search_by_music(search_query)
        elif search_type == "vibes":
            results = query.search_by_vibes(search_query)
        else:
            print("❌ Invalid search type. Use: gameplay, music, vibes")
            sys.exit(1)

        print(f"\n🔍 Search results for '{search_query}' ({search_type}):")
        for game in results:
            print(f"  AppID {game['appid']} (distance: {game.get('distance', 'N/A'):.3f})")

    elif command == "list":
        games = query.list_all_games()
        print(f"\n📋 All games in database ({len(games)} total):")
        for game in games:
            consensus_preview = (game.get('consensus', '')[:50] + '...') if game.get('consensus') else 'No consensus'
            print(f"  AppID {game['appid']}: {consensus_preview}")

    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
