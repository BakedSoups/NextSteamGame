from __future__ import annotations

import re


TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_text(tag: str) -> str:
    normalized = tag.strip().lower().replace("_", " ").replace("-", " ")
    return " ".join(TOKEN_RE.findall(normalized))


def token_set(tag: str) -> set[str]:
    return set(normalize_text(tag).split())


def metadata_lexical_guard(left: str, right: str) -> bool:
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if left_norm == right_norm:
        return True

    left_tokens = token_set(left)
    right_tokens = token_set(right)
    if left_tokens & right_tokens:
        return True

    return len(left_tokens) == 1 and len(right_tokens) == 1
