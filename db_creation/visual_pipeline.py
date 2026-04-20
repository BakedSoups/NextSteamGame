#!/usr/bin/env python3

from pathlib import Path

from paths import metadata_db_path
from visual_stage.pipeline import (
    DEFAULT_CLEANUP_MODEL,
    DEFAULT_GAME_NAME,
    DEFAULT_MODEL_NAME,
    print_visual_probe_json,
)


GAME_NAME = DEFAULT_GAME_NAME
METADATA_DB_PATH = metadata_db_path()
MODEL_NAME = DEFAULT_MODEL_NAME
CLEANUP_MODEL = DEFAULT_CLEANUP_MODEL
USE_OPENAI_CLEANUP = True


def print_run_configuration() -> None:
    print(f"Running visual probe for: {GAME_NAME}")
    print(f"Metadata DB: {METADATA_DB_PATH}")
    print(f"Model: {MODEL_NAME}")
    print(f"OpenAI cleanup: {'on' if USE_OPENAI_CLEANUP else 'off'}")
    if USE_OPENAI_CLEANUP:
        print(f"Cleanup model: {CLEANUP_MODEL}")


def run_visual_pipeline() -> None:
    print_visual_probe_json(
        game_name=GAME_NAME,
        db_path=Path(METADATA_DB_PATH),
        model_name=MODEL_NAME,
        cleanup_model=CLEANUP_MODEL,
        use_openai_cleanup=USE_OPENAI_CLEANUP,
    )


def main() -> int:
    print_run_configuration()
    run_visual_pipeline()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
