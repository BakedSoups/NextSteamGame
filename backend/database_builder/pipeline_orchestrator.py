#!/usr/bin/env python3
"""
Steam Recommender Database Pipeline Orchestrator

This script orchestrates the complete data pipeline from raw data collection
to final vector database creation. Replaces the Go orchestrator with a unified Python workflow.
"""

import argparse
import logging
import time
from pathlib import Path
from typing import Optional

# Import our Python modules
from .steamspy_collector import create_steamspy_database
from .steam_api_enricher import create_enriched_database
from .database_manager import initialize_database
from .tag_builder.steam_reviews_extractor import main as extract_steam_reviews
from .tag_builder.ign_scrape import main as scrape_ign_reviews
from .tag_builder.extract_verdicts import main as extract_verdicts
from .tag_builder.json_converter import convert_json_to_sqlite

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    """Orchestrates the complete Steam game recommendation pipeline"""

    def __init__(self):
        self.start_time = time.time()

    def show_warning(self) -> bool:
        """Show pipeline warning and get user confirmation"""
        print("\n" + "="*70)
        print("🚨 STEAM RECOMMENDER PIPELINE WARNING 🚨")
        print("="*70)
        print("⏰ This pipeline takes 3+ days to complete due to API rate limits:")
        print("   • SteamSpy collection: ~1 hour (20k games)")
        print("   • Steam API enrichment: ~1 day (rate limited)")
        print("   • Review analysis: ~1-2 days (OpenAI API + scraping)")
        print("   • Vector creation: ~30 minutes")
        print("\n💰 This will consume OpenAI API credits")
        print("📊 Final database will be ~3 months old due to rate limiting")
        print("="*70)

        response = input("\nDo you want to proceed? (y/n): ").strip().lower()
        return response == 'y'

    def stage_1_data_collection(self) -> bool:
        """Stage 1: Collect raw game data from SteamSpy and Steam API"""
        logger.info("🚀 STAGE 1: Data Collection")

        try:
            # Step 1.1: Collect SteamSpy data
            logger.info("📦 Collecting SteamSpy game catalog...")
            steamspy_count = create_steamspy_database()
            logger.info(f"✅ SteamSpy collection complete: {steamspy_count} games")

            # Step 1.2: Enrich with Steam API data
            logger.info("🎮 Enriching with Steam Store API data...")
            enriched_count = create_enriched_database()
            logger.info(f"✅ Steam API enrichment complete: {enriched_count} games")

            logger.info("✨ Stage 1 complete: Data collection finished")
            return True

        except Exception as e:
            logger.error(f"❌ Stage 1 failed: {e}")
            return False

    def stage_2_review_analysis(self) -> bool:
        """Stage 2: Extract and analyze reviews from multiple sources"""
        logger.info("🔍 STAGE 2: Review Analysis")

        try:
            # Step 2.1: Extract Steam reviews and generate tags
            logger.info("💬 Analyzing Steam reviews with OpenAI...")
            extract_steam_reviews()
            logger.info("✅ Steam review analysis complete")

            # Step 2.2: Scrape IGN reviews (optional)
            if self._should_scrape_ign():
                logger.info("📰 Scraping IGN professional reviews...")
                scrape_ign_reviews()
                logger.info("✅ IGN scraping complete")

            # Step 2.3: Extract verdicts and hierarchical tags
            logger.info("🏷️ Extracting game verdicts and hierarchical classification...")
            extract_verdicts()
            logger.info("✅ Verdict extraction complete")

            logger.info("✨ Stage 2 complete: Review analysis finished")
            return True

        except Exception as e:
            logger.error(f"❌ Stage 2 failed: {e}")
            return False

    def stage_3_database_creation(self) -> bool:
        """Stage 3: Create final recommendation database with vectors"""
        logger.info("🗄️ STAGE 3: Database Creation")

        try:
            # Step 3.1: Initialize database and migrate review data
            logger.info("🏗️ Initializing recommendation database...")
            initialize_database()
            logger.info("✅ Database initialization complete")

            # Step 3.2: Convert JSON to hierarchical SQLite database
            logger.info("🔄 Converting tags to hierarchical database...")
            convert_json_to_sqlite()
            logger.info("✅ Hierarchical database creation complete")

            logger.info("✨ Stage 3 complete: Database creation finished")
            return True

        except Exception as e:
            logger.error(f"❌ Stage 3 failed: {e}")
            return False

    def _should_scrape_ign(self) -> bool:
        """Check if IGN scraping should be performed"""
        # Check if IGN data already exists
        ign_file = Path("tag_builder/ign_all_games.json")
        if ign_file.exists():
            response = input("IGN data exists. Re-scrape? (y/n): ").strip().lower()
            return response == 'y'
        return True

    def run_full_pipeline(self) -> bool:
        """Execute the complete pipeline"""
        logger.info("🚀 Starting Steam Recommender Pipeline")

        # Stage 1: Data Collection
        if not self.stage_1_data_collection():
            return False

        # Stage 2: Review Analysis
        if not self.stage_2_review_analysis():
            return False

        # Stage 3: Database Creation
        if not self.stage_3_database_creation():
            return False

        # Pipeline complete
        duration = time.time() - self.start_time
        hours = duration / 3600
        logger.info(f"🎉 PIPELINE COMPLETE! Duration: {hours:.1f} hours")

        # Print final summary
        self._print_pipeline_summary()

        return True

    def run_stage(self, stage: int) -> bool:
        """Run a specific pipeline stage"""
        logger.info(f"🎯 Running Stage {stage} only")

        if stage == 1:
            return self.stage_1_data_collection()
        elif stage == 2:
            return self.stage_2_review_analysis()
        elif stage == 3:
            return self.stage_3_database_creation()
        else:
            logger.error(f"Invalid stage: {stage}. Must be 1, 2, or 3")
            return False

    def _print_pipeline_summary(self) -> None:
        """Print comprehensive pipeline completion summary"""
        print("\n" + "="*70)
        print("🎉 STEAM RECOMMENDER PIPELINE COMPLETE!")
        print("="*70)

        # Check output files
        outputs = [
            ("SteamSpy Database", "./steamspy_all_games.db"),
            ("Steam API Database", "./steam_api.db"),
            ("Recommendation Database", "./steam_recommendations.db"),
            ("TF-IDF Vectorizer", "./hierarchical_vectorizer.pkl"),
            ("Steam Analysis", "./tag_builder/checkpoint_steam_analysis.json"),
            ("IGN Reviews", "./tag_builder/ign_all_games.json"),
            ("Hierarchical Tags", "./tag_builder/steam_games_with_hierarchical_tags.json")
        ]

        print("\n📁 OUTPUT FILES:")
        for name, path in outputs:
            if Path(path).exists():
                size_mb = Path(path).stat().st_size / (1024 * 1024)
                print(f"   ✅ {name}: {path} ({size_mb:.1f} MB)")
            else:
                print(f"   ❌ {name}: {path} (missing)")

        duration = time.time() - self.start_time
        print(f"\n⏱️ Total Duration: {duration/3600:.1f} hours")
        print("\n🚀 Your Steam recommender is ready!")
        print("   Run: python app.py")
        print("="*70)

def main():
    """Main entry point with CLI arguments"""
    parser = argparse.ArgumentParser(description="Steam Recommender Pipeline Orchestrator")
    parser.add_argument("--stage", type=int, choices=[1, 2, 3],
                       help="Run specific stage only (1: Data Collection, 2: Review Analysis, 3: Database Creation)")
    parser.add_argument("--skip-warning", action="store_true",
                       help="Skip the initial warning prompt")

    args = parser.parse_args()

    orchestrator = PipelineOrchestrator()

    # Show warning unless skipped
    if not args.skip_warning:
        if not orchestrator.show_warning():
            print("Pipeline cancelled by user")
            return

    # Run pipeline
    try:
        if args.stage:
            success = orchestrator.run_stage(args.stage)
        else:
            success = orchestrator.run_full_pipeline()

        if success:
            print("✅ Pipeline completed successfully")
        else:
            print("❌ Pipeline failed")
            exit(1)

    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        print("\n⏹️ Pipeline stopped by user")
    except Exception as e:
        logger.error(f"Unexpected pipeline error: {e}")
        print(f"❌ Unexpected error: {e}")
        exit(1)

if __name__ == "__main__":
    main()