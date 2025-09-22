"""
Configuration settings for Steam Recommender
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
# This will look for a .env file in the project root
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# Base directory
BASE_DIR = Path(__file__).parent.parent.parent

# Database paths
DATABASE_CONFIG = {
    'steamspy_db': BASE_DIR / "data" / "steamspy_all_games.db",
    'steam_api_db': BASE_DIR / "data" / "steam_api.db",
    'recommendations_db': BASE_DIR / "data" / "steam_recommendations.db",
    'vectorizer_path': BASE_DIR / "data" / "hierarchical_vectorizer.pkl"
}

# API Configuration
API_CONFIG = {
    'openai_api_key': os.getenv('OPENAI_API_KEY', ''),  # Required for database building
    'steamspy_base_url': 'https://steamspy.com/api.php',
    'steam_api_base_url': 'https://store.steampowered.com/api',
    'steam_reviews_base_url': 'https://store.steampowered.com/appreviews'
}

# Rate limiting settings
RATE_LIMITS = {
    'steamspy_delay': float(os.getenv('STEAMSPY_DELAY', '1.0')),  # seconds between requests
    'steam_api_delay': float(os.getenv('STEAM_API_DELAY', '0.5')),
    'steam_api_batch_delay': float(os.getenv('STEAM_API_BATCH_DELAY', '10.0')),
    'openai_max_retries': int(os.getenv('OPENAI_MAX_RETRIES', '3')),
    'steam_api_max_retries': int(os.getenv('STEAM_API_MAX_RETRIES', '3'))
}

# Data collection settings
DATA_COLLECTION = {
    'max_games': int(os.getenv('MAX_GAMES', '20000')),
    'reviews_per_game': int(os.getenv('REVIEWS_PER_GAME', '100')),
    'batch_size': int(os.getenv('BATCH_SIZE', '1000')),
    'checkpoint_interval': int(os.getenv('CHECKPOINT_INTERVAL', '100'))
}

# ML/Vector settings
ML_CONFIG = {
    'tfidf_max_features': int(os.getenv('TFIDF_MAX_FEATURES', '1000')),
    'tfidf_ngram_range': (1, 2),
    'vector_dimension': int(os.getenv('VECTOR_DIMENSION', '1000')),
    'similarity_candidates_limit': int(os.getenv('SIMILARITY_CANDIDATES_LIMIT', '50'))
}

# Web application settings
WEB_CONFIG = {
    'host': os.getenv('FLASK_HOST', '0.0.0.0'),
    'port': int(os.getenv('FLASK_PORT', '5000')),
    'debug': os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 'yes'),
    'secret_key': os.getenv('FLASK_SECRET_KEY', 'steam_game_recommender_secret_key')
}

# Logging configuration
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'log_file': BASE_DIR / 'logs' / 'steam_recommender.log'
}

# File paths for data pipeline
PIPELINE_PATHS = {
    'processed_apps': BASE_DIR / "data" / "processed_apps.txt",
    'checkpoint_file': BASE_DIR / "data" / "checkpoint_steam_analysis.json",
    'ign_data_file': BASE_DIR / "data" / "ign_all_games.json",
    'hierarchical_tags_file': BASE_DIR / "data" / "steam_games_with_hierarchical_tags.json",
    'tag_context_file': BASE_DIR / "data" / "tag_context.json",
    'execution_log': BASE_DIR / "data" / "execution_log.json",
    'stage_checkpoints': BASE_DIR / "data" / "checkpoints"
}

# Pipeline execution settings
PIPELINE_CONFIG = {
    'enable_checkpointing': True,
    'checkpoint_interval': int(os.getenv('CHECKPOINT_INTERVAL', '100')),
    'enable_recovery': True,
    'validate_dependencies': True,
    'parallel_processing': False,  # Future feature
    'max_retries': int(os.getenv('MAX_RETRIES', '3')),
    'retry_delay': float(os.getenv('RETRY_DELAY', '60.0'))  # seconds
}

def ensure_directories():
    """Create necessary directories if they don't exist"""
    directories = [
        BASE_DIR / "data",
        BASE_DIR / "logs",
        LOGGING_CONFIG['log_file'].parent,
        PIPELINE_PATHS['stage_checkpoints']
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

def get_database_url(db_name: str) -> str:
    """Get database URL for given database name"""
    return str(DATABASE_CONFIG.get(f"{db_name}_db", DATABASE_CONFIG['recommendations_db']))

def validate_config(require_openai: bool = False):
    """Validate required configuration"""
    errors = []

    if require_openai and not API_CONFIG['openai_api_key']:
        errors.append("OPENAI_API_KEY environment variable not set")

    # Create data directories
    ensure_directories()

    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")

    return True

def validate_pipeline_config():
    """Validate configuration for database building pipeline"""
    return validate_config(require_openai=True)