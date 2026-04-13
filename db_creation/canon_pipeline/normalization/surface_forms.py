from __future__ import annotations

import re


TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_text(tag: str) -> str:
    normalized = tag.strip().lower().replace("_", " ").replace("-", " ")
    return " ".join(TOKEN_RE.findall(normalized))


def tokenize(tag: str) -> list[str]:
    return [token for token in normalize_text(tag).split() if token]


def head_token(tokens: list[str]) -> str:
    if not tokens:
        return ""
    return tokens[-1]
