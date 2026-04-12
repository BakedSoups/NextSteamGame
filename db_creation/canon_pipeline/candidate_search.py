from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import random
from typing import Callable, Dict, List

from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors

from .representative_selection import choose_representative


@dataclass
class Group:
    context: str
    representative: str
    members: List[str] = field(default_factory=list)
    counts: Counter = field(default_factory=Counter)

    def add(self, tag: str, occurrences: int) -> None:
        self.members.append(tag)
        self.counts[tag] += occurrences

    @property
    def member_count(self) -> int:
        return len(self.members)

    @property
    def total_occurrences(self) -> int:
        return sum(self.counts.values())


def load_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)


def create_groups_for_context(
    context: str,
    counts: Counter,
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
            chosen_indexes.append(candidate_index)

        if not chosen_indexes:
            chosen_indexes = [index]

        representative = choose_representative(
            [tags[chosen_index] for chosen_index in chosen_indexes],
            rng,
        )
        group = Group(context=context, representative=representative)
        for chosen_index in chosen_indexes:
            assigned.add(chosen_index)
            group.add(tags[chosen_index], counts[tags[chosen_index]])
        groups.append(group)

    groups.sort(key=lambda group: (-group.total_occurrences, group.context, group.representative))
    return groups


def build_groups(
    counters: Dict[str, Counter],
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
                model=model,
                threshold=thresholds[context],
                max_neighbors=max_neighbors,
                rng=rng,
                guard=guard,
            )
        )
    groups.sort(key=lambda group: (-group.total_occurrences, group.context, group.representative))
    return groups
