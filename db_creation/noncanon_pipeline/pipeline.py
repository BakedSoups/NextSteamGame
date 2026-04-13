import json
from typing import Dict

from .llm.game_metadata import generate_game_metadata
from .llm.semantic_vectors import generate_game_vectors
from .steam_review import fetch_steam_reviews, select_review_samples
from paths import insightful_words_path

INSIGHTFUL_WORDS_PATH = insightful_words_path()


def load_insightful_words() -> Dict:
    with INSIGHTFUL_WORDS_PATH.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def build_game_output(appid: str, insightful_words: Dict) -> Dict:
    reviews = fetch_steam_reviews(appid)
    review_samples = select_review_samples(reviews, insightful_words)

    return {
        "appid": int(appid),
        "review_samples": review_samples,
        "vectors": generate_game_vectors(review_samples),
        "metadata": generate_game_metadata(review_samples),
    }


def run_single_game(appid: str) -> Dict:
    insightful_words = load_insightful_words()
    return build_game_output(appid, insightful_words)
