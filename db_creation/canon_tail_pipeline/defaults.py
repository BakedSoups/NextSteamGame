from __future__ import annotations

from paths import analysis_dir


DEFAULT_ANALYSIS_DIR = analysis_dir()
METADATA_LEFTOVERS_CSV_PATH = DEFAULT_ANALYSIS_DIR / "metadata_canon_leftovers.csv"
VECTORS_LEFTOVERS_CSV_PATH = DEFAULT_ANALYSIS_DIR / "vectors_canon_leftovers.csv"
METADATA_TAIL_CSV_PATH = DEFAULT_ANALYSIS_DIR / "metadata_canon_tail.csv"
VECTORS_TAIL_CSV_PATH = DEFAULT_ANALYSIS_DIR / "vectors_canon_tail.csv"
SUMMARY_PATH = DEFAULT_ANALYSIS_DIR / "canon_tail_export_summary.txt"
