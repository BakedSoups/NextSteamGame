import json
import random
import sqlite3
from pathlib import Path
from typing import Dict, List

from .llm.game_metadata import generate_game_metadata
from .llm.semantic_vectors import generate_game_vectors
from .steam_review import fetch_steam_reviews, select_review_samples
from .tag_unification import format_tag_groups, group_tags


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "steam_metadata.db"
INSIGHTFUL_WORDS_PATH = Path(__file__).resolve().parents[1] / "insightful_words.json"
SAMPLE_OUTPUT_PATH = Path(__file__).resolve().parents[1] / "sampled_game_tags.json"


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


def fetch_random_games(sample_size: int = 5, pool_size: int = 25) -> List[Dict]:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT appid, name
            FROM games
            WHERE has_store_data = 1
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (pool_size,),
        ).fetchall()

    candidates = [{"appid": row["appid"], "name": row["name"]} for row in rows]
    random.shuffle(candidates)
    return candidates[:sample_size]


def run_database_tag_preview(sample_size: int = 5) -> Dict:
    insightful_words = load_insightful_words()
    sampled_games = []

    for game in fetch_random_games(sample_size=sample_size, pool_size=sample_size * 6):
        try:
            game_output = build_game_output(str(game["appid"]), insightful_words)
        except Exception as exc:
            print(f"Skipping {game['name']} ({game['appid']}): {exc}")
            continue

        sampled_games.append(
            {
                "appid": game["appid"],
                "name": game["name"],
                "vectors": game_output["vectors"],
                "metadata": game_output["metadata"],
            }
        )

        print(f"Processed {game['name']} ({game['appid']})")

        if len(sampled_games) >= sample_size:
            break

    SAMPLE_OUTPUT_PATH.write_text(json.dumps(sampled_games, indent=2), encoding="utf-8")
    grouped_tags = group_tags(sampled_games)

    return {
        "sampled_games": sampled_games,
        "grouped_tags": grouped_tags,
        "grouped_text": format_tag_groups(grouped_tags),
        "output_path": str(SAMPLE_OUTPUT_PATH),
    }
