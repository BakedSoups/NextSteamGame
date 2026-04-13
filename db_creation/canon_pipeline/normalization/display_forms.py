from __future__ import annotations

from .surface_forms import tokenize


ACRONYM_MAP = {
    "2d": "2D",
    "3d": "3D",
    "ai": "AI",
    "npc": "NPC",
    "pve": "PvE",
    "pvp": "PvP",
    "rpg": "RPG",
    "ui": "UI",
    "vr": "VR",
}

HYPHENATED_COMPOUNDS = {
    ("action", "packed"): "action-packed",
    ("fast", "paced"): "fast-paced",
    ("hands", "on"): "hands-on",
    ("real", "time"): "real-time",
    ("top", "down"): "top-down",
    ("turn", "based"): "turn-based",
}


def format_representative_tag(context: str, normalized_tag: str) -> str:
    tokens = tokenize(normalized_tag)
    parts: list[str] = []
    index = 0
    while index < len(tokens):
        pair = tuple(tokens[index : index + 2])
        if pair in HYPHENATED_COMPOUNDS:
            compound = HYPHENATED_COMPOUNDS[pair]
            if context.startswith("genre_tree."):
                compound = "-".join(part.capitalize() for part in compound.split("-"))
            parts.append(compound)
            index += 2
            continue

        token = tokens[index]
        if token in ACRONYM_MAP:
            parts.append(ACRONYM_MAP[token])
        elif context.startswith("genre_tree."):
            parts.append(token.capitalize())
        else:
            parts.append(token)
        index += 1
    return " ".join(parts)
