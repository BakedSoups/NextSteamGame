from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import random
from typing import Callable, Dict, List

from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors

from .representative_selection import choose_representative

ACRONYM_MAP = {
    "2d": "2D",
    "3d": "3D",
    "ai": "AI",
    "npc": "NPC",
    "pve": "PvE",
    "pvp": "PvP",
    "rpg": "RPG",
}

HYPHENATED_COMPOUNDS = {
    ("action", "packed"): "action-packed",
    ("fast", "paced"): "fast-paced",
    ("real", "time"): "real-time",
}

WEAK_MODIFIERS = {
    "action",
    "atmospheric",
    "casual",
    "emotional",
    "explosive",
    "fast",
    "hectic",
    "frenetic",
    "intense",
    "low",
}

GENERIC_MODIFIERS = {
    "character",
    "general",
    "personal",
}

STRONG_SUBTYPE_TOKENS = {
    "2d",
    "3d",
    "adventure",
    "brawler",
    "platformer",
    "puzzle",
    "rpg",
    "stealth",
    "strategy",
    "survival",
    "tactical",
}


@dataclass
class Group:
    context: str
    representative: str
    members: List[str] = field(default_factory=list)
    counts: Counter = field(default_factory=Counter)
    raw_members: List[str] = field(default_factory=list)
    raw_counts: Counter = field(default_factory=Counter)

    def add(
        self,
        tag: str,
        occurrences: int,
        raw_variants: Counter | None = None,
    ) -> None:
        self.members.append(tag)
        self.counts[tag] += occurrences
        if raw_variants is None:
            self.raw_members.append(tag)
            self.raw_counts[tag] += occurrences
            return
        for raw_tag, raw_count in raw_variants.items():
            self.raw_members.append(raw_tag)
            self.raw_counts[raw_tag] += raw_count

    @property
    def member_count(self) -> int:
        return len(self.members)

    @property
    def total_occurrences(self) -> int:
        return sum(self.counts.values())


def load_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)


def tokenize(tag: str) -> list[str]:
    return [token for token in tag.split() if token]


def head_token(tokens: list[str]) -> str:
    if not tokens:
        return ""
    if len(tokens) > 1 and tokens[-1] in STRONG_SUBTYPE_TOKENS:
        return tokens[0]
    return tokens[-1]


def extra_modifiers(tokens: list[str], head: str) -> set[str]:
    remaining = tokens.copy()
    if head in remaining:
        remaining.remove(head)
    return set(remaining)


def is_weak_modifier_set(modifiers: set[str]) -> bool:
    if not modifiers:
        return True
    for modifier in modifiers:
        if modifier in WEAK_MODIFIERS or modifier in GENERIC_MODIFIERS:
            continue
        return False
    return True


def merge_allowed(left_tag: str, right_tag: str) -> bool:
    if left_tag == right_tag:
        return True

    left_tokens = tokenize(left_tag)
    right_tokens = tokenize(right_tag)
    shared_tokens = set(left_tokens) & set(right_tokens)
    if not shared_tokens:
        return False

    left_head = head_token(left_tokens)
    right_head = head_token(right_tokens)
    left_extras = extra_modifiers(left_tokens, left_head)
    right_extras = extra_modifiers(right_tokens, right_head)

    left_subtypes = left_extras & STRONG_SUBTYPE_TOKENS
    right_subtypes = right_extras & STRONG_SUBTYPE_TOKENS
    if left_subtypes != right_subtypes:
        return False

    if left_head == right_head:
        if is_weak_modifier_set(left_extras | right_extras):
            return True
        return left_extras == right_extras

    if left_head in shared_tokens and is_weak_modifier_set(right_extras):
        return True
    if right_head in shared_tokens and is_weak_modifier_set(left_extras):
        return True
    return False


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


def create_groups_for_context(
    context: str,
    counts: Counter,
    raw_member_map: Dict[str, Counter],
    model: SentenceTransformer,
    threshold: float,
    max_neighbors: int,
    rng: random.Random,
    guard: Callable[[str, str], bool] | None = None,
) -> List[Group]:
    tags = [tag for tag, _ in counts.most_common()]
    if not tags:
        return []

    embeddings = model.encode(
        tags,
        batch_size=256,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    neighbor_count = min(max_neighbors, len(tags))
    neighbors = NearestNeighbors(metric="cosine", n_neighbors=neighbor_count, algorithm="brute")
    neighbors.fit(embeddings)
    assigned = set()
    groups: List[Group] = []

    for index, tag in enumerate(tags):
        if index in assigned:
            continue

        distances, candidate_indexes = neighbors.kneighbors(
            embeddings[index].reshape(1, -1),
            n_neighbors=neighbor_count,
            return_distance=True,
        )
        chosen_indexes: List[int] = []
        for candidate_index, distance in zip(candidate_indexes[0], distances[0]):
            if candidate_index in assigned:
                continue
            similarity = 1.0 - float(distance)
            candidate_tag = tags[candidate_index]
            if similarity < threshold:
                continue
            if guard is not None and not guard(tag, candidate_tag):
                continue
            if not merge_allowed(tag, candidate_tag):
                continue
            chosen_indexes.append(candidate_index)

        if not chosen_indexes:
            chosen_indexes = [index]

        representative = format_representative_tag(
            context,
            choose_representative(
                [tags[chosen_index] for chosen_index in chosen_indexes],
                rng,
                counts=counts,
            ),
        )
        group = Group(context=context, representative=representative)
        for chosen_index in chosen_indexes:
            assigned.add(chosen_index)
            normalized_tag = tags[chosen_index]
            group.add(
                normalized_tag,
                counts[normalized_tag],
                raw_variants=raw_member_map.get(normalized_tag),
            )
        groups.append(group)

    groups.sort(key=lambda group: (-group.total_occurrences, group.context, group.representative))
    return groups


def build_groups(
    counters: Dict[str, Counter],
    raw_member_maps: Dict[str, Dict[str, Counter]],
    model: SentenceTransformer,
    thresholds: Dict[str, float],
    max_neighbors: int,
    rng: random.Random,
    guard: Callable[[str, str], bool] | None = None,
) -> List[Group]:
    groups: List[Group] = []
    for context in sorted(counters):
        groups.extend(
            create_groups_for_context(
                context=context,
                counts=counters[context],
                raw_member_map=raw_member_maps[context],
                model=model,
                threshold=thresholds[context],
                max_neighbors=max_neighbors,
                rng=rng,
                guard=guard,
            )
        )
    groups.sort(key=lambda group: (-group.total_occurrences, group.context, group.representative))
    return groups
