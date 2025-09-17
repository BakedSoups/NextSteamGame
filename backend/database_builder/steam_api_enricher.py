import requests
import sqlite3
import time
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class SteamGameData:
    """Data class for Steam API game data"""
    appid: int
    genre: str
    description: str
    website: str
    header_image: str
    background: str
    screenshot: str
    steam_url: str
    pricing: str
    achievements: str

class SteamAPIEnricher:
    """Enriches game data with Steam Store API information"""

    def __init__(self, source_db: str = "./steamspy_all_games.db",
                 target_db: str = "./steam_api.db"):
        self.source_db = source_db
        self.target_db = target_db
        self.max_retries = 3
        self.base_delay = 5

    def fetch_steam_app_details(self, appid: int) -> Optional[SteamGameData]:
        """Fetch detailed game information from Steam Store API"""
        url = f"https://store.steampowered.com/api/appdetails?appids={appid}"

        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, timeout=15)

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After', str(self.base_delay * (2 ** attempt)))
                    wait_time = int(retry_after) if retry_after.isdigit() else self.base_delay * (2 ** attempt)
                    logger.warning(f"Rate limited for app {appid}. Waiting {wait_time}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                    continue

                if response.status_code != 200:
                    logger.warning(f"Bad status {response.status_code} for app {appid}")
                    return None

                # Check if response is HTML (error page)
                if response.text.strip().startswith('<'):
                    logger.warning(f"Got HTML response for app {appid} (likely rate limited or invalid ID)")
                    time.sleep(5)  # Brief pause before retry
                    continue

                data = response.json()

                # Check if API call was successful
                app_data = data.get(str(appid))
                if not app_data or not app_data.get('success', False):
                    logger.warning(f"API returned success=false for app {appid}")
                    return None

                return self._parse_steam_data(appid, app_data['data'])

            except requests.exceptions.RequestException as e:
                logger.error(f"Request error for app {appid}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.base_delay * (2 ** attempt))
                    continue
                return None
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for app {appid}: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error for app {appid}: {e}")
                return None

        logger.error(f"Max retries exceeded for app {appid}")
        return None

    def _parse_steam_data(self, appid: int, data: Dict[str, Any]) -> SteamGameData:
        """Parse Steam API response data"""
        # Extract genres
        genres = data.get('genres', [])
        genre_list = [g.get('description', '') for g in genres if isinstance(g, dict)]
        genre = ', '.join(genre_list)

        # Extract screenshots
        screenshots = data.get('screenshots', [])
        screenshot = screenshots[0].get('path_full', '') if screenshots else ''

        # Extract pricing
        price_overview = data.get('price_overview', {})
        pricing = price_overview.get('final_formatted', '') if price_overview else ''

        # Extract achievements
        achievements = data.get('achievements', {})
        achievement_count = achievements.get('total', 0) if achievements else 0
        achievements_text = f"{achievement_count} achievements" if achievement_count > 0 else "0 achievements"

        return SteamGameData(
            appid=appid,
            genre=genre,
            description=data.get('short_description', ''),
            website=data.get('website', ''),
            header_image=data.get('header_image', ''),
            background=data.get('background', ''),
            screenshot=screenshot,
            steam_url=f"https://store.steampowered.com/app/{appid}",
            pricing=pricing,
            achievements=achievements_text
        )

    def create_target_database(self) -> None:
        """Create the target database schema"""
        conn = sqlite3.connect(self.target_db)
        cursor = conn.cursor()

        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Create main_game table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS main_game (
            game_id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_name TEXT,
            steam_appid INTEGER NOT NULL UNIQUE
        );
        """)

        # Create steam_spy table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS steam_spy (
            game_id INTEGER PRIMARY KEY AUTOINCREMENT,
            steam_appid INTEGER NOT NULL,
            positive_reviews INTEGER,
            negative_reviews INTEGER,
            owners INTEGER,
            FOREIGN KEY(steam_appid) REFERENCES main_game(steam_appid) ON DELETE CASCADE
        );
        """)

        # Create genres table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS genres (
            steam_appid INTEGER NOT NULL,
            genre TEXT NOT NULL,
            PRIMARY KEY (steam_appid, genre),
            FOREIGN KEY(steam_appid) REFERENCES main_game(steam_appid) ON DELETE CASCADE
        );
        """)

        # Create steam_api table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS steam_api (
            detail_id INTEGER PRIMARY KEY AUTOINCREMENT,
            steam_appid INTEGER NOT NULL,
            description TEXT,
            website TEXT,
            header_image TEXT,
            background TEXT,
            screenshot TEXT,
            steam_url TEXT,
            pricing TEXT,
            achievements TEXT,
            FOREIGN KEY(steam_appid) REFERENCES main_game(steam_appid) ON DELETE CASCADE
        );
        """)

        conn.commit()
        conn.close()
        logger.info(f"Created target database schema at {self.target_db}")

    def migrate_steamspy_data(self) -> int:
        """Migrate SteamSpy data to target database"""
        source_conn = sqlite3.connect(self.source_db)
        target_conn = sqlite3.connect(self.target_db)

        source_cursor = source_conn.cursor()
        target_cursor = target_conn.cursor()

        # Fetch all games from source
        source_cursor.execute("SELECT appid, name, positive, negative, owners FROM all_games")
        games = source_cursor.fetchall()

        migrated_count = 0
        for appid, name, positive, negative, owners in games:
            try:
                # Insert into main_game
                target_cursor.execute(
                    "INSERT OR IGNORE INTO main_game (game_name, steam_appid) VALUES (?, ?)",
                    (name, appid)
                )

                # Parse owners string to integer (e.g., "0 .. 20,000" -> 10000)
                owners_int = self._parse_owners(owners)

                # Insert into steam_spy
                target_cursor.execute("""
                INSERT OR IGNORE INTO steam_spy (steam_appid, positive_reviews, negative_reviews, owners)
                VALUES (?, ?, ?, ?)
                """, (appid, positive, negative, owners_int))

                migrated_count += 1

            except sqlite3.Error as e:
                logger.warning(f"Error migrating game {appid}: {e}")
                continue

        target_conn.commit()
        source_conn.close()
        target_conn.close()

        logger.info(f"Migrated {migrated_count} games from SteamSpy data")
        return migrated_count

    def _parse_owners(self, owners_str: str) -> int:
        """Parse owners string to approximate integer"""
        if not owners_str or owners_str == '0':
            return 0

        # Handle ranges like "0 .. 20,000" or "100,000 .. 200,000"
        if '..' in owners_str:
            parts = owners_str.split('..')
            if len(parts) == 2:
                try:
                    # Take the upper bound and remove commas
                    upper = parts[1].strip().replace(',', '')
                    return int(upper)
                except ValueError:
                    pass

        # Try to extract first number
        try:
            return int(owners_str.replace(',', ''))
        except ValueError:
            return 0

    def load_processed_apps(self, filename: str = "./processed_apps.txt") -> set:
        """Load list of already processed app IDs"""
        try:
            with open(filename, 'r') as f:
                return set(int(line.strip()) for line in f if line.strip().isdigit())
        except FileNotFoundError:
            return set()

    def save_processed_app(self, appid: int, filename: str = "./processed_apps.txt") -> None:
        """Save processed app ID to file"""
        with open(filename, 'a') as f:
            f.write(f"{appid}\n")

    def enrich_all_games(self, batch_size: int = 10) -> int:
        """Enrich all games with Steam API data"""
        logger.info("Starting Steam API enrichment process")

        # Load processed apps
        processed_apps = self.load_processed_apps()
        logger.info(f"Skipping {len(processed_apps)} already processed games")

        # Get app IDs to process
        conn = sqlite3.connect(self.target_db)
        cursor = conn.cursor()
        cursor.execute("SELECT steam_appid FROM main_game ORDER BY steam_appid")
        app_ids = [row[0] for row in cursor.fetchall() if row[0] not in processed_apps]
        conn.close()

        logger.info(f"Found {len(app_ids)} games to enrich")

        enriched_count = 0
        for i, appid in enumerate(app_ids):
            logger.info(f"Processing app {appid} ({i+1}/{len(app_ids)})")

            # Fetch Steam data
            steam_data = self.fetch_steam_app_details(appid)
            if steam_data:
                # Save to database
                if self._save_steam_data(steam_data):
                    enriched_count += 1

                # Save progress
                self.save_processed_app(appid)

            # Batch delay
            if (i + 1) % batch_size == 0:
                logger.info(f"Batch complete. Waiting 10 seconds...")
                time.sleep(10)

        logger.info(f"Enrichment complete! Processed {enriched_count} games")
        return enriched_count

    def _save_steam_data(self, steam_data: SteamGameData) -> bool:
        """Save Steam API data to database"""
        conn = sqlite3.connect(self.target_db)
        cursor = conn.cursor()

        try:
            # Insert into steam_api table
            cursor.execute("""
            INSERT OR REPLACE INTO steam_api
            (steam_appid, description, website, header_image, background, screenshot, steam_url, pricing, achievements)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                steam_data.appid, steam_data.description, steam_data.website,
                steam_data.header_image, steam_data.background, steam_data.screenshot,
                steam_data.steam_url, steam_data.pricing, steam_data.achievements
            ))

            # Insert genres
            if steam_data.genre:
                # Clear existing genres
                cursor.execute("DELETE FROM genres WHERE steam_appid = ?", (steam_data.appid,))

                # Insert new genres
                for genre in steam_data.genre.split(', '):
                    if genre.strip():
                        cursor.execute(
                            "INSERT INTO genres (steam_appid, genre) VALUES (?, ?)",
                            (steam_data.appid, genre.strip())
                        )

            conn.commit()
            return True

        except sqlite3.Error as e:
            logger.error(f"Database error saving app {steam_data.appid}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

def create_enriched_database():
    """Main function to create enriched Steam database"""
    enricher = SteamAPIEnricher()

    # Create target database
    enricher.create_target_database()

    # Migrate SteamSpy data
    migrated = enricher.migrate_steamspy_data()
    logger.info(f"Migration complete: {migrated} games")

    # Enrich with Steam API data
    enriched = enricher.enrich_all_games()
    logger.info(f"Enrichment complete: {enriched} games")

    return enriched

if __name__ == "__main__":
    create_enriched_database()