from .steam_review import fetch_steam_reviews, select_review_samples
from .llm.game_metadata import generate_game_metadata
from .llm.semantic_vectors import generate_game_vectors

pull_reviews = fetch_steam_reviews
capture_descriptive_reviews = select_review_samples
embedsteam_review = generate_game_vectors
