from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_CREATION_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(DB_CREATION_ROOT) not in sys.path:
    sys.path.insert(0, str(DB_CREATION_ROOT))

from db_creation.canon_pipeline.layer_1_normalization import format_display, normalize_tag, tokenize
from db_creation.canon_group_pipeline.diagnostics import (
    build_random_sample_section,
    write_stage_diagnostics,
)
from db_creation.paths import analysis_dir


ANALYSIS_DIR = analysis_dir()
V5_INPUT_CSV = ANALYSIS_DIR / "canon_groups_v5.csv"
OUTPUT_CSV = ANALYSIS_DIR / "canon_groups_v6.csv"
SUMMARY_TXT = ANALYSIS_DIR / "canon_groups_v6_summary.txt"

EMBEDDING_MODEL = "all-mpnet-base-v2"
ENCODE_BATCH_SIZE = 64
FAMILY_SIMILARITY_THRESHOLD = 0.68
MAX_NEIGHBORS = 5
MIN_BUCKET_SIZE = 2
MAX_BUCKET_SIZE = 160

TOKEN_SYNONYMS = {
    "games": "game",
    "mechanics": "mechanic",
    "options": "option",
    "systems": "system",
    "titles": "title",
    "roguelite": "roguelike",
}
PHRASE_SYNONYMS = {
    ("card", "roguelike"): ("deckbuilding", "roguelike"),
    ("deck", "building"): ("deckbuilding",),
    ("run", "based"): ("run-based",),
    ("meta", "progression"): ("meta-progression",),
    ("social", "sim"): ("social", "simulation"),
}
WRAPPER_TOKENS = {
    "a",
    "an",
    "and",
    "based",
    "driven",
    "focused",
    "for",
    "in",
    "of",
    "style",
    "styles",
    "system",
    "systems",
    "the",
    "with",
}
GENERIC_TOKENS = {
    "action",
    "challenge",
    "content",
    "design",
    "dynamic",
    "experience",
    "feature",
    "fun",
    "game",
    "gameplay",
    "issue",
    "mechanic",
    "mode",
    "option",
    "problem",
    "request",
    "simulation",
    "skill",
    "strategy",
    "technical",
    "theme",
    "title",
    "tool",
    "usability",
}
FAMILY_TAG_OVERRIDES = {
    "automation": "automation systems",
    "roguelike": "roguelike systems",
    "deckbuilding": "deckbuilding systems",
    "social": "social simulation systems",
    "progression": "progression systems",
}


@dataclass(frozen=True)
class GroupRow:
    context: str
    canon_tag: str
    final_tag: str
    member_count: int
    total_occurrences: int
    member_tags: tuple[str, ...]
    pattern_type: str
    anchor_tokens: tuple[str, ...]


@dataclass(frozen=True)
class EnrichedGroupRow:
    context: str
    canon_tag: str
    final_tag: str
    member_count: int
    total_occurrences: int
    member_tags: tuple[str, ...]
    pattern_type: str
    anchor_tokens: tuple[str, ...]
    family_anchor: str
    family_tag: str
    subfamily_tag: str
    family_confidence: float
    semantic_neighbors: tuple[str, ...]


def _parse_pipe_list(raw_value: str) -> tuple[str, ...]:
    if not raw_value:
        return tuple()
    return tuple(part.strip() for part in raw_value.split("|") if part.strip())


def _load_rows(csv_path: Path) -> list[GroupRow]:
    csv.field_size_limit(sys.maxsize)
    rows: list[GroupRow] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                GroupRow(
                    context=(row.get("context") or "").strip(),
                    canon_tag=(row.get("canon_tag") or "").strip(),
                    final_tag=(row.get("final_tag") or "").strip(),
                    member_count=int(row.get("member_count") or 0),
                    total_occurrences=int(row.get("total_occurrences") or 0),
                    member_tags=_parse_pipe_list(row.get("member_tags") or ""),
                    pattern_type=(row.get("pattern_type") or "").strip(),
                    anchor_tokens=_parse_pipe_list(row.get("anchor_tokens") or ""),
                )
            )
    return rows


