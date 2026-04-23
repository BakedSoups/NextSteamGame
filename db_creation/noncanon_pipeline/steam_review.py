import re
import time
import threading
import random

import requests

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from .llm.errors import NoReviewsAfterFilteringError, SteamReviewsUnavailableError
from .progress import log_stage

# APP_ID = "893180"
MAX_RAW_REVIEWS_PER_GAME = 2000
MIN_FETCH_PAGES_BEFORE_EARLY_STOP = 5
MIN_RAW_REVIEWS_BEFORE_EARLY_STOP = 500
TARGET_FILTERED_REVIEWS = 120
MIN_RAW_REVIEWS_BEFORE_RECENT_FALLBACK = 400
MIN_FILTERED_REVIEWS_BEFORE_RECENT_FALLBACK = 60
MAX_ALL_PAGES = 5
MAX_RECENT_PAGES = 8
LOW_YIELD_WINDOW_PAGES = 3
LOW_YIELD_RAW_DELTA_THRESHOLD = 30
LOW_YIELD_FILTERED_DELTA_THRESHOLD = 8
REVIEWS_PER_SAMPLE_BUCKET = {
    "descriptive": 5,
    "artistic": 4,
    "music": 3,
    "systems_depth": 6,
}
STEAM_REVIEW_RETRIES = 3
STEAM_REVIEW_RETRY_DELAY = 2.0
STEAM_REVIEW_BACKOFF_MULTIPLIER = 2.0
STEAM_REVIEW_MAX_RETRY_DELAY = 20.0
STEAM_REVIEW_RETRY_JITTER = 0.75
STEAM_EMPTY_PAGE_RETRIES = 2
STEAM_CURSOR_STALL_RETRIES = 2
STEAM_DUPLICATE_PAGE_RETRIES = 3
STEAM_REQUEST_SPACING_SECONDS = 0.75
STEAM_REQUEST_TIMEOUT = (10, 20)
MAX_CONCURRENT_STEAM_FETCHES = 3
STRICT_MIN_WORDS = 50
RELAXED_MIN_WORDS = 20
MIN_PLAYTIME_MINUTES = 60

# --- load embedding model once at the top
model = SentenceTransformer("all-mpnet-base-v2")
STEAM_FETCH_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT_STEAM_FETCHES)
STEAM_THREAD_LOCAL = threading.local()
TEMPLATE_REVIEW_PATTERNS = (
    re.compile(r"---\{\s*graphics\s*\}---", re.IGNORECASE),
    re.compile(r"---\{\s*gameplay\s*\}---", re.IGNORECASE),
    re.compile(r"---\{\s*audio\s*\}---", re.IGNORECASE),
    re.compile(r"---\{\s*price\s*\}---", re.IGNORECASE),
    re.compile(r"---\{\s*bugs\s*\}---", re.IGNORECASE),
    re.compile(r"---\{\s*\?\s*/\s*10\s*\}---", re.IGNORECASE),
    re.compile(r"[☐☑✅❌].{0,40}[☐☑✅❌]", re.IGNORECASE),
)
FORMAT_PATTERN_BONUSES = (
    re.compile(r"\bgraphics\b.{0,40}\bgameplay\b.{0,40}\baudio\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\bpros?\b.{0,60}\bcons?\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\bscore\s*:\s*\d+(\.\d+)?\s*/\s*10\b", re.IGNORECASE),
)
CONCRETE_SIGNAL_PATTERNS = (
    re.compile(r"\b(recoil|spray|aim|crosshair|movement|straf|peek|headshot|weapon|loadout|economy|round|match|server|mod|map|bomb|flash|smoke)\w*\b", re.IGNORECASE),
    re.compile(r"\b(soundtrack|audio|sound design|soundscape|footstep|gunshot|music|mix|voice line)\b", re.IGNORECASE),
    re.compile(r"\b(graphics|visuals|textures|lighting|animation|ui|interface|art style|palette|model)\b", re.IGNORECASE),
    re.compile(r"\b(setting|city|school|dungeon|factory|kitchen|restaurant|ocean|space|wilderness|urban|world)\b", re.IGNORECASE),
)


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


