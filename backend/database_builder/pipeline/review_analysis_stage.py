"""
Review Analysis Stage - Analyzes Steam reviews and scrapes professional reviews
"""
import logging
import subprocess
import sys
from typing import Optional, List
from pathlib import Path

from .base_stage import BasePipelineStage, StageResult, StageCheckpoint, BatchProcessingMixin
from backend.config import DATABASE_CONFIG, PIPELINE_PATHS, API_CONFIG


class ReviewAnalysisStage(BasePipelineStage, BatchProcessingMixin):
    """Stage 2: Review Analysis from Steam and professional sources"""

    def __init__(self):
        super().__init__(
            stage_name="review_analysis",
            dependencies=["data_collection"]
        )

    def _execute_stage(self, checkpoint: Optional[StageCheckpoint]) -> StageResult:
        """Execute review analysis stage"""
        self.logger.info("🔍 Starting review analysis from multiple sources")

        # Validate OpenAI API key is available
        if not API_CONFIG['openai_api_key']:
            raise ValueError("OpenAI API key not configured - required for review analysis")

        total_processed = 0
        output_files = []
        stage_metadata = {}

        try:
            # Sub-stage 1: Steam Review Analysis
            if not self._is_steam_analysis_complete():
                self.logger.info("💬 Analyzing Steam reviews with OpenAI...")
                steam_count = self._analyze_steam_reviews()
                total_processed += steam_count
                stage_metadata['steam_reviews_analyzed'] = steam_count
                self.logger.info(f"✅ Steam review analysis complete: {steam_count} games")
            else:
                self.logger.info("✅ Steam review analysis already complete, skipping")
                stage_metadata['steam_reviews_analyzed'] = self._count_analyzed_games()

            # Sub-stage 2: IGN Review Scraping (optional)
            if self._should_scrape_ign():
                self.logger.info("📰 Scraping IGN professional reviews...")
                ign_count = self._scrape_ign_reviews()
                total_processed += ign_count
                stage_metadata['ign_reviews_scraped'] = ign_count
                self.logger.info(f"✅ IGN scraping complete: {ign_count} reviews")
            else:
                self.logger.info("✅ IGN review data exists, skipping scraping")
                stage_metadata['ign_reviews_scraped'] = self._count_ign_reviews()

            # Sub-stage 3: Verdict Extraction and Hierarchical Classification
            if not self._is_verdict_extraction_complete():
                self.logger.info("🏷️ Extracting verdicts and hierarchical classification...")
                verdict_count = self._extract_verdicts()
                total_processed += verdict_count
                stage_metadata['verdicts_extracted'] = verdict_count
                self.logger.info(f"✅ Verdict extraction complete: {verdict_count} games")
            else:
                self.logger.info("✅ Verdict extraction already complete, skipping")
                stage_metadata['verdicts_extracted'] = self._count_hierarchical_games()

            # Add output files
            output_files = [
                str(PIPELINE_PATHS['checkpoint_file']),
                str(PIPELINE_PATHS['ign_data_file']),
                str(PIPELINE_PATHS['hierarchical_tags_file'])
            ]

            self.logger.info("✨ Review analysis stage complete")
            return StageResult(
                success=True,
                stage_name=self.stage_name,
                duration=self.start_time,
                items_processed=total_processed,
                output_files=output_files,
                metadata=stage_metadata
            )

        except Exception as e:
            self.logger.error(f"Review analysis failed: {e}")
            raise

    def _analyze_steam_reviews(self) -> int:
        """Run Steam review analysis with OpenAI"""
        try:
            # Import and run the steam reviews extractor
            from backend.database_builder.tag_builder.steam_reviews_extractor import main as extract_steam_reviews
            return extract_steam_reviews()
        except Exception as e:
            self.logger.error(f"Steam review analysis failed: {e}")
            raise

    def _scrape_ign_reviews(self) -> int:
        """Scrape IGN professional reviews"""
        try:
            # Import and run the IGN scraper
            from backend.database_builder.tag_builder.ign_scrape import main as scrape_ign_reviews
            return scrape_ign_reviews()
        except Exception as e:
            self.logger.error(f"IGN scraping failed: {e}")
            # IGN scraping is optional, so don't fail the entire stage
            self.logger.warning("IGN scraping failed, continuing without professional reviews")
            return 0

    def _extract_verdicts(self) -> int:
        """Extract verdicts and create hierarchical classification"""
        try:
            # Import and run the verdict extractor
            from backend.database_builder.tag_builder.extract_verdicts import main as extract_verdicts
            return extract_verdicts()
        except Exception as e:
            self.logger.error(f"Verdict extraction failed: {e}")
            raise

    def _should_scrape_ign(self) -> bool:
        """Check if IGN scraping should be performed"""
        ign_file = PIPELINE_PATHS['ign_data_file']
        return not ign_file.exists()

    def _is_steam_analysis_complete(self) -> bool:
        """Check if Steam review analysis is complete"""
        checkpoint_file = PIPELINE_PATHS['checkpoint_file']
        if not checkpoint_file.exists():
            return False

        # Check if file has reasonable content
        try:
            import json
            with open(checkpoint_file, 'r') as f:
                data = json.load(f)

            # Consider complete if we have analyzed some games
            return len(data) > 0
        except (json.JSONDecodeError, FileNotFoundError):
            return False

    def _is_verdict_extraction_complete(self) -> bool:
        """Check if verdict extraction is complete"""
        hierarchical_file = PIPELINE_PATHS['hierarchical_tags_file']
        if not hierarchical_file.exists():
            return False

        # Check if file has reasonable content
        try:
            import json
            with open(hierarchical_file, 'r') as f:
                data = json.load(f)

            # Consider complete if we have hierarchical data for some games
            return len(data) > 0
        except (json.JSONDecodeError, FileNotFoundError):
            return False

    def _count_analyzed_games(self) -> int:
        """Count games with Steam review analysis"""
        try:
            import json
            checkpoint_file = PIPELINE_PATHS['checkpoint_file']
            with open(checkpoint_file, 'r') as f:
                data = json.load(f)
            return len(data)
        except Exception:
            return 0

    def _count_ign_reviews(self) -> int:
        """Count IGN reviews"""
        try:
            import json
            ign_file = PIPELINE_PATHS['ign_data_file']
            with open(ign_file, 'r') as f:
                data = json.load(f)
            return len(data) if isinstance(data, list) else 0
        except Exception:
            return 0

    def _count_hierarchical_games(self) -> int:
        """Count games with hierarchical classification"""
        try:
            import json
            hierarchical_file = PIPELINE_PATHS['hierarchical_tags_file']
            with open(hierarchical_file, 'r') as f:
                data = json.load(f)
            return len(data)
        except Exception:
            return 0

    def _get_expected_outputs(self) -> List[str]:
        """Return list of expected output files"""
        return [
            str(PIPELINE_PATHS['checkpoint_file']),
            str(PIPELINE_PATHS['ign_data_file']),
            str(PIPELINE_PATHS['hierarchical_tags_file'])
        ]

    def _validate_stage_inputs(self) -> bool:
        """Validate that stage inputs are available"""
        # Need Steam API database from previous stage
        steam_api_db = DATABASE_CONFIG['steam_api_db']
        if not Path(steam_api_db).exists():
            self.logger.error(f"Required input not found: {steam_api_db}")
            return False

        # Check for OpenAI API key
        if not API_CONFIG['openai_api_key']:
            self.logger.error("OpenAI API key not configured")
            return False

        return True

    def get_analysis_stats(self) -> dict:
        """Get detailed analysis statistics"""
        return {
            'steam_analysis_complete': self._is_steam_analysis_complete(),
            'verdict_extraction_complete': self._is_verdict_extraction_complete(),
            'analyzed_games': self._count_analyzed_games(),
            'ign_reviews': self._count_ign_reviews(),
            'hierarchical_games': self._count_hierarchical_games(),
            'checkpoint_file_exists': PIPELINE_PATHS['checkpoint_file'].exists(),
            'ign_file_exists': PIPELINE_PATHS['ign_data_file'].exists(),
            'hierarchical_file_exists': PIPELINE_PATHS['hierarchical_tags_file'].exists()
        }

    def estimate_cost(self) -> dict:
        """Estimate OpenAI API costs for this stage"""
        # Get number of games to analyze
        import sqlite3
        try:
            conn = sqlite3.connect(str(DATABASE_CONFIG['steam_api_db']))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM main_game")
            total_games = cursor.fetchone()[0]
            conn.close()
        except Exception:
            total_games = 1000  # Default estimate

        # Cost calculations (based on GPT-3.5-turbo pricing)
        tokens_per_game = 500  # Average tokens for review analysis
        cost_per_1k_tokens = 0.0015  # GPT-3.5-turbo input cost

        estimated_tokens = total_games * tokens_per_game
        estimated_cost = (estimated_tokens / 1000) * cost_per_1k_tokens

        return {
            'total_games': total_games,
            'estimated_tokens': estimated_tokens,
            'estimated_cost_usd': round(estimated_cost, 2),
            'cost_per_game': round(estimated_cost / total_games, 4) if total_games > 0 else 0
        }