"""
Configuration settings for Steam Recommender
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
    'openai_api_key': os.getenv('OPENAI_API_KEY'),
    'steamspy_base_url': 'https://steamspy.com/api.php',
    'steam_api_base_url': 'https://store.steampowered.com/api',
    'steam_reviews_base_url': 'https://store.steampowered.com/appreviews'
}

# Rate limiting settings
RATE_LIMITS = {
    'steamspy_delay': 1.0,  # seconds between requests
    'steam_api_delay': 0.5,
    'steam_api_batch_delay': 10.0,
    'openai_max_retries': 3,
    'steam_api_max_retries': 3
}

# Data collection settings
DATA_COLLECTION = {
    'max_games': 20000,
    'reviews_per_game': 100,
    'batch_size': 1000,
    'checkpoint_interval': 100
}

# ML/Vector settings
ML_CONFIG = {
    'tfidf_max_features': 1000,
    'tfidf_ngram_range': (1, 2),
    'vector_dimension': 1000,
    'similarity_candidates_limit': 50
}

# Web application settings
WEB_CONFIG = {
    'host': '0.0.0.0',
    'port': 5000,
    'debug': True,
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
    'tag_context_file': BASE_DIR / "data" / "tag_context.json"
}

def ensure_directories():
    """Create necessary directories if they don't exist"""
    directories = [
        BASE_DIR / "data",
        BASE_DIR / "logs",
        LOGGING_CONFIG['log_file'].parent
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