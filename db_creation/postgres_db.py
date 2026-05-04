#!/usr/bin/env python3

from paths import final_canon_db_path, metadata_db_path
from postgres.load_from_sqlite import postgres_dsn


METADATA_DB_PATH = metadata_db_path()
FINAL_CANON_DB_PATH = final_canon_db_path()


def print_run_configuration() -> None:
    print("Building final canonical DB with screenshots, then loading into Postgres")
    print(f"Metadata DB: {METADATA_DB_PATH}")
    print(f"Final canon DB: {FINAL_CANON_DB_PATH}")
    print(f"Postgres DSN set: {'yes' if postgres_dsn() else 'no'}")


def confirm_postgres_reset() -> bool:
    response = input("Delete previous Postgres instance data, including diagnostics? [y/N]: ").strip().lower()
    return response in {"y", "yes"}


def run_final_build() -> dict:
    from final_db import run_final_build as build_final_db

    return build_final_db()


def run_postgres_load(*, reset_all: bool) -> int:
    from postgres.load_from_sqlite import main as load_main

    return load_main(reset_all=reset_all)


def main() -> int:
    print_run_configuration()
    reset_all = confirm_postgres_reset()
    build_summary = run_final_build()
    print(
        f"Final DB rebuilt: rows={build_summary['processed_rows']} screenshots={build_summary.get('screenshot_rows', 0)}"
    )
    return run_postgres_load(reset_all=reset_all)


if __name__ == "__main__":
    raise SystemExit(main())
