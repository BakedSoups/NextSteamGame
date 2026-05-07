from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from db_creation.canon_pipeline.layer_1_normalization import normalize_tag, tokenize
from .diagnostics import write_stage_diagnostics


ANALYSIS_DIR = Path(__file__).resolve().parents[1] / "analysis"
INPUT_CSV = ANALYSIS_DIR / "canon_groups_v2.csv"
OUTPUT_CSV = ANALYSIS_DIR / "canon_groups_v3.csv"
SUMMARY_TXT = ANALYSIS_DIR / "canon_groups_v3_summary.txt"

EMBEDDING_MODEL = "all-mpnet-base-v2"
ENCODE_BATCH_SIZE = 128
SIMILARITY_THRESHOLD = 0.74
MIN_GROUP_SIZE = 2
MAX_BUCKET_SIZE = 200
MAX_ACCEPTED_GROUP_SIZE = 25
MIN_SHARED_ANCHORS_FOR_LARGE_GROUP = 2
LARGE_GROUP_THRESHOLD = 6
GENERIC_TOKEN_MAX_DF = 250
SKIP_CONTEXTS = {
    "music_primary",
    "music_secondary",
}

TOKEN_SYNONYMS = {
    "contemporary": "modern",
    "current": "modern",
    "futuristic": "future",
    "games": "game",
}
PHRASE_SYNONYMS = {
    ("present", "day"): ("modern",),
    ("near", "future"): ("future",),
    ("mini", "games"): ("mini", "game"),
}
WRAPPER_TOKENS = {
    "a",
    "an",
    "and",
    "backdrop",
    "collection",
    "environment",
    "environments",
    "for",
    "genre",
    "in",
    "landscape",
    "location",
    "locations",
    "of",
    "on",
    "realm",
    "realms",
    "series",
    "setting",
    "style",
    "styles",
    "theme",
    "themes",
    "universe",
    "variety",
    "with",
    "world",
    "worlds",
}


@dataclass(frozen=True)
class CanonRow:
    context: str
    canon_tag: str
    final_tag: str
    member_count: int
    total_occurrences: int
    member_tags: tuple[str, ...]
    pattern_type: str
    anchor_tokens: tuple[str, ...]


@dataclass(frozen=True)
class V3Candidate:
    context: str
    canon_tag: str
    member_count: int
    total_occurrences: int
    member_tags: tuple[str, ...]
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


def _parse_member_tags(raw_value: str) -> tuple[str, ...]:
    if not raw_value:
        return tuple()
    return tuple(tag.strip() for tag in raw_value.split("|") if tag.strip())


def _load_rows(csv_path: Path) -> list[CanonRow]:
    rows: list[CanonRow] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                CanonRow(
                    context=(row.get("context") or "").strip(),
                    canon_tag=(row.get("canon_tag") or "").strip(),
                    final_tag=(row.get("final_tag") or "").strip(),
                    member_count=int(row.get("member_count") or 0),
                    total_occurrences=int(row.get("total_occurrences") or 0),
                    member_tags=_parse_member_tags(row.get("member_tags") or ""),
                    pattern_type=(row.get("pattern_type") or "").strip(),
                    anchor_tokens=_parse_member_tags(row.get("anchor_tokens") or ""),
                )
            )
    return rows


def _normalize_semantic_tokens(tag: str) -> list[str]:
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
    return [token for token in collapsed if token and token not in WRAPPER_TOKENS]


def _semantic_token_sets(rows: list[CanonRow]) -> dict[int, tuple[str, ...]]:
    token_sets: dict[int, tuple[str, ...]] = {}
    for index, row in enumerate(rows):
        token_sets[index] = tuple(sorted(set(_normalize_semantic_tokens(row.canon_tag))))
    return token_sets


def _collect_v3_rows(rows: list[CanonRow]) -> dict[str, list[CanonRow]]:
    grouped: dict[str, list[CanonRow]] = defaultdict(list)
    for row in rows:
        if not row.canon_tag:
            continue
        grouped[row.context].append(row)
    return grouped


def _build_token_buckets(rows: list[CanonRow], token_sets: dict[int, tuple[str, ...]]) -> tuple[dict[str, list[int]], Counter]:
    token_df: Counter = Counter()
    for index in range(len(rows)):
        token_df.update(set(token_sets[index]))

    buckets: dict[str, list[int]] = defaultdict(list)
    for index in range(len(rows)):
        for token in token_sets[index]:
            if token_df[token] < 2 or token_df[token] > GENERIC_TOKEN_MAX_DF:
                continue
            buckets[token].append(index)
    return buckets, token_df