def _normalize_semantic_tokens(tag: str) -> tuple[str, ...]:
    normalized_tokens = tokenize(normalize_tag(tag))
    collapsed: list[str] = []
    index = 0
    while index < len(normalized_tokens):
        if index + 1 < len(normalized_tokens):
            pair = (normalized_tokens[index], normalized_tokens[index + 1])
            if pair in PHRASE_SYNONYMS:
                collapsed.extend(PHRASE_SYNONYMS[pair])
                index += 2
                continue
        collapsed.append(TOKEN_SYNONYMS.get(normalized_tokens[index], normalized_tokens[index]))
        index += 1
    return tuple(collapsed)


def _concrete_tokens(tag: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in _normalize_semantic_tokens(tag)
        if token not in WRAPPER_TOKENS and token not in GENERIC_TOKENS
    )


def _row_token_counter(row: GroupRow) -> Counter[str]:
    counts: Counter[str] = Counter()
    tags = [row.canon_tag, row.final_tag, *row.member_tags]
    for tag in tags:
        counts.update(set(_concrete_tokens(tag)))
    counts.update(row.anchor_tokens)
    return counts


def _semantic_text(row: GroupRow) -> str:
    examples = [member for member in row.member_tags if member != row.canon_tag][:4]
    parts = [normalize_tag(row.canon_tag)]
    if row.final_tag and row.final_tag != row.canon_tag:
        parts.append(normalize_tag(row.final_tag))
    parts.extend(normalize_tag(example) for example in examples)
    if row.anchor_tokens:
        parts.append(" ".join(row.anchor_tokens))
    return " || ".join(part for part in parts if part)


def _shared_anchor(left: Counter[str], right: Counter[str]) -> bool:
    return any(token in right for token in left)


def _family_tag_from_anchor(anchor: str) -> str:
    if not anchor:
        return ""
    if anchor in FAMILY_TAG_OVERRIDES:
        return FAMILY_TAG_OVERRIDES[anchor]
    return format_display(anchor)


def _choose_family_anchor(component_rows: list[GroupRow]) -> str:
    counts: Counter[str] = Counter()
    for row in component_rows:
        counts.update(_row_token_counter(row))
    for token, count in counts.most_common():
        if count >= 2:
            return token
    if component_rows and component_rows[0].anchor_tokens:
        return component_rows[0].anchor_tokens[0]
    if component_rows:
        tokens = _concrete_tokens(component_rows[0].canon_tag)
        if tokens:
            return tokens[0]
    return ""


def _choose_subfamily_tag(base_row: GroupRow, neighbor_rows: list[GroupRow]) -> str:
    candidates = [base_row, *neighbor_rows]
    ordered = sorted(
        candidates,
        key=lambda row: (
            -row.total_occurrences,
            -row.member_count,
            len(_concrete_tokens(row.canon_tag)),
            len(row.canon_tag),
            row.canon_tag.lower(),
        ),
    )
    return ordered[0].canon_tag if ordered else base_row.canon_tag


def _row_bucket_tokens(row: GroupRow) -> tuple[str, ...]:
    token_counter = _row_token_counter(row)
    preferred = [token for token, count in token_counter.most_common() if count >= 2]
    if preferred:
        return tuple(preferred[:3])
    if row.anchor_tokens:
        return row.anchor_tokens[:3]
    return _concrete_tokens(row.canon_tag)[:3]


def _build_anchor_buckets(context_rows: list[GroupRow]) -> dict[str, list[int]]:
    buckets: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(context_rows):
        for token in _row_bucket_tokens(row):
            if token:
                buckets[token].append(index)
    return {
        token: indexes
        for token, indexes in buckets.items()
        if MIN_BUCKET_SIZE <= len(indexes) <= MAX_BUCKET_SIZE
    }


def _component_family_anchor(
    component_indexes: list[int],
    context_rows: list[GroupRow],
    token_counters: list[Counter[str]],
) -> str:
    counts: Counter[str] = Counter()
    for index in component_indexes:
        counts.update(token_counters[index])
    for token, count in counts.most_common():
        if count >= 2:
            return token
    if component_indexes:
        row = context_rows[component_indexes[0]]
        if row.anchor_tokens:
            return row.anchor_tokens[0]
        tokens = _concrete_tokens(row.canon_tag)
        if tokens:
            return tokens[0]
    return ""


