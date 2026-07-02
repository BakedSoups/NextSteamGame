from __future__ import annotations

import re


TOKEN_RE = re.compile(r"[a-z0-9]+")
ACRONYM_MAP = {
    "2d": "2D",
    "3d": "3D",
    "4x": "4X",
    "4k": "4K",
    "ai": "AI",
    "jrpg": "JRPG",
    "mmo": "MMO",
    "npc": "NPC",
    "pve": "PvE",
    "pvp": "PvP",
    "rpg": "RPG",
    "rts": "RTS",
    "ui": "UI",
    "vr": "VR",
}
IRREGULAR_MAP = {
    "actions": "action",
    "mechanics": "mechanic",
    "systems": "system",
    "themes": "theme",
    "stories": "story",
    "visuals": "visual",
    "vibes": "vibe",
}
HYPHENATED_COMPOUNDS = {
    ("co", "op"): "co-op",
    ("fast", "paced"): "fast-paced",
    ("post", "apocalyptic"): "post-apocalyptic",
    ("turn", "based"): "turn-based",
}


def tokenize(tag: str) -> list[str]:
    lowered = str(tag).strip().lower().replace("_", " ").replace("-", " ")
    tokens = TOKEN_RE.findall(lowered)
    return [_normalize_token(token) for token in tokens if _normalize_token(token)]


def _normalize_token(token: str) -> str:
    token = token.strip().lower()
    if not token:
        return ""
    if token in IRREGULAR_MAP:
        return IRREGULAR_MAP[token]
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("s") and len(token) > 4 and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def normalize_tag(tag: str) -> str:
    tokens = tokenize(tag)
    parts: list[str] = []
    index = 0
    while index < len(tokens):
        pair = tuple(tokens[index : index + 2])
        if pair in HYPHENATED_COMPOUNDS:
            parts.append(HYPHENATED_COMPOUNDS[pair])
            index += 2
            continue
        parts.append(tokens[index])
        index += 1
    return " ".join(parts)


def format_display(tag: str) -> str:
    parts = []
    for part in normalize_tag(tag).split():
        parts.append(ACRONYM_MAP.get(part, part))
    return " ".join(parts)


def head_token(tag: str) -> str:
    tokens = normalize_tag(tag).split()
    return tokens[-1] if tokens else ""
