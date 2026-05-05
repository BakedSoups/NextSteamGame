#!/usr/bin/env python3

import sys
from urllib.parse import urlsplit

from paths import final_canon_db_path, metadata_db_path
from postgres.load_from_sqlite import postgres_dsn


METADATA_DB_PATH = metadata_db_path()
FINAL_CANON_DB_PATH = final_canon_db_path()


def format_dsn_target(dsn: str) -> str:
    parsed = urlsplit(dsn)
    username = parsed.username or ""
    hostname = parsed.hostname or ""
    port = parsed.port or ""
    database = parsed.path.lstrip("/")
    user_prefix = f"{username}@" if username else ""
    port_suffix = f":{port}" if port else ""
    database_suffix = f"/{database}" if database else ""
    return f"{user_prefix}{hostname}{port_suffix}{database_suffix}"


def print_connection_hint(dsn: str) -> None:
    target = format_dsn_target(dsn)
    print()
    print(f"Postgres connection failed for target: {target}", file=sys.stderr)
    print("If you are using the Docker stack, start Postgres first:", file=sys.stderr)
    print("  docker compose up -d postgres", file=sys.stderr)
    print("Then rerun:", file=sys.stderr)
    print("  python db_creation/postgres_db.py", file=sys.stderr)
    print("Or load fully inside Docker:", file=sys.stderr)
    print("  docker compose --profile loader run --rm postgres_loader", file=sys.stderr)


def print_run_configuration() -> None:
    dsn = postgres_dsn()
    print("Building final canonical DB with screenshots, then loading into Postgres")
    print(f"Metadata DB: {METADATA_DB_PATH}")
    print(f"Final canon DB: {FINAL_CANON_DB_PATH}")
    print(f"Postgres target: {format_dsn_target(dsn)}")


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
    try:
        return run_postgres_load(reset_all=reset_all)
    except Exception as exc:
        message = str(exc).lower()
        if "connection refused" in message or "connection failed" in message:
            print_connection_hint(postgres_dsn())
        raise


if __name__ == "__main__":
    raise SystemExit(main())
