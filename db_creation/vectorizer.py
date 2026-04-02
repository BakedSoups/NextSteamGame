import json
from vector_creator import (
    fetch_steam_reviews,
    select_review_samples,
    generate_game_vectors,
    generate_game_metadata,
)

APP_ID = "893180"


# 1. pull reviews
reviews = fetch_steam_reviews(APP_ID)

# 2. load lexicon
with open("insightful_words.json", "r", encoding="utf-8") as f:
    insightful_words = json.load(f)

# 3. structured ranking
review_samples = select_review_samples(reviews, insightful_words)

# 4. semantic vectors (LLM step)
vectors = generate_game_vectors(review_samples)

# 5. metadata (separate LLM step)
metadata = generate_game_metadata(review_samples)

# 6. output
print("\n=== FINAL VECTORS ===\n")
print(json.dumps(vectors, indent=2))

print("\n=== GAME METADATA ===\n")
print(json.dumps(metadata, indent=2))