def _normalize_review_text(text: str) -> str:
    return " ".join(text.split())


def _looks_like_template_review(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return True
    return any(pattern.search(normalized) for pattern in TEMPLATE_REVIEW_PATTERNS)


def _format_penalty(text: str) -> float:
    penalty = 0.0
    for pattern in FORMAT_PATTERN_BONUSES:
        if pattern.search(text):
            penalty += 0.25
    return min(penalty, 0.5)


def _looks_like_joke_or_meme_review(text: str) -> bool:
    normalized = _normalize_review_text(text)
    if not normalized:
        return True
    words = normalized.split()
    if len(words) < 20:
        repeated_tokens = len(words) - len(set(word.lower() for word in words))
        if repeated_tokens >= max(4, len(words) // 3):
            return True
    uppercase_chars = sum(1 for char in normalized if char.isupper())
    alpha_chars = sum(1 for char in normalized if char.isalpha())
    if alpha_chars > 0 and (uppercase_chars / alpha_chars) > 0.55:
        return True
    if re.search(r"\b(\w+)(?:\W+\1){4,}\b", normalized, re.IGNORECASE):
        return True
    return False


def _concrete_signal_bonus(text: str) -> float:
    hits = sum(1 for pattern in CONCRETE_SIGNAL_PATTERNS if pattern.search(text))
    if hits <= 0:
        return 0.0
    return min(0.12 * hits, 0.36)


def _review_quality_multiplier(text: str) -> float:
    if _looks_like_template_review(text):
        return 0.0
    multiplier = 1.0
    multiplier -= _format_penalty(text)
    if _looks_like_joke_or_meme_review(text):
        multiplier *= 0.55
    multiplier += _concrete_signal_bonus(text)
    return max(multiplier, 0.1)


def _steam_session() -> requests.Session:
    session = getattr(STEAM_THREAD_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "SteamRecommender/1.0 (+local build pipeline)",
                "Accept": "application/json",
            }
        )
        STEAM_THREAD_LOCAL.session = session
    return session


def _retry_sleep_seconds(attempt: int, *, retry_after: str | None = None) -> float:
    if retry_after:
        try:
            hinted = float(retry_after)
        except (TypeError, ValueError):
            hinted = 0.0
        if hinted > 0:
            return min(hinted, STEAM_REVIEW_MAX_RETRY_DELAY)

    delay = min(
        STEAM_REVIEW_RETRY_DELAY * (STEAM_REVIEW_BACKOFF_MULTIPLIER ** max(attempt - 1, 0)),
        STEAM_REVIEW_MAX_RETRY_DELAY,
    )
    jitter = random.uniform(0.0, STEAM_REVIEW_RETRY_JITTER)
    return delay + jitter


def _should_switch_to_recent(raw_reviews: list, *, duplicate_pages: int, cursor_stalls: int) -> bool:
    if duplicate_pages <= STEAM_DUPLICATE_PAGE_RETRIES and cursor_stalls <= STEAM_CURSOR_STALL_RETRIES:
        return False
    strict_reviews, _ = _filter_reviews(raw_reviews, STRICT_MIN_WORDS)
    relaxed_reviews, _ = _filter_reviews(raw_reviews, RELAXED_MIN_WORDS)
    if len(raw_reviews) >= MIN_RAW_REVIEWS_BEFORE_RECENT_FALLBACK:
        return False
    if len(strict_reviews) >= MIN_FILTERED_REVIEWS_BEFORE_RECENT_FALLBACK:
        return False
    if len(relaxed_reviews) >= MIN_FILTERED_REVIEWS_BEFORE_RECENT_FALLBACK:
        return False
    return True


def _filtered_review_counts(raw_reviews: list) -> tuple[int, int]:
    strict_reviews, _ = _filter_reviews(raw_reviews, STRICT_MIN_WORDS)
    relaxed_reviews, _ = _filter_reviews(raw_reviews, RELAXED_MIN_WORDS)
    return len(strict_reviews), len(relaxed_reviews)


def fetch_steam_reviews(APP_ID):
    url = f"https://store.steampowered.com/appreviews/{APP_ID}"

    base_params = {
        "json": 1,
        "num_per_page": 100,
        "language": "english",
        "review_type": "all",
        "purchase_type": "steam",
    }

    raw_reviews = []
    seen_recommendations = set()
    fetch_filter = "all"
    used_recent_fallback = False

    while len(raw_reviews) < MAX_RAW_REVIEWS_PER_GAME:
        cursor = "*"
        pages_fetched = 0
        consecutive_empty_pages = 0
        consecutive_cursor_stalls = 0
        consecutive_duplicate_pages = 0
        page_budget = MAX_ALL_PAGES if fetch_filter == "all" else MAX_RECENT_PAGES
        low_yield_history: list[tuple[int, int, int]] = []

        while len(raw_reviews) < MAX_RAW_REVIEWS_PER_GAME:
            if pages_fetched >= page_budget:
                log_stage(
                    "fetch",
                    appid=APP_ID,
                    detail=f"page budget reached using {fetch_filter} pages={pages_fetched}",
                )
                break
            params = {
                **base_params,
                "filter": fetch_filter,
                "cursor": cursor,
            }
            res = None
            for attempt in range(1, STEAM_REVIEW_RETRIES + 1):
                try:
                    with STEAM_FETCH_SEMAPHORE:
                        time.sleep(STEAM_REQUEST_SPACING_SECONDS)
                        response = _steam_session().get(
                            url,
                            params=params,
                            timeout=STEAM_REQUEST_TIMEOUT,
                        )
                        if response.status_code in {429, 500, 502, 503, 504}:
                            raise requests.HTTPError(
                                f"steam transient status {response.status_code}",
                                response=response,
                            )
                        response.raise_for_status()
                        body = response.text.strip()
                        if not body:
                            raise SteamReviewsUnavailableError("No steam review")
                        res = response.json()
                        if not isinstance(res, dict):
                            raise SteamReviewsUnavailableError("Malformed steam review payload")
                    break
                except KeyboardInterrupt:
                    raise
                except Exception as exc:
                    retry_after = None
                    status_code = None
                    if isinstance(exc, requests.HTTPError) and exc.response is not None:
                        status_code = exc.response.status_code
                        retry_after = exc.response.headers.get("Retry-After")
                    sleep_for = _retry_sleep_seconds(attempt, retry_after=retry_after)
                    detail = f"{fetch_filter} retry {attempt}/{STEAM_REVIEW_RETRIES}"
                    if status_code is not None:
                        detail += f" status={status_code}"
                    detail += f" sleep={sleep_for:.1f}s"
                    log_stage("fetch", appid=APP_ID, detail=detail)
                    if attempt == STEAM_REVIEW_RETRIES:
                        raise SteamReviewsUnavailableError("No steam review") from exc
                    time.sleep(sleep_for)

            query_summary = res.get("query_summary") or {}
            total_reviews_reported = query_summary.get("total_reviews")
            try:
                total_reviews_reported = int(total_reviews_reported)
            except (TypeError, ValueError):
                total_reviews_reported = None

            reviews = res.get("reviews", [])
            if pages_fetched == 0 and total_reviews_reported == 0:
                log_stage("fetch", appid=APP_ID, detail=f"{fetch_filter} reports zero reviews")
                return []
            if not reviews:
                consecutive_empty_pages += 1
                log_stage(
                    "fetch",
                    appid=APP_ID,
                    detail=(
                        f"{fetch_filter} empty page {consecutive_empty_pages}/{STEAM_EMPTY_PAGE_RETRIES + 1} "
                        f"cursor={cursor}"
                    ),
                )
                if consecutive_empty_pages > STEAM_EMPTY_PAGE_RETRIES:
                    break
                time.sleep(_retry_sleep_seconds(consecutive_empty_pages))
                continue
            consecutive_empty_pages = 0
            pages_fetched += 1

            before_count = len(raw_reviews)
            for review in reviews:
                recommendation_id = review.get("recommendationid")
                if recommendation_id in seen_recommendations:
                    continue
                seen_recommendations.add(recommendation_id)
                raw_reviews.append(review)
                if len(raw_reviews) >= MAX_RAW_REVIEWS_PER_GAME:
                    break

            strict_count, relaxed_count = _filtered_review_counts(raw_reviews)
            low_yield_history.append((len(raw_reviews), strict_count, relaxed_count))
            if len(low_yield_history) > LOW_YIELD_WINDOW_PAGES:
                low_yield_history.pop(0)

            if len(raw_reviews) == before_count:
                consecutive_duplicate_pages += 1
                log_stage(
                    "fetch",
                    appid=APP_ID,
                    detail=(
                        f"duplicate page using {fetch_filter} "
                        f"{consecutive_duplicate_pages}/{STEAM_DUPLICATE_PAGE_RETRIES + 1} "
                        f"cursor={cursor}"
                    ),
                )
                if consecutive_duplicate_pages > STEAM_DUPLICATE_PAGE_RETRIES:
                    break
                time.sleep(_retry_sleep_seconds(consecutive_duplicate_pages))
            else:
                consecutive_duplicate_pages = 0

            if pages_fetched % 5 == 0:
                log_stage(
                    "fetch",
                    appid=APP_ID,
                    detail=(
                        f"{fetch_filter} pages={pages_fetched} raw={len(raw_reviews)} "
                        f"strict={strict_count} relaxed={relaxed_count}"
                    ),
                )

            if (
                pages_fetched >= MIN_FETCH_PAGES_BEFORE_EARLY_STOP
                and len(raw_reviews) >= MIN_RAW_REVIEWS_BEFORE_EARLY_STOP
                and (
                    strict_count >= TARGET_FILTERED_REVIEWS
                    or relaxed_count >= TARGET_FILTERED_REVIEWS
                )
            ):
                break

            if len(low_yield_history) >= LOW_YIELD_WINDOW_PAGES:
                first_raw, first_strict, first_relaxed = low_yield_history[0]
                raw_gain = len(raw_reviews) - first_raw
                filtered_gain = max(
                    strict_count - first_strict,
                    relaxed_count - first_relaxed,
                )
                if (
                    raw_gain <= LOW_YIELD_RAW_DELTA_THRESHOLD
                    and filtered_gain <= LOW_YIELD_FILTERED_DELTA_THRESHOLD
                ):
                    log_stage(
                        "fetch",
                        appid=APP_ID,
                        detail=(
                            f"low-yield stop using {fetch_filter} "
                            f"raw_gain={raw_gain} filtered_gain={filtered_gain} "
                            f"window={LOW_YIELD_WINDOW_PAGES}"
                        ),
                    )
                    break

            next_cursor = res.get("cursor")
            if next_cursor == cursor:
                consecutive_cursor_stalls += 1
                log_stage(
                    "fetch",
                    appid=APP_ID,
                    detail=(
                        f"cursor stall using {fetch_filter} "
                        f"{consecutive_cursor_stalls}/{STEAM_CURSOR_STALL_RETRIES + 1} "
                        f"pages={pages_fetched}"
                    ),
                )
                if consecutive_cursor_stalls > STEAM_CURSOR_STALL_RETRIES:
                    break
                time.sleep(_retry_sleep_seconds(consecutive_cursor_stalls))
                continue
            consecutive_cursor_stalls = 0
            cursor = next_cursor
            if not cursor:
                break

        if fetch_filter == "all" and not used_recent_fallback and _should_switch_to_recent(
            raw_reviews,
            duplicate_pages=consecutive_duplicate_pages,
            cursor_stalls=consecutive_cursor_stalls,
        ):
            used_recent_fallback = True
            fetch_filter = "recent"
            log_stage(
                "fetch",
                appid=APP_ID,
                detail=(
                    f"switching to recent after all stalled raw={len(raw_reviews)} "
                    f"dup={consecutive_duplicate_pages} stall={consecutive_cursor_stalls}"
                ),
            )
            continue
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
        quality_multiplier = _review_quality_multiplier(text)
        if quality_multiplier <= 0.0:
            continue
        scores = score_review(text, semantic_lexicon)
        adjusted_scores = {
            category: score * quality_multiplier
            for category, score in scores.items()
        }

        scored_reviews.append({
            "review": text,
            "scores": scores,
            "adjusted_scores": adjusted_scores,
            "quality_multiplier": quality_multiplier,
        })

    if not scored_reviews:
        return {
            "descriptive": [],
            "artistic": [],
            "music": [],
            "systems_depth": [],
        }

    if all(max(review["scores"].values(), default=0) <= 0 for review in scored_reviews):
        return {
            "descriptive": [],
            "artistic": [],
            "music": [],
            "systems_depth": [],
        }

    # --- Stage 1: heuristic top 30 per category
    top_descriptive = [
        review for review in sorted(
        scored_reviews,
        key=lambda x: x["adjusted_scores"]["descriptive"],
        reverse=True
        )[:30]
        if review["adjusted_scores"]["descriptive"] > 0
    ]

    top_artistic = [
        review for review in sorted(
        scored_reviews,
        key=lambda x: x["adjusted_scores"]["artistic"],
        reverse=True
        )[:30]
        if review["adjusted_scores"]["artistic"] > 0
    ]

    top_music = [
        review for review in sorted(
        scored_reviews,
        key=lambda x: x["adjusted_scores"]["music"],
        reverse=True
        )[:30]
        if review["adjusted_scores"]["music"] > 0
    ]

    top_systems_depth = [
        review for review in sorted(
        scored_reviews,
        key=lambda x: (
            x["adjusted_scores"].get("explainability", 0.0)
            + x["adjusted_scores"]["descriptive"]
        ),
        reverse=True
        )[:40]
        if (
            review["adjusted_scores"].get("explainability", 0.0)
            + review["adjusted_scores"]["descriptive"]
        ) > 0
    ]

    # --- Stage 2: embedding rerank
    desc_query = "a deep insightful review explaining why the game works or does not"
    art_query = "a review describing visuals art style aesthetics and design"
    music_query = (
        "a review that clearly describes the soundtrack style, genre, instrumentation, "
        "or musical identity of the game rather than generic sound quality"
    )
    systems_depth_query = (
        "a review explaining the deeper systems, optimization, mastery, or hidden depth "
        "that makes this game stand out from superficially similar games"
    )

    top_descriptive = rerank_with_embeddings(top_descriptive, desc_query)[:REVIEWS_PER_SAMPLE_BUCKET["descriptive"]]
    top_artistic = rerank_with_embeddings(top_artistic, art_query)[:REVIEWS_PER_SAMPLE_BUCKET["artistic"]]
    top_music = rerank_with_embeddings(top_music, music_query)[:REVIEWS_PER_SAMPLE_BUCKET["music"]]
    top_systems_depth = rerank_with_embeddings(top_systems_depth, systems_depth_query)[:REVIEWS_PER_SAMPLE_BUCKET["systems_depth"]]

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
        "music": top_music,
        "systems_depth": top_systems_depth,
    }


# if __name__ == "__main__":
#     import json

#     reviews = fetch_steam_reviews(APP_ID)
#     with open("insightful_words.json", "r", encoding="utf-8") as f:
#         semantic_lexicon = json.load(f)
#     results = select_review_samples(reviews, semantic_lexicon)


# pull_reviews = fetch_steam_reviews
# capture_descriptive_reviews = select_review_samples
