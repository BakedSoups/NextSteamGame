"""
Game Collector - Fetches game data from Steam APIs and stores in SQLite
Uses SQLModel (SQLAlchemy + Pydantic) and Tenacity for retry logic
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime
import requests
from sqlmodel import SQLModel, Field, Session, create_engine, select
from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

# Import from parent package
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from steam_review_analyzer import SteamReviewAnalyzer

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============== SQLModel Tables ==============

class Game(SQLModel, table=True):
    """Game record - works as both DB table and Pydantic model"""
    __tablename__ = "games"

    appid: int = Field(primary_key=True)
    name: str
    owners: str = "0"
    positive_reviews: int = 0
    negative_reviews: int = 0
    insightful_reviews: Optional[str] = None
    sentiment_score: float = 0.0
    key_themes: str = "[]"  # JSON string
    processed_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    @property
    def themes_list(self) -> List[str]:
        """Get key_themes as a list"""
        try:pu
            return json.loads(self.key_themes)
        except json.JSONDecodeError:
            return []

    @themes_list.setter
    def themes_list(self, value: List[str]):
        """Set key_themes from a list"""
        self.key_themes = json.dumps(value)


# ============== Pydantic Models (non-DB) ==============

class CollectorStats(BaseModel):
    """Statistics from a collection run"""
    total_games: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0


class SteamSpyGame(BaseModel):
    """Raw game data from SteamSpy API"""
    appid: int
    name: str
    owners: str = "0"
    positive: int = 0
    negative: int = 0

    class Config:
        extra = "ignore"  # Ignore extra fields from API


# ============== Retry-enabled HTTP fetcher ==============

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    retry=retry_if_exception_type((
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.HTTPError,
    )),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def fetch_with_retry(url: str, params: Optional[Dict] = None, timeout: int = 15) -> requests.Response:
    """Fetch URL with automatic retry on failure"""
    response = requests.get(url, params=params, timeout=timeout)

    if response.status_code >= 500:
        response.raise_for_status()

    if response.status_code == 429:
        raise requests.exceptions.HTTPError("Rate limited", response=response)

    return response


# ============== Main Collector Class ==============

class GameCollector:
    """Collects game data from SteamSpy and Steam APIs, stores in SQLite"""

    STEAMSPY_API = "https://steamspy.com/api.php"

    def __init__(self, db_path: str = "steam_games.db"):
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.analyzer = SteamReviewAnalyzer()

    def _init_db(self):
        """Initialize database schema"""
        SQLModel.metadata.drop_all(self.engine)
        SQLModel.metadata.create_all(self.engine)

    def build_games_database(self, max_games: int = 1000) -> CollectorStats:
        """
        Build SQLite database with Steam games and their insightful reviews

        Args:
            max_games: Maximum number of games to process

        Returns:
            CollectorStats with results summary
        """
        stats = CollectorStats(total_games=max_games)
        logger.info(f"Building database with up to {max_games} games...")

        self._init_db()

        # Fetch games from SteamSpy
        games = self._fetch_popular_games(max_games)
        logger.info(f"Fetched {len(games)} games from SteamSpy")
        stats.total_games = len(games)

        with Session(self.engine) as session:
            for i, steamspy_game in enumerate(games, 1):
                if i > max_games:
                    break

                logger.info(f"Processing {i}/{min(len(games), max_games)}: {steamspy_game.name}")

                try:
                    # Get insightful reviews
                    reviews_text = self.analyzer.pull_insightful_reviews(steamspy_game.appid)
                    insights = self.analyzer.get_review_insights(steamspy_game.appid)

                    # Create Game model (works for both validation and DB insert)
                    game = Game(
                        appid=steamspy_game.appid,
                        name=steamspy_game.name,
                        owners=steamspy_game.owners,
                        positive_reviews=steamspy_game.positive,
                        negative_reviews=steamspy_game.negative,
                        insightful_reviews=reviews_text,
                        sentiment_score=insights.get("average_sentiment", 0),
                        key_themes=json.dumps(insights.get("key_themes", [])),
                    )

                    session.add(game)
                    session.commit()
                    stats.successful += 1

                except Exception as e:
                    logger.error(f"Error processing game {steamspy_game.appid}: {e}")
                    session.rollback()
                    stats.failed += 1

                if i % 10 == 0:
                    logger.info(f"Checkpoint: {i} games (success: {stats.successful}, failed: {stats.failed})")

        logger.info(f"Database built: {self.db_path}")
        logger.info(f"Stats: {stats.successful} successful, {stats.failed} failed")
        return stats

    def get_game(self, appid: int) -> Optional[Game]:
        """Get a game by appid"""
        with Session(self.engine) as session:
            return session.get(Game, appid)

    def get_all_games(self) -> List[Game]:
        """Get all games from database"""
        with Session(self.engine) as session:
            return session.exec(select(Game)).all()

    def _fetch_popular_games(self, limit: int) -> List[SteamSpyGame]:
        """Fetch popular games from SteamSpy with retry logic"""
        games = []

        try:
            # Get top 100 games
            response = fetch_with_retry(
                self.STEAMSPY_API,
                params={"request": "top100in2weeks"}
            )
            data = response.json()

            for appid, game_data in data.items():
                try:
                    games.append(SteamSpyGame(appid=int(appid), **game_data))
                except Exception:
                    continue

            # If we need more, get all games
            if len(games) < limit:
                response = fetch_with_retry(
                    self.STEAMSPY_API,
                    params={"request": "all", "page": "0"}
                )
                data = response.json()

                for appid, game_data in data.items():
                    if len(games) >= limit:
                        break
                    try:
                        game = SteamSpyGame(appid=int(appid), **game_data)
                        if game.appid not in [g.appid for g in games]:
                            games.append(game)
                    except Exception:
                        continue

        except Exception as e:
            logger.error(f"Error fetching games from SteamSpy: {e}")

        return games[:limit]


# ============== Convenience Functions ==============

def build_steam_database(max_games: int = 100) -> CollectorStats:
    """Build a Steam games database with insightful reviews"""
    return GameCollector().build_games_database(max_games)


def get_reviews_for_game(appid: int) -> str:
    """Get insightful reviews for a specific game"""
    return SteamReviewAnalyzer().pull_insightful_reviews(appid)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "build":
            max_games = int(sys.argv[2]) if len(sys.argv) > 2 else 100
            stats = build_steam_database(max_games)
            print(f"\nFinal stats: {stats.model_dump_json(indent=2)}")

        elif command == "review":
            if len(sys.argv) > 2:
                appid = int(sys.argv[2])
                reviews = get_reviews_for_game(appid)
                print(f"Reviews for {appid}:")
                print(reviews)
            else:
                print("Usage: python game_collector.py review <appid>")

        elif command == "get":
            if len(sys.argv) > 2:
                appid = int(sys.argv[2])
                collector = GameCollector()
                game = collector.get_game(appid)
                if game:
                    print(game.model_dump_json(indent=2))
                else:
                    print(f"Game {appid} not found")
            else:
                print("Usage: python game_collector.py get <appid>")

        else:
            print("Unknown command:", command)
    else:
        print("Usage:")
        print("  python game_collector.py build [max_games]  # Build database")
        print("  python game_collector.py review <appid>     # Get reviews for game")
        print("  python game_collector.py get <appid>        # Get game from DB")
