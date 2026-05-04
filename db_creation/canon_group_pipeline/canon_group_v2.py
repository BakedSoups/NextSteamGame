from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from canon_pipeline.layer_1_normalization import normalize_tag, tokenize


ANALYSIS_DIR = Path(__file__).resolve().parent / "analysis"
INPUT_CSV = ANALYSIS_DIR / "canon_groups.csv"
OUTPUT_CSV = ANALYSIS_DIR / "canon_groups_v2.csv"
SUMMARY_TXT = ANALYSIS_DIR / "canon_groups_v2_summary.txt"

CORE_MIN_SIZE = 2
MIN_CORE_TOKENS = 2
TOKEN_SYNONYMS = {
    "contemporary": "modern",
    "current": "modern",
    "futuristic": "future",
}
PHRASE_SYNONYMS = {
    ("present", "day"): ("modern",),
    ("near", "future"): ("future",),
}
WRAPPER_TOKENS = {
    "a",
    "an",
    "area",
    "areas",
    "backdrop",
    "collection",
    "design",
    "environment",
    "environments",
    "experience",
    "experiences",
    "game",
    "games",
    "genre",
    "journey",
    "landscape",
    "location",
    "locations",
    "mode",
    "modes",
    "of",
    "place",
    "places",
    "realm",
    "realms",
    "series",
    "setting",
    "space",
    "spaces",
    "style",
    "styles",
    "theme",
    "themed",
    "type",
    "types",
    "universe",
    "variety",
    "visual",
    "visuals",
    "world",
    "worlds",
}


@dataclass(frozen=True)
class CanonRow:
    context: str
    canon_tag: str
    member_count: int
    total_occurrences: int
    member_tags: tuple[str, ...]


@dataclass(frozen=True)
class PatternCandidate:
    context: str
    canon_tag: str
    pattern_type: str
    pattern_key: str
    members: tuple[str, ...]
    total_occurrences: int

    @property
    def member_count(self) -> int:
        return len(self.members)


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
                    member_count=int(row.get("member_count") or 0),
                    total_occurrences=int(row.get("total_occurrences") or 0),
                    member_tags=_parse_member_tags(row.get("member_tags") or ""),
                )
            )
    return rows


def _collect_singletons(rows: list[CanonRow]) -> dict[str, list[CanonRow]]:
    singleton_rows: dict[str, list[CanonRow]] = defaultdict(list)
    for row in rows:
        if row.member_count != 1 or not row.canon_tag:
            continue
        singleton_rows[row.context].append(row)
    return singleton_rows


def _normalize_core_tokens(tokens: list[str]) -> list[str]:
    normalized: list[str] = []
    index = 0
    while index < len(tokens):
        if index + 1 < len(tokens):
            pair = (tokens[index], tokens[index + 1])
            if pair in PHRASE_SYNONYMS:
                normalized.extend(PHRASE_SYNONYMS[pair])
                index += 2
                continue
        normalized.append(TOKEN_SYNONYMS.get(tokens[index], tokens[index]))
        index += 1
    return normalized


def _concept_core(tag: str) -> str:
    tokens = _normalize_core_tokens(tokenize(normalize_tag(tag)))
    content_tokens = [token for token in tokens if token not in WRAPPER_TOKENS]
    if len(content_tokens) < MIN_CORE_TOKENS:
        return ""
    return " ".join(content_tokens)


def _mine_candidates(singleton_rows: dict[str, list[CanonRow]]) -> list[PatternCandidate]:
    core_buckets: dict[tuple[str, str], list[CanonRow]] = defaultdict(list)

    for context, rows in singleton_rows.items():
        for row in rows:
            core = _concept_core(row.canon_tag)
            if core:
                core_buckets[(context, core)].append(row)

    candidates: list[PatternCandidate] = []

    for (context, core), rows in sorted(core_buckets.items()):
        unique_tags = sorted({row.canon_tag for row in rows})
        if len(unique_tags) < CORE_MIN_SIZE:
            continue
        candidates.append(
            PatternCandidate(
                context=context,
                canon_tag=core,
                pattern_type="concept_core",
                pattern_key=core,
                members=tuple(unique_tags),
                total_occurrences=sum(row.total_occurrences for row in rows),
            )
        )

    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate.member_count,
            -candidate.total_occurrences,
            candidate.context,
            candidate.pattern_key,
        ),
    )


def _write_candidates(csv_path: Path, candidates: list[PatternCandidate]) -> None:
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
                "pattern_key",
            ]
        )
        for candidate in candidates:
            writer.writerow(
                [
                    candidate.context,
                    candidate.canon_tag,
                    "",
                    candidate.member_count,
                    candidate.total_occurrences,
                    " | ".join(candidate.members),
                    candidate.pattern_type,
                    candidate.pattern_key,
                ]
            )


def _write_summary(summary_path: Path, rows: list[CanonRow], candidates: list[PatternCandidate]) -> None:
    singleton_count = sum(1 for row in rows if row.member_count == 1)
    new_merges = sum(max(0, candidate.member_count - 1) for candidate in candidates)
    summary_lines = [
        f"input_csv: {INPUT_CSV}",
        f"rows_read: {len(rows)}",
        f"singleton_rows: {singleton_count}",
        f"v2_candidates: {len(candidates)}",
        f"new_merges: {new_merges}",
    ]
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Missing canon groups CSV: {INPUT_CSV}")

    rows = _load_rows(INPUT_CSV)
    singleton_rows = _collect_singletons(rows)
    candidates = _mine_candidates(singleton_rows)
    _write_candidates(OUTPUT_CSV, candidates)
    _write_summary(SUMMARY_TXT, rows, candidates)

    print(f"Rows read: {len(rows)}")
    print(f"Contexts with singleton analysis: {len(singleton_rows)}")
    print(f"V2 candidate groups: {len(candidates)}")
    print(f"New merges: {sum(max(0, candidate.member_count - 1) for candidate in candidates)}")
    print(f"V2 CSV: {OUTPUT_CSV}")
    print(f"Summary: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
