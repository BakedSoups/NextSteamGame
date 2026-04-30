from __future__ import annotations

from pathlib import Path

from paths import analysis_dir, initial_noncanon_db_path


DEFAULT_NONCANON_DB_PATH = initial_noncanon_db_path()
DEFAULT_ANALYSIS_DIR = analysis_dir()
DEFAULT_BATCH_SIZE = 500

METADATA_CONTEXTS = (
    "micro_tags",
    "signature_tag",
    "niche_anchors",
    "identity_tags",
    "setting_tags",
    "music_primary",
    "music_secondary",
    "genre_tree.primary",
    "genre_tree.sub",
    "genre_tree.sub_sub",
)

VECTOR_CONTEXTS = (
    "mechanics",
    "narrative",
    "vibe",
    "structure_loop",
)

METADATA_CSV_PATH = DEFAULT_ANALYSIS_DIR / "metadata_canon_full.csv"
VECTORS_CSV_PATH = DEFAULT_ANALYSIS_DIR / "vectors_canon_full.csv"
METADATA_LEFTOVERS_CSV_PATH = DEFAULT_ANALYSIS_DIR / "metadata_canon_leftovers.csv"
VECTORS_LEFTOVERS_CSV_PATH = DEFAULT_ANALYSIS_DIR / "vectors_canon_leftovers.csv"
SUMMARY_PATH = DEFAULT_ANALYSIS_DIR / "canon_export_summary.txt"
