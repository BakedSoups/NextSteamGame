#!/usr/bin/env python3

from chroma_pipeline import run_chroma_migration
from paths import chroma_dir_path, final_canon_db_path


FINAL_DB_PATH = final_canon_db_path()
CHROMA_DIR_PATH = chroma_dir_path()


def _print_progress(update: dict) -> None:
    print(
        f"Chroma batch {update['batch_number']}: "
        f"{update['processed_rows']}/{update['total_rows']} game rows prepared"
    )


def main() -> int:
    print(f"Reading final canonical DB from {FINAL_DB_PATH}")
    print(f"Writing Chroma collection under {CHROMA_DIR_PATH}")
    summary = run_chroma_migration(
        final_db_path=FINAL_DB_PATH,
        chroma_dir_path=CHROMA_DIR_PATH,
        progress=_print_progress,
    )
    print(f"Status: {summary['status']}")
    print(f"Processed rows: {summary['processed_rows']}")
    print(f"Collection: {summary['collection_name']}")
    print(f"Output dir: {summary['chroma_dir_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