def _build_enriched_rows(rows: list[GroupRow]) -> list[EnrichedGroupRow]:
    if not rows:
        return []

    model = SentenceTransformer(EMBEDDING_MODEL)
    rows_by_context: dict[str, list[GroupRow]] = defaultdict(list)
    for row in rows:
        rows_by_context[row.context].append(row)

    enriched: list[EnrichedGroupRow] = []

    for context, context_rows in sorted(rows_by_context.items()):
        texts = [_semantic_text(row) for row in context_rows]
        embeddings = np.asarray(
            model.encode(
                texts,
                batch_size=ENCODE_BATCH_SIZE,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        )
        token_counters = [_row_token_counter(row) for row in context_rows]
        anchor_buckets = _build_anchor_buckets(context_rows)

        print(
            f"V6 context start: context={context} rows={len(context_rows)} "
            f"anchor_buckets={len(anchor_buckets)}"
        )

        parent: list[int] = list(range(len(context_rows)))

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left: int, right: int) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parent[right_root] = left_root

        edge_scores: dict[tuple[int, int], float] = {}

        bucket_items = sorted(anchor_buckets.items())
        for bucket_index, (token, indexes) in enumerate(bucket_items, start=1):
            if bucket_index == 1 or bucket_index % 250 == 0 or bucket_index == len(bucket_items):
                print(
                    f"V6 progress: context={context} bucket={bucket_index}/{len(bucket_items)} "
                    f"token={token} bucket_size={len(indexes)}"
                )
            bucket_embeddings = embeddings[indexes]
            bucket_similarities = np.matmul(bucket_embeddings, bucket_embeddings.T)
            for left_position, left_index in enumerate(indexes):
                for right_position, right_index in enumerate(indexes[left_position + 1 :], start=left_position + 1):
                    similarity = float(bucket_similarities[left_position, right_position])
                    if similarity < FAMILY_SIMILARITY_THRESHOLD:
                        continue
                    if not _shared_anchor(token_counters[left_index], token_counters[right_index]):
                        continue
                    pair = (left_index, right_index) if left_index < right_index else (right_index, left_index)
                    if similarity > edge_scores.get(pair, 0.0):
                        edge_scores[pair] = similarity
                    union(left_index, right_index)

        component_indexes: dict[int, list[int]] = defaultdict(list)
        for index in range(len(context_rows)):
            component_indexes[find(index)].append(index)

        family_anchor_by_index: dict[int, str] = {}
        family_tag_by_index: dict[int, str] = {}
        subfamily_tag_by_index: dict[int, str] = {}
        component_confidence_by_index: dict[int, float] = {}
        for indexes in component_indexes.values():
            component_rows = [context_rows[index] for index in indexes]
            family_anchor = _component_family_anchor(indexes, context_rows, token_counters)
            family_tag = _family_tag_from_anchor(family_anchor)
            representative_row = sorted(
                component_rows,
                key=lambda row: (
                    -row.total_occurrences,
                    -row.member_count,
                    len(_concrete_tokens(row.canon_tag)),
                    len(row.canon_tag),
                    row.canon_tag.lower(),
                ),
            )[0]
            subfamily_tag = representative_row.canon_tag
            component_confidence = 0.0
            component_index_set = set(indexes)
            for (left_index, right_index), similarity in edge_scores.items():
                if left_index in component_index_set and right_index in component_index_set:
                    component_confidence = max(component_confidence, similarity)
            for index in indexes:
                family_anchor_by_index[index] = family_anchor
                family_tag_by_index[index] = family_tag
                subfamily_tag_by_index[index] = subfamily_tag
                component_confidence_by_index[index] = component_confidence

        neighbor_indexes: dict[int, list[tuple[int, float]]] = defaultdict(list)
        for (left_index, right_index), similarity in edge_scores.items():
            neighbor_indexes[left_index].append((right_index, similarity))
            neighbor_indexes[right_index].append((left_index, similarity))

        for index, row in enumerate(context_rows):
            neighbors = sorted(
                neighbor_indexes.get(index, []),
                key=lambda item: (-item[1], context_rows[item[0]].canon_tag.lower()),
            )[:MAX_NEIGHBORS]
            neighbor_rows = [context_rows[neighbor_index] for neighbor_index, _ in neighbors]
            family_anchor = family_anchor_by_index.get(index, "")
            family_tag = family_tag_by_index.get(index, "")
            subfamily_tag = subfamily_tag_by_index.get(index, row.canon_tag)
            family_confidence = component_confidence_by_index.get(index, neighbors[0][1] if neighbors else 0.0)
            semantic_neighbors = tuple(neighbor_row.canon_tag for neighbor_row in neighbor_rows)

            enriched.append(
                EnrichedGroupRow(
                    context=row.context,
                    canon_tag=row.canon_tag,
                    final_tag=row.final_tag,
                    member_count=row.member_count,
                    total_occurrences=row.total_occurrences,
                    member_tags=row.member_tags,
                    pattern_type=row.pattern_type,
                    anchor_tokens=row.anchor_tokens,
                    family_anchor=family_anchor,
                    family_tag=family_tag,
                    subfamily_tag=subfamily_tag,
                    family_confidence=family_confidence,
                    semantic_neighbors=semantic_neighbors,
                )
            )

    return sorted(
        enriched,
        key=lambda row: (-row.member_count, -row.total_occurrences, row.context, row.canon_tag.lower()),
    )


