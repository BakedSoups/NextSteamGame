from .steam_review import fetch_steam_reviews, select_review_samples
from .llm.game_metadata import generate_game_metadata
from .llm.semantic_vectors import generate_game_vectors
from .pipeline import run_database_tag_preview, run_single_game

pull_reviews = fetch_steam_reviews
capture_descriptive_reviews = select_review_samples
embedsteam_review = generate_game_vectors
