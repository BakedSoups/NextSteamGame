from pathlib import Path

from db_creation import paths


def test_final_canon_path_can_be_overridden(monkeypatch):
    monkeypatch.setenv("STEAM_REC_FINAL_CANON_DB_PATH", "/tmp/test-final-v71.db")
    assert paths.final_canon_db_path() == Path("/tmp/test-final-v71.db")


def test_chroma_path_can_be_overridden(monkeypatch):
    monkeypatch.setenv("STEAM_REC_CHROMA_DIR_PATH", "/tmp/test-chroma-v71")
    assert paths.chroma_dir_path() == Path("/tmp/test-chroma-v71")
