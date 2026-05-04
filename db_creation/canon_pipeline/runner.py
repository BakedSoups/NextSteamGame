from __future__ import annotations

import time
from collections import Counter
from pathlib import Path
from typing import Callable

from .defaults import (
    DEFAULT_ANALYSIS_DIR,
    DEFAULT_BATCH_SIZE,
    DEFAULT_NONCANON_DB_PATH,
    GROUPS_CSV_PATH,
    SUMMARY_PATH,
)
from .exporters import write_groups_csv, write_summary
from .io import collect_batch_counters, count_rows, empty_metadata_counters, empty_vector_counters, iter_row_batches, merge_counter_maps
from .layer_2_surface_merge import collapse_exact_normalized
from .layer_3_phrase_merge import merge_surface_variants
from .layer_4_family_merge import merge_family_variants
from .representatives import build_group
from .types import LeftoverRow


def run_canon_export(
    *,
    noncanon_db_path: Path = DEFAULT_NONCANON_DB_PATH,
    analysis_output_dir: Path = DEFAULT_ANALYSIS_DIR,
    batch_size: int = DEFAULT_BATCH_SIZE,
    progress: Callable[[dict], None] | None = None,
) -> dict:
    start = time.time()
    total_rows = count_rows(noncanon_db_path)
    metadata_counters = empty_metadata_counters()
    vector_counters = empty_vector_counters()

    processed_rows = 0
    batch_count = 0
    for rows in iter_row_batches(noncanon_db_path, batch_size):
        batch_count += 1
        processed_rows += len(rows)
        batch_metadata, batch_vectors = collect_batch_counters(rows)
        merge_counter_maps(metadata_counters, batch_metadata)
        merge_counter_maps(vector_counters, batch_vectors)
        if progress:
            progress(
                {
                    "batch_number": batch_count,
                    "processed_rows": processed_rows,
                    "total_rows": total_rows,
                    "metadata_unique_tags": sum(len(counter) for counter in metadata_counters.values()),
                    "vector_unique_tags": sum(len(counter) for counter in vector_counters.values()),
                }
            )

    metadata_groups, metadata_leftovers = _build_groups(metadata_counters)
    vector_groups, vector_leftovers = _build_groups(vector_counters)
    all_groups = sorted(
        metadata_groups + vector_groups,
        key=lambda group: (-group.member_count, -group.total_occurrences, group.context, group.representative_tag.lower()),
    )

    groups_csv = analysis_output_dir / GROUPS_CSV_PATH.name
    summary_path = analysis_output_dir / SUMMARY_PATH.name

    write_groups_csv(groups_csv, all_groups)
    write_summary(
        summary_path,
        [
            f"processed_rows: {processed_rows}",
            f"batch_count: {batch_count}",
            f"metadata_groups: {len(metadata_groups)}",
            f"vector_groups: {len(vector_groups)}",
            f"metadata_leftovers: {len(metadata_leftovers)}",
            f"vector_leftovers: {len(vector_leftovers)}",
            f"total_groups: {len(all_groups)}",
            f"elapsed_seconds: {round(time.time() - start, 2)}",
        ],
    )

    return {
        "processed_rows": processed_rows,
        "batch_count": batch_count,
        "metadata_unique_tags": sum(len(counter) for counter in metadata_counters.values()),
        "vector_unique_tags": sum(len(counter) for counter in vector_counters.values()),
        "metadata_contexts": len(metadata_counters),
        "vector_contexts": len(vector_counters),
        "metadata_groups": len(metadata_groups),
        "vector_groups": len(vector_groups),
        "metadata_leftovers": len(metadata_leftovers),
        "vector_leftovers": len(vector_leftovers),
        "total_groups": len(all_groups),
        "groups_csv_path": str(groups_csv),
        "summary_path": str(summary_path),
        "elapsed_seconds": round(time.time() - start, 2),
    }


def _build_groups(counter_map: dict[str, Counter]) -> tuple[list, list[LeftoverRow]]:
    groups = []
    leftovers: list[LeftoverRow] = []
    for context, counter in counter_map.items():
        print(f"Canon grouping start: context={context} raw_tags={len(counter)}")
        collapsed, raw_members = collapse_exact_normalized(counter)
        print(f"Canon layer 2 complete: context={context} groups={len(collapsed)}")
        collapsed, raw_members = merge_surface_variants(collapsed, raw_members)
        print(f"Canon layer 3 complete: context={context} groups={len(collapsed)}")
        collapsed, raw_members = merge_family_variants(collapsed, raw_members)
        print(f"Canon layer 4 complete: context={context} groups={len(collapsed)}")
        for normalized_tag, total_occurrences in sorted(collapsed.items()):
            raw_counts = raw_members.get(normalized_tag, Counter())
            groups.append(build_group(context, normalized_tag, total_occurrences, raw_counts))
            if len(raw_counts) <= 1:
                leftovers.append(
                    LeftoverRow(
                        context=context,
                        representative_tag=normalized_tag,
                        total_occurrences=total_occurrences,
                        members=sorted(raw_counts) or [normalized_tag],
                    )
                )
        print(
            f"Canon grouping complete: context={context} "
            f"export_groups={len([group for group in groups if group.context == context])}"
        )
    return groups, leftovers