def _token_jaccard(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _select_canon_tag(rows: list[CanonRow], member_indexes: list[int]) -> str:
    ordered = sorted(
        (rows[index] for index in member_indexes),
        key=lambda row: (-row.total_occurrences, len(normalize_tag(row.canon_tag).split()), len(row.canon_tag), row.canon_tag.lower()),
    )
    return normalize_tag(ordered[0].canon_tag)


def _mine_context_candidates(context: str, rows: list[CanonRow], model: SentenceTransformer) -> tuple[list[V3Candidate], dict[str, int]]:
    if context in SKIP_CONTEXTS:
        return [], {
            "rows": len(rows),
            "eligible_buckets": 0,
            "processed_buckets": 0,
            "skipped_large_buckets": 0,
            "skipped_oversized_groups": 0,
            "skipped_weak_anchor_groups": 0,
            "candidates": 0,
        }

    token_sets = _semantic_token_sets(rows)
    buckets, token_df = _build_token_buckets(rows, token_sets)
    eligible_buckets = {
        token: indexes
        for token, indexes in buckets.items()
        if 2 <= len(indexes) <= MAX_BUCKET_SIZE
    }

    print(
        f"V3 context start: context={context} rows={len(rows)} "
        f"eligible_buckets={len(eligible_buckets)}"
    )
    print(f"V3 encoding context: context={context} rows={len(rows)}")

    context_texts = [normalize_tag(row.canon_tag) for row in rows]
    context_embeddings = np.asarray(
        model.encode(
            context_texts,
            batch_size=ENCODE_BATCH_SIZE,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    )

    union_find = UnionFind(list(range(len(rows))))
    processed_buckets = 0
    skipped_large_buckets = sum(1 for indexes in buckets.values() if len(indexes) > MAX_BUCKET_SIZE)
    skipped_oversized_groups = 0
    skipped_weak_anchor_groups = 0

    for token_index, (token, indexes) in enumerate(sorted(eligible_buckets.items()), start=1):
        if token_index == 1 or token_index % 250 == 0 or token_index == len(eligible_buckets):
            print(
                f"V3 progress: context={context} bucket={token_index}/{len(eligible_buckets)} "
                f"token={token} bucket_size={len(indexes)}"
            )

        bucket_embeddings = context_embeddings[indexes]
        similarities = np.matmul(bucket_embeddings, bucket_embeddings.T)

        for left_position, left_index in enumerate(indexes):
            for right_position in range(left_position + 1, len(indexes)):
                right_index = indexes[right_position]
                if similarities[left_position, right_position] < SIMILARITY_THRESHOLD:
                    continue
                jaccard = _token_jaccard(token_sets[left_index], token_sets[right_index])
                if jaccard < 0.5:
                    continue
                union_find.union(left_index, right_index)

        processed_buckets += 1

    grouped_indexes: dict[int, list[int]] = defaultdict(list)
    for index in range(len(rows)):
        grouped_indexes[union_find.find(index)].append(index)

    candidates: list[V3Candidate] = []
    for member_indexes in grouped_indexes.values():
        if len(member_indexes) < MIN_GROUP_SIZE:
            continue
        if len(member_indexes) > MAX_ACCEPTED_GROUP_SIZE:
            skipped_oversized_groups += 1
            continue

        anchor_token_counts = Counter(
            token
            for index in member_indexes
            for token in token_sets[index]
        )
        shared_anchor_tokens = tuple(
            sorted(
                token
                for token, count in anchor_token_counts.items()
                if count >= 2 and token_df[token] <= GENERIC_TOKEN_MAX_DF
            )
        )
        if len(member_indexes) >= LARGE_GROUP_THRESHOLD and len(shared_anchor_tokens) < MIN_SHARED_ANCHORS_FOR_LARGE_GROUP:
            skipped_weak_anchor_groups += 1
            continue

        candidate_rows = [rows[index] for index in member_indexes]
        candidate = V3Candidate(
            context=context,
            canon_tag=_select_canon_tag(rows, member_indexes),
            member_count=len(member_indexes),
            total_occurrences=sum(row.total_occurrences for row in candidate_rows),
            member_tags=tuple(sorted(row.canon_tag for row in candidate_rows)),
            anchor_tokens=shared_anchor_tokens,
        )
        candidates.append(candidate)

    stats = {
        "rows": len(rows),
        "eligible_buckets": len(eligible_buckets),
        "processed_buckets": processed_buckets,
        "skipped_large_buckets": skipped_large_buckets,
        "skipped_oversized_groups": skipped_oversized_groups,
        "skipped_weak_anchor_groups": skipped_weak_anchor_groups,
        "candidates": len(candidates),
    }
    return candidates, stats


def _build_output_rows(rows: list[CanonRow], candidates: list[V3Candidate]) -> tuple[list[CanonRow], int]:
    consumed_members = {
        (candidate.context, member)
        for candidate in candidates
        for member in candidate.member_tags
    }
    output_rows: list[CanonRow] = []
    consumed_count = 0

    for row in rows:
        if row.canon_tag and (row.context, row.canon_tag) in consumed_members:
            consumed_count += 1
            continue
        output_rows.append(row)

    rows_by_key = {(row.context, row.canon_tag): row for row in rows if row.canon_tag}
    for candidate in candidates:
        consumed_rows = [
            rows_by_key[(candidate.context, member)]
            for member in candidate.member_tags
            if (candidate.context, member) in rows_by_key
        ]
        merged_member_tags = tuple(
            sorted(
                {
                    member
                    for consumed_row in consumed_rows
                    for member in (consumed_row.member_tags or ((consumed_row.canon_tag,) if consumed_row.canon_tag else tuple()))
                }
            )
        )
        output_rows.append(
            CanonRow(
                context=candidate.context,
                canon_tag=candidate.canon_tag,
                final_tag="",
                member_count=len(merged_member_tags),
                total_occurrences=candidate.total_occurrences,
                member_tags=merged_member_tags,
                pattern_type="semantic_bucket",
                anchor_tokens=candidate.anchor_tokens,
            )
        )

    output_rows.sort(
        key=lambda row: (-row.member_count, -row.total_occurrences, row.context, row.canon_tag.lower()),
    )
    return output_rows, consumed_count


def _write_rows(csv_path: Path, rows: list[CanonRow]) -> None:
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


def _write_summary(summary_path: Path, rows: list[CanonRow], output_rows: list[CanonRow], candidates: list[V3Candidate], context_stats: dict[str, dict[str, int]], consumed_count: int) -> None:
    regroupable_rows = sum(1 for row in rows if row.canon_tag)
    group_merges = sum(max(0, candidate.member_count - 1) for candidate in candidates)
    total_eligible_buckets = sum(stats["eligible_buckets"] for stats in context_stats.values())
    total_processed_buckets = sum(stats["processed_buckets"] for stats in context_stats.values())
    total_skipped_large_buckets = sum(stats["skipped_large_buckets"] for stats in context_stats.values())
    total_skipped_oversized_groups = sum(stats["skipped_oversized_groups"] for stats in context_stats.values())
    total_skipped_weak_anchor_groups = sum(stats["skipped_weak_anchor_groups"] for stats in context_stats.values())

    metrics = [
        f"input_csv: {INPUT_CSV}",
        f"rows_read: {len(rows)}",
        f"rows_written: {len(output_rows)}",
        f"rows_evaluated_for_regrouping: {regroupable_rows}",
        f"consumed_source_rows: {consumed_count}",
        f"v3_candidates: {len(candidates)}",
        f"group_merges: {group_merges}",
        f"eligible_buckets: {total_eligible_buckets}",
        f"processed_buckets: {total_processed_buckets}",
        f"skipped_large_buckets: {total_skipped_large_buckets}",
        f"skipped_oversized_groups: {total_skipped_oversized_groups}",
        f"skipped_weak_anchor_groups: {total_skipped_weak_anchor_groups}",
    ]
    context_lines = [
        "context_stats:",
        *[
            f"{context}: rows={stats['rows']} eligible_buckets={stats['eligible_buckets']} "
            f"processed_buckets={stats['processed_buckets']} skipped_large_buckets={stats['skipped_large_buckets']} "
            f"skipped_oversized_groups={stats['skipped_oversized_groups']} skipped_weak_anchor_groups={stats['skipped_weak_anchor_groups']} "
            f"emitted_groups={stats['candidates']}"
            for context, stats in sorted(context_stats.items())
        ],
    ]
    write_stage_diagnostics(summary_path, metrics=metrics, sections=[context_lines])


def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Missing v2 groups CSV: {INPUT_CSV}")

    rows = _load_rows(INPUT_CSV)
    grouped_rows = _collect_v3_rows(rows)
    model = SentenceTransformer(EMBEDDING_MODEL)

    candidates: list[V3Candidate] = []
    context_stats: dict[str, dict[str, int]] = {}

    for context, context_rows in sorted(grouped_rows.items()):
        context_candidates, stats = _mine_context_candidates(context, context_rows, model)
        candidates.extend(context_candidates)
        context_stats[context] = stats

    candidates = sorted(
        candidates,
        key=lambda candidate: (-candidate.member_count, -candidate.total_occurrences, candidate.context, candidate.canon_tag),
    )

    output_rows, consumed_count = _build_output_rows(rows, candidates)
    _write_rows(OUTPUT_CSV, output_rows)
    _write_summary(SUMMARY_TXT, rows, output_rows, candidates, context_stats, consumed_count)

    print(f"Rows read: {len(rows)}")
    print(f"Rows written: {len(output_rows)}")
    print(f"Contexts analyzed: {len(grouped_rows)}")
    print(f"V3 candidate groups: {len(candidates)}")
    print(f"Consumed source rows: {consumed_count}")
    print(f"Group merges: {sum(max(0, candidate.member_count - 1) for candidate in candidates)}")
    print(f"V3 CSV: {OUTPUT_CSV}")
    print(f"Summary: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
