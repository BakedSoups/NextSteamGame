import json
from typing import Dict

from .llm.game_semantics import generate_game_semantics
from .llm.errors import NoReviewsAfterFilteringError, NoReviewsError, SteamReviewsUnavailableError
from .steam_review import fetch_steam_reviews, select_review_samples
from paths import insightful_words_path

INSIGHTFUL_WORDS_PATH = insightful_words_path()


def build_skipped_profile(status: str) -> Dict:
    return {
        "review_samples": {
            "status": status,
            "descriptive": [],
            "artistic": [],
            "music": [],
        },
        "vectors": {
            "status": status,
            "mechanics": {},
            "narrative": {},
            "vibe": {},
            "structure_loop": {},
            "uniqueness": {},
        },
        "metadata": {
            "status": status,
            "micro_tags": [],
            "signature_tag": "",
            "appeal_axes": {
                "challenge": 50,
                "complexity": 50,
                "pace": 50,
                "narrative_focus": 50,
                "social_energy": 50,
                "creativity": 50,
            },
            "soundtrack_tags": [],
            "genre_tree": {
                "primary": [],
                "sub": [],
                "sub_sub": [],
                "traits": [],
            },
        },
    }


def load_insightful_words() -> Dict:
    with INSIGHTFUL_WORDS_PATH.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def build_game_output(appid: str, insightful_words: Dict) -> Dict:
    print(f"[{appid}] Fetching Steam reviews")
    try:
        reviews = fetch_steam_reviews(appid)
    except SteamReviewsUnavailableError:
        skipped = build_skipped_profile("no_steam_review")
        return {
            "appid": int(appid),
            "review_samples": skipped["review_samples"],
            "vectors": skipped["vectors"],
            "metadata": skipped["metadata"],
        }
    except NoReviewsAfterFilteringError as exc:
        raise NoReviewsError(str(exc)) from exc

    if not reviews:
        raise NoReviewsError("No reviews")

    print(f"[{appid}] Filtered reviews ready: {len(reviews)}")
    review_samples = select_review_samples(reviews, insightful_words)
    if not any(review_samples.get(category) for category in ("descriptive", "artistic", "music")):
        raise NoReviewsError("No insightful reviews")

    sample_counts = {
        category: len(review_samples.get(category, []))
        for category in ("descriptive", "artistic", "music")
    }
    print(f"[{appid}] Review samples selected: {sample_counts}")
    print(f"[{appid}] Requesting semantics")
    semantics = generate_game_semantics(review_samples)
    print(f"[{appid}] Semantics generated")

    return {
        "appid": int(appid),
        "review_samples": review_samples,
        "vectors": semantics["vectors"],
        "metadata": semantics["metadata"],
    }


def run_single_game(appid: str) -> Dict:
    insightful_words = load_insightful_words()
    return build_game_output(appid, insightful_words)
