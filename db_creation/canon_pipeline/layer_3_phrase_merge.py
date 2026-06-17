from __future__ import annotations

from collections import Counter
from collections import defaultdict
from typing import Dict

from .layer_1_normalization import head_token, normalize_tag, tokenize


def _token_overlap(left: str, right: str) -> float:
    left_tokens = set(tokenize(left))
    right_tokens = set(tokenize(right))
    if not left_tokens or not right_tokens:
        return 0.0
    union = left_tokens | right_tokens
    if not union:
        return 0.0
    return len(left_tokens & right_tokens) / len(union)


def _can_merge_phrase_variant(left: str, right: str) -> bool:
    if left == right:
        return True
    left_tokens = tokenize(left)
    right_tokens = tokenize(right)
    if len(left_tokens) < 2 or len(right_tokens) < 2:
        return False
    if head_token(left) != head_token(right):
        return False
    overlap = _token_overlap(left, right)
    if overlap >= 0.8:
        return True
    if overlap >= 0.66 and abs(len(left_tokens) - len(right_tokens)) <= 1:
        return True
    return False


def merge_surface_variants(counter: Counter, raw_members: Dict[str, Counter]) -> tuple[Counter, Dict[str, Counter]]:
    merged_counter = Counter()
    merged_members: Dict[str, Counter] = {}
    buckets: dict[tuple[str, int], list[str]] = defaultdict(list)

    for tag in counter:
        tokens = tokenize(tag)
        bucket_key = (head_token(tag), len(tokens))
        buckets[bucket_key].append(tag)

    total_buckets = len(buckets)
    for bucket_index, bucket_tags in enumerate(buckets.values(), start=1):
        if bucket_index == 1 or bucket_index % 250 == 0 or bucket_index == total_buckets:
            print(
                f"Layer 3 progress: bucket={bucket_index}/{total_buckets} "
                f"bucket_size={len(bucket_tags)} merged_groups={len(merged_counter)}"
            )
        ordered = sorted(bucket_tags, key=lambda tag: (-counter[tag], len(tag), tag))
        consumed: set[str] = set()

        for seed in ordered:
            if seed in consumed:
                continue
            base = normalize_tag(seed)
            merged_counter[base] += counter[seed]
            merged_members.setdefault(base, Counter()).update(raw_members.get(seed, Counter()))
            consumed.add(seed)

            seed_len = len(tokenize(seed))
            for candidate in ordered:
                if candidate in consumed or candidate == seed:
                    continue
                candidate_len = len(tokenize(candidate))
                if abs(candidate_len - seed_len) > 1:
                    continue
                if not _can_merge_phrase_variant(base, candidate):
                    continue
                merged_counter[base] += counter[candidate]
                merged_members.setdefault(base, Counter()).update(raw_members.get(candidate, Counter()))
                consumed.add(candidate)

    return merged_counter, merged_members
