import re
import unicodedata
from collections import defaultdict
from typing import Dict, Iterable, List


GENERIC_SUFFIXES = {
    "game",
    "gameplay",
    "mechanic",
    "mechanics",
    "system",
    "systems",
    "elements",
}

TOKEN_ALIASES = {
    "rts": "real time strategy",
    "jrpg": "japanese role playing",
    "arpg": "action role playing",
    "crpg": "computer role playing",
    "fps": "first person shooter",
    "tps": "third person shooter",
    "pvp": "player versus player",
    "pve": "player versus environment",
}

PHRASE_ALIASES = {
    "real time strategy": "real-time strategy",
    "rogue lite": "roguelite",
    "rogue like": "roguelike",
    "co op": "co-op",
    "coop": "co-op",
    "turn based": "turn-based",
    "deck building": "deckbuilding",
    "open world": "open-world",
}


def normalize_tag(tag: str) -> str:
    normalized = unicodedata.normalize("NFKD", tag).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().strip()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[-_/]+", " ", normalized)
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    tokens = [TOKEN_ALIASES.get(token, token) for token in normalized.split()]
    normalized = " ".join(tokens)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    words = normalized.split()
    while len(words) > 1 and words[-1] in GENERIC_SUFFIXES:
        words.pop()
    normalized = " ".join(words)

    return PHRASE_ALIASES.get(normalized, normalized)


def group_tags(sampled_games: Iterable[Dict]) -> Dict[str, Dict[str, Dict[str, List[str] | int]]]:
    grouped: Dict[str, Dict[str, Dict[str, List[str] | int]]] = defaultdict(dict)

    for game in sampled_games:
        game_name = game["name"]

        for category, weights in game["vectors"].items():
            for raw_tag in weights:
                _add_group_entry(grouped, category, raw_tag, game_name)

        for raw_tag in game["metadata"].get("micro_tags", []):
            _add_group_entry(grouped, "micro_tags", raw_tag, game_name)

        genre_tree = game["metadata"].get("genre_tree", {})
        for branch in ("primary", "sub", "traits"):
            for raw_tag in genre_tree.get(branch, []):
                _add_group_entry(grouped, f"genre_{branch}", raw_tag, game_name)

    return grouped


def format_tag_groups(grouped_tags: Dict[str, Dict[str, Dict[str, List[str] | int]]]) -> str:
    lines: List[str] = []

    for category in sorted(grouped_tags):
        lines.append(f"\n=== {category.upper()} ===")

        for canonical_tag, info in sorted(
            grouped_tags[category].items(),
            key=lambda item: (-int(item[1]["count"]), item[0]),
        ):
            raw_tags = ", ".join(sorted(info["raw_tags"]))
            games = ", ".join(sorted(info["games"]))
            lines.append(f"{canonical_tag} ({info['count']})")
            lines.append(f"  raw: {raw_tags}")
            lines.append(f"  games: {games}")

    return "\n".join(lines)


def _add_group_entry(
    grouped: Dict[str, Dict[str, Dict[str, List[str] | int]]],
    category: str,
    raw_tag: str,
    game_name: str,
) -> None:
    canonical_tag = normalize_tag(raw_tag)
    bucket = grouped[category].setdefault(
        canonical_tag,
        {"count": 0, "raw_tags": [], "games": []},
    )

    bucket["count"] += 1
    if raw_tag not in bucket["raw_tags"]:
        bucket["raw_tags"].append(raw_tag)
    if game_name not in bucket["games"]:
        bucket["games"].append(game_name)

