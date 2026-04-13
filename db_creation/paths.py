from __future__ import annotations

import os
from pathlib import Path


DB_CREATION_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = DB_CREATION_ROOT.parent


def _configured_dir(env_var: str, default: Path) -> Path:
    raw = os.getenv(env_var)
    if not raw:
        return default
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def data_dir() -> Path:
    return _configured_dir("DB_CREATION_DATA_DIR", PROJECT_ROOT / "data")


def analysis_dir() -> Path:
    return _configured_dir("DB_CREATION_ANALYSIS_DIR", DB_CREATION_ROOT / "analysis")


def metadata_db_path() -> Path:
    return data_dir() / "steam_metadata.db"


def initial_noncanon_db_path() -> Path:
    return data_dir() / "steam_initial_noncanon.db"


def final_canon_db_path() -> Path:
    return data_dir() / "steam_final_canon.db"


def insightful_words_path() -> Path:
    return DB_CREATION_ROOT / "insightful_words.json"


def sampled_game_tags_path() -> Path:
    return analysis_dir() / "sampled_game_tags.json"
