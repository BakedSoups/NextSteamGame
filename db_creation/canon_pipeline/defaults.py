from __future__ import annotations

from pathlib import Path

from db_creation.paths import analysis_dir, initial_noncanon_db_path


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

GROUPS_CSV_PATH = DEFAULT_ANALYSIS_DIR / "canon_groups.csv"
SUMMARY_PATH = DEFAULT_ANALYSIS_DIR / "canon_export_summary.txt"
