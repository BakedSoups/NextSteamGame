import re
import time
import threading

import requests

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from .llm.errors import NoReviewsAfterFilteringError, SteamReviewsUnavailableError
from .progress import log_stage

# APP_ID = "893180"
MAX_RAW_REVIEWS_PER_GAME = 400
TARGET_FILTERED_REVIEWS = 20
STEAM_REVIEW_RETRIES = 3
STEAM_REVIEW_RETRY_DELAY = 2.0
STEAM_REQUEST_SPACING_SECONDS = 0.75
STEAM_REQUEST_TIMEOUT = (10, 20)
MAX_CONCURRENT_STEAM_FETCHES = 3
STRICT_MIN_WORDS = 50
RELAXED_MIN_WORDS = 20
MIN_PLAYTIME_MINUTES = 60

# --- load embedding model once at the top
model = SentenceTransformer("all-mpnet-base-v2")
STEAM_FETCH_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT_STEAM_FETCHES)


def _is_ascii_art(text):
    letters = len(re.findall(r'[a-zA-Z]', text))
    total = len(text.strip())
    if total == 0:
        return True
    return (letters / total) < 0.5


def _filter_reviews(reviews, min_words):
    counts = {"raw": len(reviews)}

    filtered = [r for r in reviews if not r["refunded"]]
    counts["not_refunded"] = len(filtered)

    filtered = [r for r in filtered if len(r["review"].split()) >= min_words]
    counts[f"min_words_{min_words}"] = len(filtered)

    filtered = [
        r for r in filtered
        if r["author"]["playtime_forever"] >= MIN_PLAYTIME_MINUTES
    ]
    counts[f"playtime_{MIN_PLAYTIME_MINUTES}m"] = len(filtered)

    filtered = [r for r in filtered if not _is_ascii_art(r["review"])]
    counts["not_ascii_art"] = len(filtered)

    seen = set()
    unique_reviews = []
    for review in filtered:
        text = review["review"].strip()
        if text not in seen:
            seen.add(text)
            unique_reviews.append(review)
    counts["deduped"] = len(unique_reviews)
    return unique_reviews, counts


def fetch_steam_reviews(APP_ID):
    url = f"https://store.steampowered.com/appreviews/{APP_ID}"

    params = {
        "json": 1,
        "num_per_page": 100,
        "language": "english",
        "filter": "all",
        "review_type": "all",
        "purchase_type": "steam",
    }

    raw_reviews = []
    seen_recommendations = set()
    cursor = "*"

    while len(raw_reviews) < MAX_RAW_REVIEWS_PER_GAME:
        params["cursor"] = cursor
        res = None
        for attempt in range(1, STEAM_REVIEW_RETRIES + 1):
            try:
                with STEAM_FETCH_SEMAPHORE:
                    time.sleep(STEAM_REQUEST_SPACING_SECONDS)
                    response = requests.get(
                        url,
                        params=params,
                        timeout=STEAM_REQUEST_TIMEOUT,
                        headers={
                            "User-Agent": "SteamRecommender/1.0 (+local build pipeline)",
                            "Accept": "application/json",
                        },
                    )
                    response.raise_for_status()
                    body = response.text.strip()
                    if not body:
                        raise SteamReviewsUnavailableError("No steam review")
                    res = response.json()
                break
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                log_stage("fetch", appid=APP_ID, detail=f"retry {attempt}/{STEAM_REVIEW_RETRIES}")
                if attempt == STEAM_REVIEW_RETRIES:
                    raise SteamReviewsUnavailableError("No steam review") from exc
                time.sleep(STEAM_REVIEW_RETRY_DELAY)
        
        reviews = res.get("reviews", [])
        if not reviews:
            break

        before_count = len(raw_reviews)
        for review in reviews:
            recommendation_id = review.get("recommendationid")
            if recommendation_id in seen_recommendations:
                continue
            seen_recommendations.add(recommendation_id)
            raw_reviews.append(review)
            if len(raw_reviews) >= MAX_RAW_REVIEWS_PER_GAME:
                break
        if len(raw_reviews) == before_count:
            break

        strict_reviews, _ = _filter_reviews(raw_reviews, STRICT_MIN_WORDS)
        if len(strict_reviews) >= TARGET_FILTERED_REVIEWS:
            break

        relaxed_reviews, _ = _filter_reviews(raw_reviews, RELAXED_MIN_WORDS)
        if len(relaxed_reviews) >= TARGET_FILTERED_REVIEWS:
            break

        cursor = res.get("cursor")
        if not cursor:
            break

    if not raw_reviews:
        return []

    strict_reviews, strict_counts = _filter_reviews(raw_reviews, STRICT_MIN_WORDS)
    if strict_reviews:
        return strict_reviews

    relaxed_reviews, relaxed_counts = _filter_reviews(raw_reviews, RELAXED_MIN_WORDS)
    if relaxed_reviews:
        return relaxed_reviews

    raise NoReviewsAfterFilteringError(
        "No reviews after filtering "
        f"(strict={strict_counts}; relaxed={relaxed_counts})"
    )


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
