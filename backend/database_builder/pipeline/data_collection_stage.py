"""
Data Collection Stage - Collects raw game data from SteamSpy and Steam API
"""
import logging
from typing import Optional, List
from pathlib import Path

from .base_stage import BasePipelineStage, StageResult, StageCheckpoint
from ..steamspy_collector import SteamSpyCollector
from ..steam_api_enricher import SteamAPIEnricher
from backend.config import DATABASE_CONFIG, DATA_COLLECTION


class DataCollectionStage(BasePipelineStage):
    """Stage 1: Data Collection from SteamSpy and Steam API"""

    def __init__(self):
        super().__init__(
            stage_name="data_collection",
            dependencies=[]  # No dependencies - this is the first stage
        )

        self.steamspy_collector = SteamSpyCollector(
            db_path=str(DATABASE_CONFIG['steamspy_db'])
        )
        self.steam_api_enricher = SteamAPIEnricher(
            source_db=str(DATABASE_CONFIG['steamspy_db']),
            target_db=str(DATABASE_CONFIG['steam_api_db'])
        )

    def _execute_stage(self, checkpoint: Optional[StageCheckpoint]) -> StageResult:
        """Execute data collection stage"""
        self.logger.info("🚀 Starting data collection from SteamSpy and Steam API")

        total_processed = 0
        output_files = []
        stage_metadata = {}

        try:
            # Sub-stage 1: SteamSpy Collection
            if not self._is_steamspy_complete():
                self.logger.info("📦 Collecting SteamSpy game catalog...")
                steamspy_count = self._collect_steamspy_data()
                total_processed += steamspy_count
                stage_metadata['steamspy_games'] = steamspy_count
                self.logger.info(f"✅ SteamSpy collection complete: {steamspy_count} games")
            else:
                self.logger.info("✅ SteamSpy data already exists, skipping collection")
                stage_metadata['steamspy_games'] = self._count_steamspy_games()

            # Sub-stage 2: Steam API Enrichment
            if not self._is_steam_api_complete():
                self.logger.info("🎮 Enriching with Steam Store API data...")
                enriched_count = self._enrich_with_steam_api()
                total_processed += enriched_count
                stage_metadata['enriched_games'] = enriched_count
                self.logger.info(f"✅ Steam API enrichment complete: {enriched_count} games")
            else:
                self.logger.info("✅ Steam API data already exists, skipping enrichment")
                stage_metadata['enriched_games'] = self._count_enriched_games()

            # Add output files
            output_files = [
                str(DATABASE_CONFIG['steamspy_db']),
                str(DATABASE_CONFIG['steam_api_db'])
            ]

            self.logger.info("✨ Data collection stage complete")
            return StageResult(
                success=True,
                stage_name=self.stage_name,
                duration=self.start_time,
                items_processed=total_processed,
                output_files=output_files,
                metadata=stage_metadata
            )

        except Exception as e:
            self.logger.error(f"Data collection failed: {e}")
            raise

    def _collect_steamspy_data(self) -> int:
        """Collect data from SteamSpy API"""
        # Set max games from configuration
        self.steamspy_collector.max_games = DATA_COLLECTION['max_games']
        return self.steamspy_collector.collect_all_games()

    def _enrich_with_steam_api(self) -> int:
        """Enrich data with Steam Store API"""
        # Create target database schema
        self.steam_api_enricher.create_target_database()

        # Migrate SteamSpy data
        migrated = self.steam_api_enricher.migrate_steamspy_data()
        self.logger.info(f"Migrated {migrated} games from SteamSpy")

        # Enrich with Steam API data
        batch_size = DATA_COLLECTION.get('batch_size', 1000) // 100  # Smaller batches for API
        enriched = self.steam_api_enricher.enrich_all_games(batch_size=batch_size)

        return enriched

    def _is_steamspy_complete(self) -> bool:
        """Check if SteamSpy collection is complete"""
        db_path = DATABASE_CONFIG['steamspy_db']
        if not Path(db_path).exists():
            return False

        # Check if database has reasonable number of games
        import sqlite3
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM all_games")
            count = cursor.fetchone()[0]
            conn.close()

            # Consider complete if we have at least 80% of target games
            min_required = int(DATA_COLLECTION['max_games'] * 0.8)
            return count >= min_required
        except Exception:
            return False

    def _is_steam_api_complete(self) -> bool:
        """Check if Steam API enrichment is complete"""
        db_path = DATABASE_CONFIG['steam_api_db']
        if not Path(db_path).exists():
            return False

        # Check if database has reasonable number of enriched games
        import sqlite3
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM steam_api")
            count = cursor.fetchone()[0]
            conn.close()

            # Consider complete if we have at least 50% enriched
            # (Steam API often fails for many games)
            min_required = int(DATA_COLLECTION['max_games'] * 0.5)
            return count >= min_required
        except Exception:
            return False

    def _count_steamspy_games(self) -> int:
        """Count existing SteamSpy games"""
        import sqlite3
        try:
            conn = sqlite3.connect(str(DATABASE_CONFIG['steamspy_db']))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM all_games")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    def _count_enriched_games(self) -> int:
        """Count existing enriched games"""
        import sqlite3
        try:
            conn = sqlite3.connect(str(DATABASE_CONFIG['steam_api_db']))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM steam_api")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    def _get_expected_outputs(self) -> List[str]:
        """Return list of expected output files"""
        return [
            str(DATABASE_CONFIG['steamspy_db']),
            str(DATABASE_CONFIG['steam_api_db'])
        ]

    def _validate_stage_inputs(self) -> bool:
        """Validate that stage inputs are available"""
        # This stage has no inputs - it fetches from APIs
        return True

    def get_collection_stats(self) -> dict:
        """Get detailed collection statistics"""
        stats = {
            'steamspy_games': self._count_steamspy_games(),
            'enriched_games': self._count_enriched_games(),
            'target_games': DATA_COLLECTION['max_games'],
            'steamspy_complete': self._is_steamspy_complete(),
            'steam_api_complete': self._is_steam_api_complete()
        }

        # Calculate completion percentages
        if stats['target_games'] > 0:
            stats['steamspy_completion_pct'] = (stats['steamspy_games'] / stats['target_games']) * 100
            stats['enrichment_completion_pct'] = (stats['enriched_games'] / stats['target_games']) * 100

        return stats