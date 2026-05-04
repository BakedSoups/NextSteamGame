from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from canon_pipeline.layer_1_normalization import normalize_tag, tokenize


ANALYSIS_DIR = Path(__file__).resolve().parent / "analysis"
V3_INPUT_CSV = ANALYSIS_DIR / "canon_groups_v3.csv"
OUTPUT_CSV = ANALYSIS_DIR / "canon_groups_v4.csv"
SUMMARY_TXT = ANALYSIS_DIR / "canon_groups_v4_summary.txt"

TARGET_CONTEXT = "niche_anchors"
MIN_GROUP_SIZE = 2
MIN_SHARED_CONCRETE_TOKENS = 1
MIN_PAIRWISE_JACCARD = 0.34
MIN_DOMINANT_TOKEN_COVERAGE = 0.66
MIN_LARGE_GROUP_SHARED_TOKENS = 2
LARGE_GROUP_SIZE = 6

TOKEN_SYNONYMS = {
    "games": "game",
    "mechanics": "mechanic",
    "options": "option",
    "systems": "system",
    "titles": "title",
}
PHRASE_SYNONYMS = {
    ("drag", "drop"): ("drag", "drop"),
    ("day", "night"): ("day", "night"),
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
    "mechanics",
    "mode",
    "option",
    "options",
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


def _shared_concrete_tokens(member_tags: tuple[str, ...]) -> tuple[str, ...]:
    counts = Counter(
        token
        for member_tag in member_tags
        for token in set(_concrete_tokens(member_tag))
    )
    return tuple(sorted(token for token, count in counts.items() if count >= 2))


def _tokenized_member_sets(member_tags: tuple[str, ...]) -> list[set[str]]:
    return [set(_concrete_tokens(member_tag)) for member_tag in member_tags]


def _pairwise_jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _average_pairwise_jaccard(member_tags: tuple[str, ...]) -> float:
    token_sets = _tokenized_member_sets(member_tags)
    if len(token_sets) < 2:
        return 0.0
    scores: list[float] = []
    for index, left in enumerate(token_sets):
        for right in token_sets[index + 1 :]:
            scores.append(_pairwise_jaccard(left, right))
    return sum(scores) / len(scores) if scores else 0.0


def _dominant_token_coverage(member_tags: tuple[str, ...]) -> float:
    token_counts = Counter(
        token
        for member_tag in member_tags
        for token in set(_concrete_tokens(member_tag))
    )
    if not token_counts or not member_tags:
        return 0.0
    return max(token_counts.values()) / len(member_tags)


def _best_representative(member_tags: tuple[str, ...], preferred_tokens: tuple[str, ...]) -> str:
    token_set = set(preferred_tokens)
    ordered = sorted(
        member_tags,
        key=lambda tag: (
            -sum(1 for token in set(_concrete_tokens(tag)) if token in token_set),
            len(_normalize_semantic_tokens(tag)),
            len(tag),
            tag.lower(),
        ),
    )
    return normalize_tag(ordered[0]) if ordered else ""


def _split_group(row: GroupRow) -> list[GroupRow]:
    token_counts = Counter(
        token
        for member_tag in row.member_tags
        for token in set(_concrete_tokens(member_tag))
    )
    split_tokens = [
        token
        for token, count in token_counts.most_common()
        if count >= 2
    ]
    if not split_tokens:
        return []

    assigned: set[str] = set()
    split_rows: list[GroupRow] = []
    for token in split_tokens:
        members = tuple(
            sorted(
                member_tag
                for member_tag in row.member_tags
                if member_tag not in assigned and token in set(_concrete_tokens(member_tag))
            )
        )
        if len(members) < MIN_GROUP_SIZE:
            continue
        assigned.update(members)
        shared_tokens = _shared_concrete_tokens(members)
        split_rows.append(
            GroupRow(
                context=row.context,
                canon_tag=_best_representative(members, shared_tokens or (token,)),
                final_tag="",
                member_count=len(members),
                total_occurrences=row.total_occurrences,
                member_tags=members,
                pattern_type="v4_split",
                anchor_tokens=shared_tokens or (token,),
            )
        )
    return split_rows


def _validate_niche_anchor_group(row: GroupRow) -> tuple[list[GroupRow], str]:
    shared_tokens = _shared_concrete_tokens(row.member_tags)
    average_jaccard = _average_pairwise_jaccard(row.member_tags)
    dominant_coverage = _dominant_token_coverage(row.member_tags)

    passes_small_group = (
        len(shared_tokens) >= MIN_SHARED_CONCRETE_TOKENS
        and average_jaccard >= MIN_PAIRWISE_JACCARD
        and dominant_coverage >= MIN_DOMINANT_TOKEN_COVERAGE
    )
    passes_large_group = (
        len(row.member_tags) < LARGE_GROUP_SIZE
        or (
            len(shared_tokens) >= MIN_LARGE_GROUP_SHARED_TOKENS
            and average_jaccard >= MIN_PAIRWISE_JACCARD
        )
    )

    if passes_small_group and passes_large_group:
        return (
            [
                GroupRow(
                    context=row.context,
                    canon_tag=_best_representative(row.member_tags, shared_tokens),
                    final_tag="",
                    member_count=row.member_count,
                    total_occurrences=row.total_occurrences,
                    member_tags=row.member_tags,
                    pattern_type="v4_validated",
                    anchor_tokens=shared_tokens,
                )
            ],
            "validated",
        )

    split_rows = _split_group(row)
    if split_rows:
        return split_rows, "split"

    return [], "rejected"


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


def _write_summary(summary_path: Path, input_rows: list[GroupRow], output_rows: list[GroupRow], validated: int, split: int, rejected: int) -> None:
    target_input = sum(1 for row in input_rows if row.context == TARGET_CONTEXT)
    target_output = sum(1 for row in output_rows if row.context == TARGET_CONTEXT)
    new_merges = sum(max(0, row.member_count - 1) for row in output_rows if row.context == TARGET_CONTEXT)
    summary_lines = [
        f"input_csv: {V3_INPUT_CSV}",
        f"rows_read: {len(input_rows)}",
        f"{TARGET_CONTEXT}_input_rows: {target_input}",
        f"{TARGET_CONTEXT}_output_rows: {target_output}",
        f"validated_groups: {validated}",
        f"split_groups: {split}",
        f"rejected_groups: {rejected}",
        f"new_merges: {new_merges}",
    ]
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


def main() -> None:
    if not V3_INPUT_CSV.exists():
        raise FileNotFoundError(f"Missing v3 groups CSV: {V3_INPUT_CSV}")

    input_rows = _load_rows(V3_INPUT_CSV)
    output_rows: list[GroupRow] = []
    validated = 0
    split = 0
    rejected = 0

    for row in input_rows:
        if row.context != TARGET_CONTEXT:
            output_rows.append(row)
            continue

        replacement_rows, verdict = _validate_niche_anchor_group(row)
        if verdict == "validated":
            validated += 1
        elif verdict == "split":
            split += 1
        else:
            rejected += 1
        output_rows.extend(replacement_rows)

    output_rows = sorted(
        output_rows,
        key=lambda row: (-row.member_count, -row.total_occurrences, row.context, row.canon_tag.lower()),
    )

    _write_rows(OUTPUT_CSV, output_rows)
    _write_summary(SUMMARY_TXT, input_rows, output_rows, validated, split, rejected)

    print(f"Rows read: {len(input_rows)}")
    print(f"{TARGET_CONTEXT} validated: {validated}")
    print(f"{TARGET_CONTEXT} split: {split}")
    print(f"{TARGET_CONTEXT} rejected: {rejected}")
    print(f"V4 CSV: {OUTPUT_CSV}")
    print(f"Summary: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
