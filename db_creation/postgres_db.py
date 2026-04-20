#!/usr/bin/env python3

from db_creation.paths import final_canon_db_path, metadata_db_path
from db_creation.postgres.load_from_sqlite import postgres_dsn


METADATA_DB_PATH = metadata_db_path()
FINAL_CANON_DB_PATH = final_canon_db_path()


def print_run_configuration() -> None:
    print("Loading canonical SQLite data into Postgres")
    print(f"Metadata DB: {METADATA_DB_PATH}")
    print(f"Final canon DB: {FINAL_CANON_DB_PATH}")
    print(f"Postgres DSN set: {'yes' if postgres_dsn() else 'no'}")


def run_postgres_load() -> int:
    from db_creation.postgres.load_from_sqlite import main as load_main

    return load_main()


def main() -> int:
    print_run_configuration()
    return run_postgres_load()


if __name__ == "__main__":
    raise SystemExit(main())
