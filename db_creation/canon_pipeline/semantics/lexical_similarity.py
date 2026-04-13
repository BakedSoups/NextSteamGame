from __future__ import annotations

from difflib import SequenceMatcher

from ..normalization.surface_forms import tokenize


def token_jaccard(left: str, right: str) -> float:
    left_tokens = set(tokenize(left))
    right_tokens = set(tokenize(right))
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def sequence_ratio(left: str, right: str) -> float:
    return SequenceMatcher(a=left, b=right).ratio()


def looks_like_surface_variant(left: str, right: str) -> bool:
    return token_jaccard(left, right) >= 0.95 or sequence_ratio(left, right) >= 0.92
