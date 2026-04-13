from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .lexical_similarity import looks_like_surface_variant, token_jaccard
from ..normalization.surface_forms import head_token, tokenize


@dataclass
class ContextTokenStats:
    token_occurrences: Counter = field(default_factory=Counter)
    token_tag_count: Counter = field(default_factory=Counter)
    token_head_count: dict[str, set[str]] = field(default_factory=dict)
    head_occurrences: Counter = field(default_factory=Counter)


def build_context_stats(counts: Counter) -> ContextTokenStats:
    stats = ContextTokenStats()
    for tag, occurrences in counts.items():
        tokens = tokenize(tag)
        head = head_token(tokens)
        stats.head_occurrences[head] += occurrences
        for token in set(tokens):
            stats.token_occurrences[token] += occurrences
            stats.token_tag_count[token] += 1
            stats.token_head_count.setdefault(token, set()).add(head)
    return stats


def classify_modifier(modifier: str, stats: ContextTokenStats) -> str:
    head_diversity = len(stats.token_head_count.get(modifier, set()))
    tag_diversity = stats.token_tag_count.get(modifier, 0)
    token_frequency = stats.token_occurrences.get(modifier, 0)

    if any(char.isdigit() for char in modifier):
        return "form_factor"
    if modifier.isalpha() and len(modifier) <= 3:
        return "form_factor"
    if modifier.endswith(("ing", "ed")):
        return "process"
    if modifier.endswith(("ive", "al", "ic", "ous", "ful", "less", "able")):
        return "descriptive"
    if head_diversity == 1 and (tag_diversity <= 2 or token_frequency <= 3):
        return "specific"
    if head_diversity >= 3 or tag_diversity >= 5:
        return "generic"
    return "unknown"


def classify_modifier_set(modifiers: set[str], stats: ContextTokenStats) -> set[str]:
    if not modifiers:
        return {"none"}
    return {classify_modifier(modifier, stats) for modifier in modifiers}


def is_mergeable_modifier_profile(profile: set[str]) -> bool:
    return profile <= {"none", "descriptive", "generic", "process", "unknown"}


def merge_allowed(left_tag: str, right_tag: str, stats: ContextTokenStats) -> bool:
    if left_tag == right_tag:
        return True

    if looks_like_surface_variant(left_tag, right_tag):
        return True

    left_tokens = tokenize(left_tag)
    right_tokens = tokenize(right_tag)
    left_head = head_token(left_tokens)
    right_head = head_token(right_tokens)
    if left_head != right_head:
        return False

    left_extras = set(left_tokens)
    right_extras = set(right_tokens)
    left_extras.discard(left_head)
    right_extras.discard(right_head)

    if bool(left_extras) != bool(right_extras):
        return False

    left_profile = classify_modifier_set(left_extras, stats)
    right_profile = classify_modifier_set(right_extras, stats)

    if "specific" in left_profile or "specific" in right_profile:
        return left_extras == right_extras
    if "form_factor" in left_profile or "form_factor" in right_profile:
        return left_extras == right_extras

    if left_extras == right_extras:
        return True

    if is_mergeable_modifier_profile(left_profile | right_profile) and token_jaccard(left_tag, right_tag) >= 0.5:
        return True
    return False
