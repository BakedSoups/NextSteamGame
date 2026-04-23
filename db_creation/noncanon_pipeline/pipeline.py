import json
from typing import Dict

from .llm.game_semantics import generate_game_semantics
from .llm.errors import NoReviewsAfterFilteringError, NoReviewsError, SteamReviewsUnavailableError
from .progress import advance_appid, start_appid
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
            "systems_depth": [],
        },
        "vectors": {
            "status": status,
            "mechanics": {},
            "narrative": {},
            "vibe": {},
            "structure_loop": {},
        },
        "metadata": {
            "status": status,
            "micro_tags": [],
            "signature_tag": "",
            "niche_anchors": [],
            "identity_tags": [],
            "music_primary": "",
            "music_secondary": "",
            "appeal_axes": {
                "challenge": 50,
                "complexity": 50,
                "pace": 50,
                "narrative_focus": 50,
                "social_energy": 50,
                "creativity": 50,
            },
            "genre_tree": {
                "primary": "",
                "sub": "",
                "sub_sub": "",
            },
        },
    }


def load_insightful_words() -> Dict:
    with INSIGHTFUL_WORDS_PATH.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def build_game_output(appid: str, insightful_words: Dict) -> Dict:
    start_appid(appid)
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
        raise NoReviewsError(str(exc), status="no_reviews_after_filtering") from exc

    if not reviews:
        raise NoReviewsError("No reviews", status="no_reviews")

    advance_appid(appid, "fetch", f"raw Steam reviews collected")
    advance_appid(appid, "filter", f"{len(reviews)} reviews survived filtering")
    review_samples = select_review_samples(reviews, insightful_words)
    if not any(review_samples.get(category) for category in ("descriptive", "artistic", "music", "systems_depth")):
        raise NoReviewsError("No insightful reviews", status="no_insightful_reviews")

    sample_counts = {
        category: len(review_samples.get(category, []))
        for category in ("descriptive", "artistic", "music", "systems_depth")
    }
    advance_appid(
        appid,
        "sample",
        (
            f"descriptive={sample_counts['descriptive']} "
            f"artistic={sample_counts['artistic']} "
            f"music={sample_counts['music']} "
            f"systems_depth={sample_counts['systems_depth']}"
        ),
    )
    semantics = generate_game_semantics(review_samples, appid=appid)
    advance_appid(appid, "semantics", "structured semantics generated")

    return {
        "appid": int(appid),
        "review_samples": review_samples,
        "vectors": semantics["vectors"],
        "metadata": semantics["metadata"],
    }


def run_single_game(appid: str) -> Dict:
    insightful_words = load_insightful_words()
    return build_game_output(appid, insightful_words)
