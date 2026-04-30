#!/usr/bin/env python3

from paths import analysis_dir

ANALYSIS_DIR = analysis_dir()


def main() -> int:
    from canon_tail_pipeline.runner import run_canon_tail_export

    summary = run_canon_tail_export(analysis_output_dir=ANALYSIS_DIR)
    print(f"Metadata tail rows out: {summary['metadata_tail_rows_out']}")
    print(f"Vector tail rows out: {summary['vector_tail_rows_out']}")
    print(f"Metadata tail CSV: {summary['metadata_tail_csv_path']}")
    print(f"Vector tail CSV: {summary['vector_tail_csv_path']}")
    print(f"Summary: {summary['summary_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
