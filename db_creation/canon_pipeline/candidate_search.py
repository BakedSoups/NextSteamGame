from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import random
from typing import Callable, Dict, List

from .normalization.display_forms import format_representative_tag
from .semantics.clustering import connected_similarity_clusters
from .semantics.embeddings import encode_tags, load_model
from .semantics.family_builder import build_family_index
from .semantics.specificity import ContextTokenStats, build_context_stats, merge_allowed
from .representative_selection import choose_representative


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


def _materialize_cluster(
    context: str,
    cluster: list[int],
    tags: list[str],
    counts: Counter,
    raw_member_map: Dict[str, Counter],
    stats: ContextTokenStats,
    rng: random.Random,
) -> Group:
    accepted: list[int] = []
    for candidate_index in cluster:
        candidate_tag = tags[candidate_index]
        if all(
            merge_allowed(candidate_tag, tags[other_index], stats)
            for other_index in accepted
        ):
            accepted.append(candidate_index)

    if not accepted:
        accepted = [cluster[0]]

    representative = format_representative_tag(
        context,
        choose_representative(
            [tags[index] for index in accepted],
            rng,
            counts=counts,
        ),
    )
    group = Group(context=context, representative=representative)
    for accepted_index in accepted:
        normalized_tag = tags[accepted_index]
        group.add(
            normalized_tag,
            counts[normalized_tag],
            raw_variants=raw_member_map.get(normalized_tag),
        )
    return group


def create_groups_for_context(
    context: str,
    counts: Counter,
    raw_member_map: Dict[str, Counter],
    model,
    threshold: float,
    max_neighbors: int,
    rng: random.Random,
    guard: Callable[[str, str], bool] | None = None,
) -> List[Group]:
    tags = [tag for tag, _ in counts.most_common()]
    if not tags:
        return []

    stats = build_context_stats(counts)
    embeddings = encode_tags(model, tags)
    family_index = build_family_index(tags)
    groups: List[Group] = []

    for family_members in family_index.values():
        clusters = connected_similarity_clusters(family_members, embeddings, threshold)
        for cluster in clusters:
            filtered_cluster = cluster
            if guard is not None and len(cluster) > 1:
                filtered_cluster = []
                for candidate_index in cluster:
                    candidate_tag = tags[candidate_index]
                    if any(
                        candidate_index == other_index or guard(candidate_tag, tags[other_index])
                        for other_index in cluster
                    ):
                        filtered_cluster.append(candidate_index)
            if not filtered_cluster:
                filtered_cluster = [cluster[0]]

            group = _materialize_cluster(
                context=context,
                cluster=filtered_cluster,
                tags=tags,
                counts=counts,
                raw_member_map=raw_member_map,
                stats=stats,
                rng=rng,
            )
            groups.append(group)

    groups.sort(key=lambda group: (-group.total_occurrences, group.context, group.representative))
    return groups


def build_groups(
    counters: Dict[str, Counter],
    raw_member_maps: Dict[str, Dict[str, Counter]],
    model,
    thresholds: Dict[str, float],
    max_neighbors: int,
    rng: random.Random,
    guard: Callable[[str, str], bool] | None = None,
) -> List[Group]:
    groups: List[Group] = []
    for context in sorted(counters):
        if context not in thresholds:
            raise KeyError(
                f"Missing grouping threshold for context {context!r}. "
                "Add it to the pipeline thresholds map."
            )
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
