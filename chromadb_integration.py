"""
ChromaDB Integration for Steam Game Reviews
Simple vector database for game similarity search
"""

import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict, Optional
import json
from steam_review_analyzer import pull_insightful_reviews


class SteamChromaDB:
    """ChromaDB integration for Steam game reviews"""

    def __init__(self, persist_directory: str = "./chroma_db"):
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(path=persist_directory)

        # Use default sentence transformer
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        # Create or get collection
        self.collection = self.client.get_or_create_collection(
            name="steam_games",
            embedding_function=self.embedding_function,
            metadata={"description": "Steam game reviews and descriptions"}
        )

    def add_game(self, appid: int, name: str = None):
        """
        Add a game to ChromaDB by fetching its insightful reviews

        Args:
            appid: Steam app ID
            name: Game name (optional)
        """
        # Get insightful reviews
        reviews = pull_insightful_reviews(appid)

        if not reviews:
            print(f"No insightful reviews found for appid {appid}")
            return

        # Add to ChromaDB
        self.collection.add(
            documents=[reviews],
            ids=[str(appid)],
            metadatas=[{
                "appid": appid,
                "name": name or f"Game_{appid}"
            }]
        )

        print(f"Added game {appid} ({name}) to ChromaDB")

    def add_games_batch(self, games: List[Dict]):
        """
        Add multiple games to ChromaDB

        Args:
            games: List of dicts with 'appid' and 'name' keys
        """
        documents = []
        ids = []
        metadatas = []

        for game in games:
            appid = game["appid"]
            reviews = pull_insightful_reviews(appid)

            if reviews:
                documents.append(reviews)
                ids.append(str(appid))
                metadatas.append({
                    "appid": appid,
                    "name": game.get("name", f"Game_{appid}")
                })

        if documents:
            self.collection.add(
                documents=documents,
                ids=ids,
                metadatas=metadatas
            )
            print(f"Added {len(documents)} games to ChromaDB")

    def find_similar_games(self, appid: int, n_results: int = 5) -> List[Dict]:
        """
        Find games similar to the given appid

        Args:
            appid: Steam app ID to search for
            n_results: Number of similar games to return

        Returns:
            List of similar games with metadata
        """
        # Get the game's reviews as query
        query_text = pull_insightful_reviews(appid)

        if not query_text:
            print(f"No reviews found for appid {appid}")
            return []

        # Search for similar games
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results + 1  # +1 because it might include itself
        )

        # Format results
        similar_games = []
        for i, game_id in enumerate(results["ids"][0]):
            if game_id != str(appid):  # Exclude the query game itself
                similar_games.append({
                    "appid": results["metadatas"][0][i]["appid"],
                    "name": results["metadatas"][0][i]["name"],
                    "distance": results["distances"][0][i] if "distances" in results else None
                })

        return similar_games[:n_results]

    def search_by_description(self, description: str, n_results: int = 5) -> List[Dict]:
        """
        Search for games by a text description

        Args:
            description: Text description of desired game type
            n_results: Number of results to return

        Returns:
            List of matching games
        """
        results = self.collection.query(
            query_texts=[description],
            n_results=n_results
        )

        # Format results
        games = []
        for i, game_id in enumerate(results["ids"][0]):
            games.append({
                "appid": results["metadatas"][0][i]["appid"],
                "name": results["metadatas"][0][i]["name"],
                "distance": results["distances"][0][i] if "distances" in results else None
            })

        return games

    def get_collection_stats(self) -> Dict:
        """Get statistics about the ChromaDB collection"""
        count = self.collection.count()
        return {
            "total_games": count,
            "collection_name": "steam_games",
            "embedding_model": "all-MiniLM-L6-v2"
        }

    def clear_collection(self):
        """Clear all data from the collection"""
        self.client.delete_collection("steam_games")
        self.collection = self.client.create_collection(
            name="steam_games",
            embedding_function=self.embedding_function
        )
        print("Collection cleared")


# Example usage functions
def quick_setup_chromadb(game_appids: List[int]):
    """
    Quick setup ChromaDB with a list of game IDs

    Args:
        game_appids: List of Steam app IDs
    """
    db = SteamChromaDB()

    for appid in game_appids:
        db.add_game(appid)

    stats = db.get_collection_stats()
    print(f"ChromaDB setup complete: {stats['total_games']} games indexed")


def find_games_like(appid: int, count: int = 5):
    """
    Find games similar to a given game

    Args:
        appid: Steam app ID
        count: Number of similar games to find

    Returns:
        List of similar games
    """
    db = SteamChromaDB()
    similar = db.find_similar_games(appid, count)

    print(f"\nGames similar to {appid}:")
    for game in similar:
        print(f"  - {game['name']} (appid: {game['appid']})")

    return similar


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "setup":
            # Setup ChromaDB with some popular games
            popular_games = [
                730,    # CS:GO
                570,    # Dota 2
                440,    # Team Fortress 2
                271590, # GTA V
                1172470 # Apex Legends
            ]
            quick_setup_chromadb(popular_games)

        elif command == "add":
            # Add a specific game
            if len(sys.argv) > 2:
                appid = int(sys.argv[2])
                db = SteamChromaDB()
                db.add_game(appid)
            else:
                print("Usage: python chromadb_integration.py add <appid>")

        elif command == "similar":
            # Find similar games
            if len(sys.argv) > 2:
                appid = int(sys.argv[2])
                count = int(sys.argv[3]) if len(sys.argv) > 3 else 5
                find_games_like(appid, count)
            else:
                print("Usage: python chromadb_integration.py similar <appid> [count]")

        elif command == "search":
            # Search by description
            if len(sys.argv) > 2:
                description = " ".join(sys.argv[2:])
                db = SteamChromaDB()
                results = db.search_by_description(description)
                print(f"\nGames matching '{description}':")
                for game in results:
                    print(f"  - {game['name']} (appid: {game['appid']})")
            else:
                print("Usage: python chromadb_integration.py search <description>")

        elif command == "stats":
            # Show collection stats
            db = SteamChromaDB()
            stats = db.get_collection_stats()
            print(f"ChromaDB Stats: {stats}")

        else:
            print("Unknown command:", command)
    else:
        print("Usage:")
        print("  python chromadb_integration.py setup              # Setup with popular games")
        print("  python chromadb_integration.py add <appid>        # Add a game")
        print("  python chromadb_integration.py similar <appid>    # Find similar games")
        print("  python chromadb_integration.py search <text>      # Search by description")
        print("  python chromadb_integration.py stats              # Show collection stats")