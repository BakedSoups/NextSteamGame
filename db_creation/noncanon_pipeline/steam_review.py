import re
import time

import requests

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from .llm.errors import SteamReviewsUnavailableError

# APP_ID = "893180"
MAX_REVIEWS_PER_GAME = 250
STEAM_REVIEW_RETRIES = 3
STEAM_REVIEW_RETRY_DELAY = 2.0

# --- load embedding model once at the top
model = SentenceTransformer("all-mpnet-base-v2")


def fetch_steam_reviews(APP_ID):
    url = f"https://store.steampowered.com/appreviews/{APP_ID}"

    params = {
        "json": 1,
        "num_per_page": 100,
        "language": "english",
        "filter": "all",
    }

    all_reviews = []
    cursor = "*"

    while len(all_reviews) < MAX_REVIEWS_PER_GAME:
        params["cursor"] = cursor
        res = None
        for attempt in range(1, STEAM_REVIEW_RETRIES + 1):
            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                body = response.text.strip()
                if not body:
                    raise SteamReviewsUnavailableError("No steam review")
                res = response.json()
                break
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                if attempt == STEAM_REVIEW_RETRIES:
                    raise SteamReviewsUnavailableError("No steam review") from exc
                time.sleep(STEAM_REVIEW_RETRY_DELAY)
        
        reviews = res.get("reviews", [])
        if not reviews:
            break

        all_reviews.extend(reviews)
        if len(all_reviews) >= MAX_REVIEWS_PER_GAME:
            all_reviews = all_reviews[:MAX_REVIEWS_PER_GAME]
            break
        cursor = res.get("cursor")

    # --- basic filters
    all_reviews = [r for r in all_reviews if not r['refunded']]
    all_reviews = [r for r in all_reviews if len(r['review'].split()) >= 50]

    # --- playtime >= 60 minutes
    all_reviews = [
        r for r in all_reviews
        if r["author"]["playtime_forever"] >= 60
    ]

    # --- ascii filter
    def is_ascii_art(text):
        letters = len(re.findall(r'[a-zA-Z]', text))
        total = len(text.strip())
        if total == 0:
            return True
        return (letters / total) < 0.5

    all_reviews = [r for r in all_reviews if not is_ascii_art(r['review'])]

    # --- deduplicate reviews
    seen = set()
    unique_reviews = []
    for r in all_reviews:
        text = r["review"].strip()
        if text not in seen:
            seen.add(text)
            unique_reviews.append(r)

    return unique_reviews


def score_category(text, category):
    text = text.lower()

    core_hits = sum(term in text for term in category["core"])
    context_hits = sum(term in text for term in category["context"])
    modifier_hits = sum(term in text for term in category["modifiers"])

    return core_hits * 2 + context_hits + modifier_hits * 0.5


def score_review(review_text, lexicon):
    scores = {}
    for category_name, category_data in lexicon.items():
        scores[category_name] = score_category(review_text, category_data)
    return scores


def rerank_with_embeddings(candidates, query):
    if not candidates:
        return []

    texts = [r["review"] for r in candidates]

    review_embeddings = model.encode(texts)
    query_embedding = model.encode([query])[0]

    sims = cosine_similarity([query_embedding], review_embeddings)[0]

    for i, r in enumerate(candidates):
        r["embedding_score"] = float(sims[i])

    return sorted(candidates, key=lambda x: x["embedding_score"], reverse=True)


def select_review_samples(reviews: list, semantic_lexicon: dict):
    scored_reviews = []

    for r in reviews:
        text = r["review"]
        scores = score_review(text, semantic_lexicon)

        scored_reviews.append({
            "review": text,
            "scores": scores
        })

    if not scored_reviews:
        return {
            "descriptive": [],
            "artistic": [],
            "music": [],
        }

    if all(max(review["scores"].values(), default=0) <= 0 for review in scored_reviews):
        return {
            "descriptive": [],
            "artistic": [],
            "music": [],
        }

    # --- Stage 1: heuristic top 30 per category
    top_descriptive = [
        review for review in sorted(
        scored_reviews,
        key=lambda x: x["scores"]["descriptive"],
        reverse=True
        )[:30]
        if review["scores"]["descriptive"] > 0
    ]

    top_artistic = [
        review for review in sorted(
        scored_reviews,
        key=lambda x: x["scores"]["artistic"],
        reverse=True
        )[:30]
        if review["scores"]["artistic"] > 0
    ]

    top_music = [
        review for review in sorted(
        scored_reviews,
        key=lambda x: x["scores"]["music"],
        reverse=True
        )[:30]
        if review["scores"]["music"] > 0
    ]

    # --- Stage 2: embedding rerank
    desc_query = "a deep insightful review explaining why the game works or does not"
    art_query = "a review describing visuals art style aesthetics and design"
    music_query = "a review discussing music soundtrack audio design and sound quality"

    top_descriptive = rerank_with_embeddings(top_descriptive, desc_query)[:3]
    top_artistic = rerank_with_embeddings(top_artistic, art_query)[:3]
    top_music = rerank_with_embeddings(top_music, music_query)[:3]

    # print("\n=== TOP DESCRIPTIVE ===")
    # for r in top_descriptive:
    #     print(r["scores"], "| emb:", round(r["embedding_score"], 3))
    #     print(r["review"])
    #     print("\n")

    # print("\n=== TOP ARTISTIC ===")
    # for r in top_artistic:
    #     print(r["scores"], "| emb:", round(r["embedding_score"], 3))
    #     print(r["review"])
    #     print("\n")

    return {
        "descriptive": top_descriptive,
        "artistic": top_artistic,
        "music": top_music
    }


# if __name__ == "__main__":
#     import json

#     reviews = fetch_steam_reviews(APP_ID)
#     with open("insightful_words.json", "r", encoding="utf-8") as f:
#         semantic_lexicon = json.load(f)
#     results = select_review_samples(reviews, semantic_lexicon)


# pull_reviews = fetch_steam_reviews
# capture_descriptive_reviews = select_review_samples
