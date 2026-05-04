from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from canon_pipeline.layer_1_normalization import normalize_tag, tokenize


ANALYSIS_DIR = Path(__file__).resolve().parent / "analysis"
V4_INPUT_CSV = ANALYSIS_DIR / "canon_groups_v4.csv"
OUTPUT_CSV = ANALYSIS_DIR / "canon_groups_v5.csv"
SUMMARY_TXT = ANALYSIS_DIR / "canon_groups_v5_summary.txt"

EMBEDDING_MODEL = "all-mpnet-base-v2"
ENCODE_BATCH_SIZE = 64
SIMILARITY_THRESHOLD = 0.79
GENERIC_TOKEN_MAX_DF = 200
MAX_BUCKET_SIZE = 120
MAX_RESULT_GROUP_SIZE = 8
ELIGIBLE_MAX_MEMBER_COUNT = 3
MIN_AVG_JACCARD = 0.22
MIN_DOMINANT_COVERAGE = 0.6

TOKEN_SYNONYMS = {
    "games": "game",
    "mechanics": "mechanic",
    "options": "option",
    "systems": "system",
    "titles": "title",
}
PHRASE_SYNONYMS = {
    ("day", "night"): ("day", "night"),
    ("drag", "drop"): ("drag", "drop"),
    ("mini", "games"): ("mini", "game"),
    ("multi", "monitor"): ("multi", "monitor"),
    ("real", "time"): ("real", "time"),
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
    "system",
    "technical",
    "theme",
    "title",
    "tool",
    "usability",
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


class UnionFind:
    def __init__(self, values: list[int]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: int) -> int:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        self.parent[right_root] = left_root


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


def _row_concrete_tokens(row: GroupRow) -> tuple[str, ...]:
    tokens = Counter()
    for member_tag in row.member_tags or (row.canon_tag,):
        tokens.update(set(_concrete_tokens(member_tag)))
    tokens.update(set(_concrete_tokens(row.canon_tag)))
    return tuple(sorted(tokens))


def _semantic_text(row: GroupRow) -> str:
    examples = [member for member in row.member_tags if member != row.canon_tag][:3]
    parts = [normalize_tag(row.canon_tag)]
    if examples:
        parts.extend(normalize_tag(example) for example in examples)
    return " || ".join(parts)


def _pairwise_jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _average_pairwise_jaccard(token_sets: list[set[str]]) -> float:
    if len(token_sets) < 2:
        return 0.0
    scores: list[float] = []
    for index, left in enumerate(token_sets):
        for right in token_sets[index + 1 :]:
            scores.append(_pairwise_jaccard(left, right))
    return sum(scores) / len(scores) if scores else 0.0


def _dominant_token_coverage(token_sets: list[set[str]]) -> float:
    counts = Counter(token for token_set in token_sets for token in token_set)
    if not counts or not token_sets:
        return 0.0
    return max(counts.values()) / len(token_sets)


def _best_representative(rows: list[GroupRow], shared_tokens: tuple[str, ...]) -> str:
    preferred = set(shared_tokens)
    ordered = sorted(
        rows,
        key=lambda row: (
            -sum(1 for token in set(_row_concrete_tokens(row)) if token in preferred),
            -row.total_occurrences,
            len(_normalize_semantic_tokens(row.canon_tag)),
            len(row.canon_tag),
            row.canon_tag.lower(),
        ),
    )
    return normalize_tag(ordered[0].canon_tag) if ordered else ""


def _build_semantic_group(context: str, rows: list[GroupRow]) -> GroupRow:
    token_sets = [set(_row_concrete_tokens(row)) for row in rows]
    shared_tokens = tuple(
        sorted(
            token
            for token, count in Counter(token for token_set in token_sets for token in token_set).items()
            if count >= 2
        )
    )
    member_tags = tuple(sorted({member for row in rows for member in (row.member_tags or (row.canon_tag,))}))
    return GroupRow(
        context=context,
        canon_tag=_best_representative(rows, shared_tokens),
        final_tag="",
        member_count=len(member_tags),
        total_occurrences=sum(row.total_occurrences for row in rows),
        member_tags=member_tags,
        pattern_type="v5_semantic",
        anchor_tokens=shared_tokens,
    )


def _candidate_groups_for_context(context: str, rows: list[GroupRow], model: SentenceTransformer) -> tuple[list[GroupRow], set[int], dict[str, int]]:
    eligible_indexes = [index for index, row in enumerate(rows) if row.member_count <= ELIGIBLE_MAX_MEMBER_COUNT]
    if not eligible_indexes:
        return [], set(), {"eligible_rows": 0, "eligible_buckets": 0, "merged_groups": 0}

    row_token_sets = {index: set(_row_concrete_tokens(rows[index])) for index in eligible_indexes}
    token_df = Counter(token for tokens in row_token_sets.values() for token in tokens)
    buckets: dict[str, list[int]] = defaultdict(list)
    for index, token_set in row_token_sets.items():
        for token in token_set:
            if token_df[token] < 2 or token_df[token] > GENERIC_TOKEN_MAX_DF:
                continue
            buckets[token].append(index)

    eligible_buckets = {
        token: indexes
        for token, indexes in buckets.items()
        if 2 <= len(indexes) <= MAX_BUCKET_SIZE
    }

    print(
        f"V5 context start: context={context} eligible_rows={len(eligible_indexes)} "
        f"eligible_buckets={len(eligible_buckets)}"
    )

    union_find = UnionFind(eligible_indexes)
    for bucket_index, (token, indexes) in enumerate(sorted(eligible_buckets.items()), start=1):
        if bucket_index == 1 or bucket_index % 250 == 0 or bucket_index == len(eligible_buckets):
            print(
                f"V5 progress: context={context} bucket={bucket_index}/{len(eligible_buckets)} "
                f"token={token} bucket_size={len(indexes)}"
            )
        texts = [_semantic_text(rows[index]) for index in indexes]
        embeddings = model.encode(
            texts,
            batch_size=ENCODE_BATCH_SIZE,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        similarities = np.matmul(np.asarray(embeddings), np.asarray(embeddings).T)

        for left_position, left_index in enumerate(indexes):
            for right_position in range(left_position + 1, len(indexes)):
                right_index = indexes[right_position]
                if similarities[left_position, right_position] < SIMILARITY_THRESHOLD:
                    continue
                if _pairwise_jaccard(row_token_sets[left_index], row_token_sets[right_index]) < MIN_AVG_JACCARD:
                    continue
                union_find.union(left_index, right_index)

    grouped_indexes: dict[int, list[int]] = defaultdict(list)
    for index in eligible_indexes:
        grouped_indexes[union_find.find(index)].append(index)

    merged_rows: list[GroupRow] = []
    consumed_indexes: set[int] = set()
    for member_indexes in grouped_indexes.values():
        if len(member_indexes) < 2:
            continue
        candidate_rows = [rows[index] for index in member_indexes]
        token_sets = [set(_row_concrete_tokens(row)) for row in candidate_rows]
        if len({token for token_set in token_sets for token in token_set}) == 0:
            continue
        if _average_pairwise_jaccard(token_sets) < MIN_AVG_JACCARD:
            continue
        if _dominant_token_coverage(token_sets) < MIN_DOMINANT_COVERAGE:
            continue
        merged_group = _build_semantic_group(context, candidate_rows)
        if merged_group.member_count > MAX_RESULT_GROUP_SIZE:
            continue
        merged_rows.append(merged_group)
        consumed_indexes.update(member_indexes)

    stats = {
        "eligible_rows": len(eligible_indexes),
        "eligible_buckets": len(eligible_buckets),
        "merged_groups": len(merged_rows),
    }
    return merged_rows, consumed_indexes, stats


def _write_rows(csv_path: Path, rows: list[GroupRow]) -> None:
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
                ]
            )


