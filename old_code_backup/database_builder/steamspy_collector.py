import requests
import sqlite3
import json
import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class SteamSpyGame:
    """Data class for SteamSpy game data"""
    appid: int
    name: str
    developer: str
    publisher: str
    score_rank: str  # Can be string or number from API
    positive: int
    negative: int
    owners: str
    average_forever: int

class SteamSpyCollector:
    """Collects game data from SteamSpy API and stores in SQLite"""

    def __init__(self, db_path: str = "./steamspy_all_games.db"):
        self.db_path = db_path
        self.max_games = 20000

    def create_database(self) -> None:
        """Create the SteamSpy database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS all_games (
            appid INTEGER PRIMARY KEY,
            name TEXT,
            developer TEXT,
            publisher TEXT,
            score_rank TEXT,
            positive INTEGER,
            negative INTEGER,
            owners TEXT,
            average_forever INTEGER
        )
        """)

        conn.commit()
        conn.close()
        logger.info(f"Created database schema at {self.db_path}")

    def fetch_steamspy_page(self, page: int) -> Optional[Dict[str, Any]]:
        """Fetch a single page from SteamSpy API"""
        url = f"https://steamspy.com/api.php?request=all&page={page}"

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Fetched page {page}: {len(data)} games")
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching page {page}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON for page {page}: {e}")
            return None

    def parse_game_data(self, game_data: Dict[str, Any]) -> SteamSpyGame:
        """Parse raw game data from SteamSpy API"""
        # Handle flexible score_rank (can be string or number)
        score_rank = game_data.get('score_rank', '')
        if isinstance(score_rank, (int, float)):
            score_rank = str(score_rank)
        elif score_rank is None:
            score_rank = ''

        return SteamSpyGame(
            appid=int(game_data.get('appid', 0)),
            name=game_data.get('name', ''),
            developer=game_data.get('developer', ''),
            publisher=game_data.get('publisher', ''),
            score_rank=score_rank,
            positive=int(game_data.get('positive', 0)),
            negative=int(game_data.get('negative', 0)),
            owners=game_data.get('owners', ''),
            average_forever=int(game_data.get('average_forever', 0))
        )

    def save_games_batch(self, games: list[SteamSpyGame]) -> int:
        """Save a batch of games to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Prepare batch data
        batch_data = [
            (game.appid, game.name, game.developer, game.publisher,
             game.score_rank, game.positive, game.negative,
             game.owners, game.average_forever)
            for game in games
        ]

        # Insert with transaction
        try:
            cursor.executemany("""
            INSERT OR REPLACE INTO all_games
            (appid, name, developer, publisher, score_rank, positive, negative, owners, average_forever)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch_data)

            conn.commit()
            saved_count = len(batch_data)
            logger.info(f"Saved {saved_count} games to database")
            return saved_count

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()

    def collect_all_games(self) -> int:
        """Main collection function - fetches all games from SteamSpy"""
        logger.info(f"Starting SteamSpy collection (target: {self.max_games} games)")

        # Create database
        self.create_database()

        total_saved = 0
        page = 0

        while total_saved < self.max_games:
            logger.info(f"Fetching page {page}...")

            # Fetch page data
            game_map = self.fetch_steamspy_page(page)
            if not game_map:
                logger.warning(f"No data received for page {page}, stopping")
                break

            if len(game_map) == 0:
                logger.info(f"No more games on page {page}, stopping")
                break

            # Parse games
            games = []
            for game_id, game_data in game_map.items():
                if total_saved >= self.max_games:
                    break

                try:
                    game = self.parse_game_data(game_data)
                    games.append(game)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Error parsing game {game_id}: {e}")
                    continue

            # Save batch
            if games:
                saved_count = self.save_games_batch(games)
                total_saved += saved_count
                logger.info(f"Page {page} complete. Total saved: {total_saved}")

            # Rate limiting
            page += 1
            time.sleep(1)  # Be nice to the API

        logger.info(f"Collection complete! Total games saved: {total_saved}")
        return total_saved

def create_steamspy_database() -> int:
    """Main function to create SteamSpy database"""
    collector = SteamSpyCollector()
    return collector.collect_all_games()

if __name__ == "__main__":
    # Check if user wants to proceed
    response = input("WARNING: Database creation takes ~1 hour due to API rate limits. Continue? (y/n): ")
    if response.lower().strip() == 'y':
        total_games = create_steamspy_database()
        print(f"✅ SteamSpy collection complete: {total_games} games")
    else:
        print("Operation cancelled")