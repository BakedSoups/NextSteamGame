from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from db_creation.canon_group_pipeline.v7_experiment.ontology_v7 import TagPair
from db_creation.canon_group_pipeline.v7_experiment.ontology_v71 import (
    _normalized_for_equivalence,
    deterministic_decision,
    load_gold,
)
from db_creation.canon_pipeline.io import collect_batch_counters, iter_row_batches, merge_counter_maps
from db_creation.canon_pipeline.layer_1_normalization import format_display, normalize_tag
from db_creation.chroma_pipeline import run_chroma_migration
from db_creation.final_db import _sync_screenshots_into_final_db
from db_creation.final_pipeline import run_final_db_build
from db_creation.paths import analysis_dir, data_dir, initial_noncanon_db_path, metadata_db_path


V6_CSV = analysis_dir() / "canon_groups_v6.csv"
V71_CSV = analysis_dir() / "canon_groups_v71_safe.csv"
V71_SUMMARY = analysis_dir() / "canon_groups_v71_safe_summary.json"
V71_DB = data_dir() / "steam_final_canon_v71.db"
V71_CHROMA = data_dir() / "chroma_v71"
CSV_FIELDS = (
    "context", "canon_tag", "final_tag", "member_count", "total_occurrences",
    "member_tags", "pattern_type", "anchor_tokens", "family_anchor", "family_tag",
    "subfamily_tag", "family_confidence", "semantic_neighbors",
)


def _split_members(value: str) -> list[str]:
    return [part.strip() for part in value.split("|") if part.strip()]


def collect_occurrences(db_path: Path) -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for rows in iter_row_batches(db_path, 500):
        metadata_counts, vector_counts = collect_batch_counters(rows)
        merge_counter_maps(counts, metadata_counts)
        merge_counter_maps(counts, vector_counts)
    return dict(counts)


def _normalized_counts(raw_counts: dict[str, Counter[str]]) -> dict[str, Counter[str]]:
    result: dict[str, Counter[str]] = defaultdict(Counter)
    for context, counter in raw_counts.items():
        for tag, count in counter.items():
            result[context][normalize_tag(tag)] += count
    return dict(result)


def select_outcome(member: str, representative: str, context: str, gold: dict) -> tuple[str, str]:
    key = (normalize_tag(member), normalize_tag(representative))
    reviewed = gold.get(key)
    if reviewed is not None:
        if reviewed["equivalent"]:
            return format_display(reviewed.get("preferred") or member), "reviewed_merge"
        return format_display(member), "reviewed_keep"

    decision = deterministic_decision(TagPair(member, representative, context))
    if decision is not None and decision.equivalent:
        return format_display(_normalized_for_equivalence(member)), "deterministic_merge"
    if decision is not None:
        return format_display(member), f"blocked:{decision.blocker}"
    return format_display(member), "deferred_unreviewed"


def build_safe_groups_csv(
    *, source_csv: Path, output_csv: Path, noncanon_db: Path,
) -> dict:
    gold = load_gold()
    occurrence_counts = _normalized_counts(collect_occurrences(noncanon_db))
    groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    reasons: Counter[str] = Counter()
    seen_members: dict[str, set[str]] = defaultdict(set)

    with source_csv.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            context = row["context"]
            representative = (row.get("final_tag") or row.get("canon_tag") or "").strip()
            members = _split_members(row.get("member_tags") or "")
            if representative and representative not in members:
                members.append(representative)
            for member in members:
                normalized_member = normalize_tag(member)
                if not normalized_member or normalized_member in seen_members[context]:
                    continue
                seen_members[context].add(normalized_member)
                outcome, reason = select_outcome(member, representative, context, gold)
                groups[(context, outcome)].add(member)
                reasons[reason] += 1

    # Retain any source tag omitted by an earlier grouping stage.
    for context, counter in occurrence_counts.items():
        for normalized_member in counter:
            if normalized_member not in seen_members[context]:
                groups[(context, format_display(normalized_member))].add(normalized_member)
                reasons["source_tag_recovered"] += 1

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for (context, canonical), members in sorted(groups.items()):
            ordered_members = sorted(members, key=lambda value: (normalize_tag(value), value.lower()))
            occurrences = sum(occurrence_counts.get(context, {}).get(normalize_tag(member), 0)
                              for member in ordered_members)
            writer.writerow({
                "context": context,
                "canon_tag": canonical,
                "final_tag": canonical,
                "member_count": len(ordered_members),
                "total_occurrences": occurrences,
                "member_tags": " | ".join(ordered_members),
                "pattern_type": "v71_safe",
                "anchor_tokens": "",
                "family_anchor": "",
                "family_tag": "",
                "subfamily_tag": "",
                "family_confidence": "",
                "semantic_neighbors": "",
            })

    summary = {
        "source_groups": sum(1 for _ in source_csv.open(encoding="utf-8")) - 1,
        "source_unique_members": sum(len(values) for values in seen_members.values()),
        "v71_groups": len(groups),
        "decisions": dict(sorted(reasons.items())),
        "policy": "Only deterministic or manually reviewed equivalents merge; unresolved tags stay separate.",
        "output_csv": str(output_csv),
    }
    V71_SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _progress(prefix: str):
    def report(update: dict) -> None:
        print(f"{prefix} batch {update['batch_number']}: {update['processed_rows']}/{update['total_rows']}", flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build isolated safe-v7.1 SQLite and Chroma databases")
    parser.add_argument("--groups-only", action="store_true")
    parser.add_argument("--skip-groups", action="store_true")
    parser.add_argument("--skip-db", action="store_true")
    parser.add_argument("--skip-chroma", action="store_true")
    parser.add_argument("--output-db", type=Path, default=V71_DB)
    parser.add_argument("--chroma-dir", type=Path, default=V71_CHROMA)
    args = parser.parse_args()
    if args.groups_only and args.skip_groups:
        raise SystemExit("--groups-only and --skip-groups cannot be combined")

    if not args.skip_groups:
        summary = build_safe_groups_csv(
            source_csv=V6_CSV, output_csv=V71_CSV, noncanon_db=initial_noncanon_db_path(),
        )
        print(json.dumps(summary, indent=2), flush=True)
    if args.groups_only:
        return 0

    if not args.skip_db:
        db_summary = run_final_db_build(
            noncanon_db_path=initial_noncanon_db_path(),
            output_db_path=args.output_db,
            canon_groups_csv_path=V71_CSV,
            batch_size=500,
            progress=_progress("SQLite"),
        )
        db_summary["screenshot_rows"] = _sync_screenshots_into_final_db(
            metadata_db_path=metadata_db_path(), final_db_path=args.output_db,
        )
        print(json.dumps(db_summary, indent=2), flush=True)
    elif not args.output_db.exists():
        raise FileNotFoundError(f"Cannot skip DB build; missing {args.output_db}")

    if not args.skip_chroma:
        chroma_summary = run_chroma_migration(
            final_db_path=args.output_db,
            chroma_dir_path=args.chroma_dir,
            progress=_progress("Chroma"),
        )
        print(json.dumps(chroma_summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