def _write_summary(summary_path: Path, input_rows: list[GroupRow], output_rows: list[GroupRow], context_stats: dict[str, dict[str, int]], consumed_count: int) -> None:
    new_merges = sum(max(0, row.member_count - 1) for row in output_rows if row.pattern_type == "v5_semantic")
    summary_lines = [
        f"input_csv: {V4_INPUT_CSV}",
        f"rows_read: {len(input_rows)}",
        f"rows_written: {len(output_rows)}",
        f"consumed_source_rows: {consumed_count}",
        f"v5_semantic_groups: {sum(1 for row in output_rows if row.pattern_type == 'v5_semantic')}",
        f"new_merges: {new_merges}",
        f"contexts_analyzed: {len(context_stats)}",
    ]
    for context, stats in sorted(context_stats.items()):
        summary_lines.append(
            f"context={context} eligible_rows={stats['eligible_rows']} eligible_buckets={stats['eligible_buckets']} merged_groups={stats['merged_groups']}"
        )
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


def main() -> None:
    if not V4_INPUT_CSV.exists():
        raise FileNotFoundError(f"Missing v4 groups CSV: {V4_INPUT_CSV}")

    input_rows = _load_rows(V4_INPUT_CSV)
    rows_by_context: dict[str, list[GroupRow]] = defaultdict(list)
    for row in input_rows:
        rows_by_context[row.context].append(row)

    model = SentenceTransformer(EMBEDDING_MODEL)
    output_rows: list[GroupRow] = []
    consumed_count = 0
    context_stats: dict[str, dict[str, int]] = {}

    for context, context_rows in sorted(rows_by_context.items()):
        merged_rows, consumed_indexes, stats = _candidate_groups_for_context(context, context_rows, model)
        context_stats[context] = stats
        consumed_count += len(consumed_indexes)

        for index, row in enumerate(context_rows):
            if index not in consumed_indexes:
                output_rows.append(row)
        output_rows.extend(merged_rows)

    output_rows = sorted(
        output_rows,
        key=lambda row: (-row.member_count, -row.total_occurrences, row.context, row.canon_tag.lower()),
    )

    _write_rows(OUTPUT_CSV, output_rows)
    _write_summary(SUMMARY_TXT, input_rows, output_rows, context_stats, consumed_count)

    print(f"Rows read: {len(input_rows)}")
    print(f"Consumed source rows: {consumed_count}")
    print(f"V5 semantic groups: {sum(1 for row in output_rows if row.pattern_type == 'v5_semantic')}")
    print(f"V5 CSV: {OUTPUT_CSV}")
    print(f"Summary: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