def _write_rows(csv_path: Path, rows: list[EnrichedGroupRow]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "context",
                "canon_tag",
                "final_tag",
                "member_count",
                "total_occurrences",
                "member_tags",
                "pattern_type",
                "anchor_tokens",
                "family_anchor",
                "family_tag",
                "subfamily_tag",
                "family_confidence",
                "semantic_neighbors",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.context,
                    row.canon_tag,
                    row.final_tag,
                    row.member_count,
                    row.total_occurrences,
                    " | ".join(row.member_tags),
                    row.pattern_type,
                    " | ".join(row.anchor_tokens),
                    row.family_anchor,
                    row.family_tag,
                    row.subfamily_tag,
                    f"{row.family_confidence:.4f}",
                    " | ".join(row.semantic_neighbors),
                ]
            )


def _write_summary(summary_path: Path, input_rows: list[GroupRow], output_rows: list[EnrichedGroupRow]) -> None:
    rows_with_family = sum(1 for row in output_rows if row.family_tag)
    rows_with_neighbors = sum(1 for row in output_rows if row.semantic_neighbors)
    metrics = [
        f"input_csv: {V5_INPUT_CSV}",
        f"rows_read: {len(input_rows)}",
        f"rows_written: {len(output_rows)}",
        f"embedding_model: {EMBEDDING_MODEL}",
        f"family_similarity_threshold: {FAMILY_SIMILARITY_THRESHOLD}",
        f"rows_with_family_tag: {rows_with_family}",
        f"rows_with_semantic_neighbors: {rows_with_neighbors}",
        "v6_status: bert_assisted_family_subfamily_proposals",
        "notes: v6 proposes family_tag and subfamily_tag for diagnostics; it does not alter live search",
    ]
    sample_section = build_random_sample_section(
        title="sample_groups",
        rows=output_rows,
        formatter=lambda row, index: [
            f"{index}. context={row.context} canon_tag={row.canon_tag} "
            f"family_tag={row.family_tag or '-'} subfamily_tag={row.subfamily_tag or '-'} "
            f"confidence={row.family_confidence:.4f} member_count={row.member_count} "
            f"total_occurrences={row.total_occurrences}",
            f"   anchor_tokens={' | '.join(row.anchor_tokens) if row.anchor_tokens else '-'}",
            f"   semantic_neighbors={' | '.join(row.semantic_neighbors) if row.semantic_neighbors else '-'}",
            f"   members={' | '.join(row.member_tags)}",
        ],
        sample_size=20,
        seed=0,
    )
    write_stage_diagnostics(summary_path, metrics=metrics, sections=[sample_section])


def main() -> None:
    if not V5_INPUT_CSV.exists():
        raise FileNotFoundError(f"Missing v5 groups CSV: {V5_INPUT_CSV}")

    input_rows = _load_rows(V5_INPUT_CSV)
    output_rows = _build_enriched_rows(input_rows)

    _write_rows(OUTPUT_CSV, output_rows)
    _write_summary(SUMMARY_TXT, input_rows, output_rows)

    print(f"Rows read: {len(input_rows)}")
    print(f"Rows written: {len(output_rows)}")
    print(f"Rows with family tag: {sum(1 for row in output_rows if row.family_tag)}")
    print("V6 status: bert_assisted_family_subfamily_proposals")
    print(f"V6 CSV: {OUTPUT_CSV}")
    print(f"Summary: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
