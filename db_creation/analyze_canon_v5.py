from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path


ANALYSIS_DIR = Path(__file__).resolve().parent / "analysis"
INPUT_CSV = ANALYSIS_DIR / "canon_groups_v5.csv"


def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Missing v5 groups CSV: {INPUT_CSV}")

    csv.field_size_limit(sys.maxsize)

    total_rows = 0
    total_member_tags = 0
    total_occurrences = 0
    bucket_group_counts = Counter({"singletons": 0, "pairs": 0, "triples": 0, "four_plus": 0})
    bucket_member_totals = Counter({"singletons": 0, "pairs": 0, "triples": 0, "four_plus": 0})
    bucket_occurrence_totals = Counter({"singletons": 0, "pairs": 0, "triples": 0, "four_plus": 0})
    context_row_counts: dict[str, int] = defaultdict(int)
    context_member_totals: dict[str, int] = defaultdict(int)

    with INPUT_CSV.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            total_rows += 1
            member_count = int(row.get("member_count") or 0)
            occurrences = int(row.get("total_occurrences") or 0)
            context = (row.get("context") or "").strip()
            total_member_tags += member_count
            total_occurrences += occurrences
            context_row_counts[context] += 1
            context_member_totals[context] += member_count

            if member_count <= 1:
                bucket = "singletons"
            elif member_count == 2:
                bucket = "pairs"
            elif member_count == 3:
                bucket = "triples"
            else:
                bucket = "four_plus"

            bucket_group_counts[bucket] += 1
            bucket_member_totals[bucket] += member_count
            bucket_occurrence_totals[bucket] += occurrences

    print(f"Input CSV: {INPUT_CSV}")
    print(f"Total groups: {total_rows}")
    print(f"Total member tags represented: {total_member_tags}")
    print(f"Total occurrences represented: {total_occurrences}")
    print()
    print("Bucket summary:")
    print(
        "singletons:"
        f" groups={bucket_group_counts['singletons']}"
        f" member_tags={bucket_member_totals['singletons']}"
        f" occurrences={bucket_occurrence_totals['singletons']}"
    )
    print(
        "pairs:"
        f" groups={bucket_group_counts['pairs']}"
        f" member_tags={bucket_member_totals['pairs']}"
        f" occurrences={bucket_occurrence_totals['pairs']}"
    )
    print(
        "triples:"
        f" groups={bucket_group_counts['triples']}"
        f" member_tags={bucket_member_totals['triples']}"
        f" occurrences={bucket_occurrence_totals['triples']}"
    )
    print(
        "4+:"
        f" groups={bucket_group_counts['four_plus']}"
        f" member_tags={bucket_member_totals['four_plus']}"
        f" occurrences={bucket_occurrence_totals['four_plus']}"
    )
    print()
    print("Top contexts by remaining groups:")
    for context, count in sorted(context_row_counts.items(), key=lambda item: (-item[1], item[0]))[:15]:
        print(f"{context}: groups={count} member_tags={context_member_totals[context]}")


if __name__ == "__main__":
    main()
