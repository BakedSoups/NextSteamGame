import sqlite3
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database initialization and migration tasks"""

    def __init__(self, db_path: str = "./steam_api.db"):
        self.db_path = db_path

    def create_review_tables(self) -> None:
        """Create tables for storing review data from IGN, ACG, and GameRanx"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Create IGN scores table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ign_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            steam_appid INTEGER NOT NULL,
            game_name TEXT,
            ign_score REAL,
            ign_review_text TEXT,
            ign_url TEXT,
            review_date TEXT,
            FOREIGN KEY(steam_appid) REFERENCES main_game(steam_appid) ON DELETE CASCADE
        );
        """)

        # Create ACG scores table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ACG_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            steam_appid INTEGER NOT NULL,
            game_name TEXT,
            acg_verdict TEXT,
            acg_review_summary TEXT,
            video_url TEXT,
            review_date TEXT,
            FOREIGN KEY(steam_appid) REFERENCES main_game(steam_appid) ON DELETE CASCADE
        );
        """)

        # Create GameRanx scores table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS GameRanx_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            steam_appid INTEGER NOT NULL,
            game_name TEXT,
            gameranx_score REAL,
            gameranx_review_text TEXT,
            gameranx_url TEXT,
            review_date TEXT,
            FOREIGN KEY(steam_appid) REFERENCES main_game(steam_appid) ON DELETE CASCADE
        );
        """)

        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ign_appid ON ign_scores(steam_appid);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_acg_appid ON ACG_scores(steam_appid);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gameranx_appid ON GameRanx_scores(steam_appid);")

        conn.commit()
        conn.close()
        logger.info("Created review tables")

    def migrate_steam_reviews(self, json_file: str = "checkpoint_steam_analysis.json") -> int:
        """Migrate Steam review analysis data from JSON to database"""
        if not Path(json_file).exists():
            logger.warning(f"Steam reviews JSON file not found: {json_file}")
            return 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create steam_review_analysis table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS steam_review_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            steam_appid INTEGER NOT NULL,
            game_name TEXT,
            main_genre TEXT,
            unique_tags TEXT,  -- JSON array
            subjective_tags TEXT,  -- JSON array
            tag_ratios TEXT,  -- JSON object
            analysis_date TEXT,
            FOREIGN KEY(steam_appid) REFERENCES main_game(steam_appid) ON DELETE CASCADE
        );
        """)

        # Load JSON data
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading JSON file: {e}")
            return 0

        migrated_count = 0
        for appid_str, game_data in analysis_data.items():
            try:
                appid = int(appid_str)

                # Insert analysis data
                cursor.execute("""
                INSERT OR REPLACE INTO steam_review_analysis
                (steam_appid, game_name, main_genre, unique_tags, subjective_tags, tag_ratios, analysis_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    appid,
                    game_data.get('game_name', ''),
                    game_data.get('main_genre', ''),
                    json.dumps(game_data.get('unique_tags', [])),
                    json.dumps(game_data.get('subjective_tags', [])),
                    json.dumps(game_data.get('tag_ratios', {})),
                    game_data.get('analysis_date', '')
                ))

                migrated_count += 1

            except (ValueError, sqlite3.Error) as e:
                logger.warning(f"Error migrating analysis for app {appid_str}: {e}")
                continue

        conn.commit()
        conn.close()
        logger.info(f"Migrated {migrated_count} steam review analyses")
        return migrated_count

    def migrate_ign_data(self, json_file: str = "ign_all_games.json") -> int:
        """Migrate IGN review data from JSON to database"""
        if not Path(json_file).exists():
            logger.warning(f"IGN JSON file not found: {json_file}")
            return 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Load JSON data
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                ign_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading IGN JSON file: {e}")
            return 0

        migrated_count = 0
        for game in ign_data:
            try:
                # Try to match game by name to get steam_appid
                game_name = game.get('name', '').strip()
                if not game_name:
                    continue

                # Find matching steam_appid
                cursor.execute(
                    "SELECT steam_appid FROM main_game WHERE LOWER(game_name) LIKE LOWER(?)",
                    (f"%{game_name}%",)
                )
                match = cursor.fetchone()

                if not match:
                    logger.debug(f"No Steam match found for IGN game: {game_name}")
                    continue

                steam_appid = match[0]

                # Extract score from IGN data
                score_text = game.get('score', '')
                score = None
                if score_text:
                    try:
                        # Extract numeric score (e.g., "8.5/10" -> 8.5)
                        if '/' in score_text:
                            score = float(score_text.split('/')[0])
                        else:
                            score = float(score_text)
                    except ValueError:
                        pass

                # Insert IGN data
                cursor.execute("""
                INSERT OR REPLACE INTO ign_scores
                (steam_appid, game_name, ign_score, ign_review_text, ign_url, review_date)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    steam_appid,
                    game_name,
                    score,
                    game.get('review_text', ''),
                    game.get('url', ''),
                    game.get('date', '')
                ))

                migrated_count += 1

            except (ValueError, sqlite3.Error) as e:
                logger.warning(f"Error migrating IGN data for {game.get('name', 'unknown')}: {e}")
                continue

        conn.commit()
        conn.close()
        logger.info(f"Migrated {migrated_count} IGN reviews")
        return migrated_count

    def create_indexes(self) -> None:
        """Create performance indexes on all tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_main_game_appid ON main_game(steam_appid);",
            "CREATE INDEX IF NOT EXISTS idx_main_game_name ON main_game(game_name);",
            "CREATE INDEX IF NOT EXISTS idx_steam_spy_appid ON steam_spy(steam_appid);",
            "CREATE INDEX IF NOT EXISTS idx_steam_api_appid ON steam_api(steam_appid);",
            "CREATE INDEX IF NOT EXISTS idx_genres_appid ON genres(steam_appid);",
            "CREATE INDEX IF NOT EXISTS idx_genres_genre ON genres(genre);",
            "CREATE INDEX IF NOT EXISTS idx_steam_analysis_appid ON steam_review_analysis(steam_appid);",
            "CREATE INDEX IF NOT EXISTS idx_steam_analysis_genre ON steam_review_analysis(main_genre);"
        ]

        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
                logger.debug(f"Created index: {index_sql.split()[-1]}")
            except sqlite3.Error as e:
                logger.warning(f"Error creating index: {e}")

        conn.commit()
        conn.close()
        logger.info("Created performance indexes")

    def get_database_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # Table counts
        tables = ['main_game', 'steam_spy', 'steam_api', 'genres',
                 'ign_scores', 'ACG_scores', 'GameRanx_scores', 'steam_review_analysis']

        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[f"{table}_count"] = cursor.fetchone()[0]
            except sqlite3.Error:
                stats[f"{table}_count"] = 0

        # Genre distribution
        try:
            cursor.execute("""
            SELECT genre, COUNT(*) as count
            FROM genres
            GROUP BY genre
            ORDER BY count DESC
            LIMIT 10
            """)
            stats['top_genres'] = cursor.fetchall()
        except sqlite3.Error:
            stats['top_genres'] = []

        # Database size
        try:
            cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            stats['database_size_bytes'] = cursor.fetchone()[0]
        except sqlite3.Error:
            stats['database_size_bytes'] = 0

        conn.close()
        return stats

    def print_database_summary(self) -> None:
        """Print a comprehensive database summary"""
        stats = self.get_database_stats()

        print("\n" + "="*60)
        print("STEAM GAME DATABASE SUMMARY")
        print("="*60)

        print(f"\n📊 TABLE COUNTS:")
        print(f"   Main Games: {stats.get('main_game_count', 0):,}")
        print(f"   Steam Spy Data: {stats.get('steam_spy_count', 0):,}")
        print(f"   Steam API Data: {stats.get('steam_api_count', 0):,}")
        print(f"   Genres: {stats.get('genres_count', 0):,}")
        print(f"   IGN Reviews: {stats.get('ign_scores_count', 0):,}")
        print(f"   ACG Reviews: {stats.get('ACG_scores_count', 0):,}")
        print(f"   GameRanx Reviews: {stats.get('GameRanx_scores_count', 0):,}")
        print(f"   Review Analysis: {stats.get('steam_review_analysis_count', 0):,}")

        print(f"\n🎮 TOP GENRES:")
        for genre, count in stats.get('top_genres', [])[:10]:
            print(f"   {count:4d} - {genre}")

        size_mb = stats.get('database_size_bytes', 0) / (1024 * 1024)
        print(f"\n💾 DATABASE SIZE: {size_mb:.1f} MB")
        print("="*60)

def initialize_database():
    """Complete database initialization workflow"""
    logger.info("Starting database initialization")

    db_manager = DatabaseManager()

    # Create review tables
    db_manager.create_review_tables()

    # Migrate data
    steam_migrated = db_manager.migrate_steam_reviews()
    ign_migrated = db_manager.migrate_ign_data()

    # Create indexes
    db_manager.create_indexes()

    # Print summary
    db_manager.print_database_summary()

    logger.info(f"Database initialization complete: {steam_migrated} steam reviews, {ign_migrated} IGN reviews")

if __name__ == "__main__":
    initialize_database()