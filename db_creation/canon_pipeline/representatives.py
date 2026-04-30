from __future__ import annotations

from collections import Counter

from .layer_1_normalization import format_display, head_token
from .types import CanonGroup


def build_group(context: str, normalized_tag: str, total_occurrences: int, raw_counts: Counter) -> CanonGroup:
    representative = choose_representative(normalized_tag, raw_counts)
    parent = derive_parent_tag(context, normalized_tag)
    specificity = 1 if parent == normalized_tag else 2
    return CanonGroup(
        context=context,
        representative_tag=representative,
        parent_tag=format_display(parent),
        specificity_level=specificity,
        counts={representative: total_occurrences},
        raw_counts=dict(raw_counts),
    )


def choose_representative(normalized_tag: str, raw_counts: Counter) -> str:
    if raw_counts:
        best_raw = sorted(raw_counts.items(), key=lambda item: (-item[1], len(item[0]), item[0]))[0][0]
        return format_display(best_raw)
    return format_display(normalized_tag)


def derive_parent_tag(context: str, normalized_tag: str) -> str:
    if context.startswith("genre_tree.") or context in {"music_primary", "music_secondary", "setting_tags"}:
        return normalized_tag
    head = head_token(normalized_tag)
    return head or normalized_tag
