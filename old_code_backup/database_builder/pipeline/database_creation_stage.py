"""
Database Creation Stage - Creates final recommendation database with vectors
"""
import logging
import sqlite3
from typing import Optional, List
from pathlib import Path

from .base_stage import BasePipelineStage, StageResult, StageCheckpoint
from backend.config import DATABASE_CONFIG, PIPELINE_PATHS


class DatabaseCreationStage(BasePipelineStage):
    """Stage 3: Create final recommendation database with hierarchical structure and vectors"""

    def __init__(self):
        super().__init__(
            stage_name="database_creation",
            dependencies=["data_collection", "review_analysis"]
        )

    def _execute_stage(self, checkpoint: Optional[StageCheckpoint]) -> StageResult:
        """Execute database creation stage"""
        self.logger.info("🗄️ Starting final recommendation database creation")

        total_processed = 0
        output_files = []
        stage_metadata = {}

        try:
            # Sub-stage 1: Initialize Database Schema
            if not self._is_database_initialized():
                self.logger.info("🏗️ Initializing recommendation database schema...")
                self._initialize_database()
                self.logger.info("✅ Database schema initialization complete")
            else:
                self.logger.info("✅ Database schema already initialized")

            # Sub-stage 2: Convert JSON to Hierarchical SQLite Database
            if not self._is_json_conversion_complete():
                self.logger.info("🔄 Converting analysis data to hierarchical database...")
                converted_count = self._convert_json_to_sqlite()
                total_processed += converted_count
                stage_metadata['games_converted'] = converted_count
                self.logger.info(f"✅ Hierarchical database creation complete: {converted_count} games")
            else:
                self.logger.info("✅ JSON conversion already complete")
                stage_metadata['games_converted'] = self._count_recommendation_games()

            # Sub-stage 3: Create TF-IDF Vectors
            if not self._are_vectors_created():
                self.logger.info("🧮 Creating TF-IDF vectors for similarity matching...")
                vector_count = self._create_tfidf_vectors()
                total_processed += vector_count
                stage_metadata['vectors_created'] = vector_count
                self.logger.info(f"✅ Vector creation complete: {vector_count} game vectors")
            else:
                self.logger.info("✅ TF-IDF vectors already exist")
                stage_metadata['vectors_created'] = self._count_vectors()

            # Sub-stage 4: Create Performance Indexes
            self.logger.info("📊 Creating performance indexes...")
            self._create_performance_indexes()
            self.logger.info("✅ Performance indexes created")

            # Add output files
            output_files = [
                str(DATABASE_CONFIG['recommendations_db']),
                str(DATABASE_CONFIG['vectorizer_path'])
            ]

            # Generate database statistics
            stats = self._get_database_statistics()
            stage_metadata.update(stats)

            self.logger.info("✨ Database creation stage complete")
            return StageResult(
                success=True,
                stage_name=self.stage_name,
                duration=self.start_time,
                items_processed=total_processed,
                output_files=output_files,
                metadata=stage_metadata
            )

        except Exception as e:
            self.logger.error(f"Database creation failed: {e}")
            raise

    def _initialize_database(self) -> None:
        """Initialize the recommendation database schema"""
        from backend.database_builder.database_manager import initialize_database
        initialize_database()

    def _convert_json_to_sqlite(self) -> int:
        """Convert JSON analysis data to SQLite hierarchical database"""
        try:
            from backend.database_builder.tag_builder.json_converter import convert_json_to_sqlite
            return convert_json_to_sqlite()
        except Exception as e:
            self.logger.error(f"JSON to SQLite conversion failed: {e}")
            raise

    def _create_tfidf_vectors(self) -> int:
        """Create TF-IDF vectors for similarity matching"""
        # Check if the json_converter already handles vectorization
        vectorizer_path = DATABASE_CONFIG['vectorizer_path']
        if Path(vectorizer_path).exists():
            return self._count_vectors()

        # If not, we need to create vectors separately
        # This would involve loading the hierarchical database and creating vectors
        # For now, assuming json_converter handles this
        self.logger.warning("Vector creation not implemented separately - should be handled by json_converter")
        return 0

    def _create_performance_indexes(self) -> None:
        """Create performance indexes on the recommendation database"""
        conn = sqlite3.connect(str(DATABASE_CONFIG['recommendations_db']))
        cursor = conn.cursor()

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_games_appid ON games(steam_appid);",
            "CREATE INDEX IF NOT EXISTS idx_games_name ON games(name);",
            "CREATE INDEX IF NOT EXISTS idx_games_main_genre ON games(main_genre);",
            "CREATE INDEX IF NOT EXISTS idx_games_sub_genre ON games(sub_genre);",
            "CREATE INDEX IF NOT EXISTS idx_games_sub_sub_genre ON games(sub_sub_genre);",
            "CREATE INDEX IF NOT EXISTS idx_steam_tags_appid ON steam_tags(steam_appid);",
            "CREATE INDEX IF NOT EXISTS idx_unique_tags_appid ON unique_tags(steam_appid);",
            "CREATE INDEX IF NOT EXISTS idx_subjective_tags_appid ON subjective_tags(steam_appid);",
            "CREATE INDEX IF NOT EXISTS idx_game_vectors_appid ON game_vectors(steam_appid);",
        ]

        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
                self.logger.debug(f"Created index: {index_sql.split()[-1]}")
            except sqlite3.Error as e:
                self.logger.warning(f"Error creating index: {e}")

        conn.commit()
        conn.close()

    def _is_database_initialized(self) -> bool:
        """Check if recommendation database is initialized"""
        db_path = DATABASE_CONFIG['recommendations_db']
        if not Path(db_path).exists():
            return False

        # Check if basic tables exist
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Check for key tables
            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('games', 'steam_tags', 'unique_tags')
            """)
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            # Should have at least the main tables
            required_tables = {'games', 'steam_tags', 'unique_tags'}
            return required_tables.issubset(set(tables))

        except Exception:
            return False

    def _is_json_conversion_complete(self) -> bool:
        """Check if JSON to SQLite conversion is complete"""
        db_path = DATABASE_CONFIG['recommendations_db']
        if not Path(db_path).exists():
            return False

        # Check if games table has data
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM games")
            count = cursor.fetchone()[0]
            conn.close()

            # Consider complete if we have some games
            return count > 0
        except Exception:
            return False

    def _are_vectors_created(self) -> bool:
        """Check if TF-IDF vectors are created"""
        vectorizer_path = DATABASE_CONFIG['vectorizer_path']
        if not Path(vectorizer_path).exists():
            return False

        # Check if game_vectors table exists and has data
        db_path = DATABASE_CONFIG['recommendations_db']
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM game_vectors")
            count = cursor.fetchone()[0]
            conn.close()

            return count > 0
        except Exception:
            return False

    def _count_recommendation_games(self) -> int:
        """Count games in recommendation database"""
        try:
            conn = sqlite3.connect(str(DATABASE_CONFIG['recommendations_db']))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM games")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    def _count_vectors(self) -> int:
        """Count TF-IDF vectors in database"""
        try:
            conn = sqlite3.connect(str(DATABASE_CONFIG['recommendations_db']))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM game_vectors")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    def _get_database_statistics(self) -> dict:
        """Get comprehensive database statistics"""
        stats = {}

        try:
            conn = sqlite3.connect(str(DATABASE_CONFIG['recommendations_db']))
            cursor = conn.cursor()

            # Basic counts
            tables = ['games', 'steam_tags', 'unique_tags', 'subjective_tags', 'game_vectors']
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[f"{table}_count"] = cursor.fetchone()[0]
                except sqlite3.Error:
                    stats[f"{table}_count"] = 0

            # Genre distribution
            try:
                cursor.execute("""
                SELECT main_genre, COUNT(*) as count
                FROM games
                GROUP BY main_genre
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
                stats['database_size_mb'] = stats['database_size_bytes'] / (1024 * 1024)
            except sqlite3.Error:
                stats['database_size_bytes'] = 0
                stats['database_size_mb'] = 0

            conn.close()

        except Exception as e:
            self.logger.warning(f"Could not get database statistics: {e}")

        return stats

    def _get_expected_outputs(self) -> List[str]:
        """Return list of expected output files"""
        return [
            str(DATABASE_CONFIG['recommendations_db']),
            str(DATABASE_CONFIG['vectorizer_path'])
        ]

    def _validate_stage_inputs(self) -> bool:
        """Validate that stage inputs are available"""
        # Check for analysis JSON files
        required_files = [
            PIPELINE_PATHS['checkpoint_file'],
            PIPELINE_PATHS['hierarchical_tags_file']
        ]

        for file_path in required_files:
            if not Path(file_path).exists():
                self.logger.error(f"Required input file not found: {file_path}")
                return False

        return True

    def get_database_stats(self) -> dict:
        """Get detailed database statistics"""
        return {
            'database_initialized': self._is_database_initialized(),
            'json_conversion_complete': self._is_json_conversion_complete(),
            'vectors_created': self._are_vectors_created(),
            'games_count': self._count_recommendation_games(),
            'vectors_count': self._count_vectors(),
            'database_size_mb': self._get_database_statistics().get('database_size_mb', 0)
        }

    def validate_database_integrity(self) -> dict:
        """Validate the integrity of the created database"""
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': []
        }

        try:
            conn = sqlite3.connect(str(DATABASE_CONFIG['recommendations_db']))
            cursor = conn.cursor()

            # Check foreign key constraints
            cursor.execute("PRAGMA foreign_key_check")
            fk_violations = cursor.fetchall()
            if fk_violations:
                validation_results['valid'] = False
                validation_results['errors'].append(f"Foreign key violations found: {len(fk_violations)}")

            # Check for games without tags
            cursor.execute("""
            SELECT COUNT(*) FROM games g
            LEFT JOIN steam_tags st ON g.steam_appid = st.steam_appid
            WHERE st.steam_appid IS NULL
            """)
            games_without_tags = cursor.fetchone()[0]
            if games_without_tags > 0:
                validation_results['warnings'].append(f"{games_without_tags} games have no Steam tags")

            # Check for games without vectors
            cursor.execute("""
            SELECT COUNT(*) FROM games g
            LEFT JOIN game_vectors gv ON g.steam_appid = gv.steam_appid
            WHERE gv.steam_appid IS NULL
            """)
            games_without_vectors = cursor.fetchone()[0]
            if games_without_vectors > 0:
                validation_results['warnings'].append(f"{games_without_vectors} games have no vectors")

            conn.close()

        except Exception as e:
            validation_results['valid'] = False
            validation_results['errors'].append(f"Database validation failed: {e}")

        return validation_results