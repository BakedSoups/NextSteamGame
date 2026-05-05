#!/usr/bin/env python3

import sqlite3

from paths import analysis_dir, final_canon_db_path, initial_noncanon_db_path, metadata_db_path

NONCANON_DB_PATH = initial_noncanon_db_path()
OUTPUT_DB_PATH = final_canon_db_path()
METADATA_DB_PATH = metadata_db_path()
ANALYSIS_DIR = analysis_dir()
CANON_GROUPS_CSV_PATH = ANALYSIS_DIR / "canon_groups_v5.csv"
BATCH_SIZE = 500


def print_batch_progress(update: dict) -> None:
    print(
        f"Store batch {update['batch_number']}: "
        f"{update['processed_rows']}/{update['total_rows']} canonical game rows written"
    )


def _load_screenshot_rows(metadata_connection: sqlite3.Connection) -> list[tuple[int, int, str, str]]:
    metadata_connection.row_factory = sqlite3.Row
    rows = metadata_connection.execute(
        """
        SELECT
            gs.appid,
            gs.screenshot_id,
            COALESCE(gs.path_thumbnail, '') AS path_thumbnail,
            COALESCE(gs.path_full, '') AS path_full
        FROM game_screenshots gs
        INNER JOIN games g ON g.appid = gs.appid
        ORDER BY gs.appid, gs.screenshot_id
        """
    ).fetchall()
    return [
        (
            int(row["appid"]),
            int(row["screenshot_id"]),
            str(row["path_thumbnail"]),
            str(row["path_full"]),
        )
        for row in rows
    ]


def _sync_screenshots_into_final_db(*, metadata_db_path, final_db_path) -> int:
    metadata_connection = sqlite3.connect(metadata_db_path)
    final_connection = sqlite3.connect(final_db_path)
    try:
        screenshot_rows = _load_screenshot_rows(metadata_connection)
        final_connection.execute(
            """
            CREATE TABLE IF NOT EXISTS game_screenshots (
                appid INTEGER NOT NULL,
                screenshot_id INTEGER NOT NULL,
                path_thumbnail TEXT,
                path_full TEXT,
                PRIMARY KEY (appid, screenshot_id),
                FOREIGN KEY (appid) REFERENCES canonical_game_semantics(appid) ON DELETE CASCADE
            )
            """
        )
        final_connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_game_screenshots_appid
            ON game_screenshots (appid)
            """
        )
        final_connection.execute("DELETE FROM game_screenshots")
        final_connection.executemany(
            """
            INSERT INTO game_screenshots (
                appid,
                screenshot_id,
                path_thumbnail,
                path_full
            )
            SELECT ?, ?, ?, ?
            WHERE EXISTS (
                SELECT 1
                FROM canonical_game_semantics
                WHERE appid = ?
            )
            """,
            [
                (
                    appid,
                    screenshot_id,
                    path_thumbnail,
                    path_full,
                    appid,
                )
                for appid, screenshot_id, path_thumbnail, path_full in screenshot_rows
            ],
        )
        final_connection.commit()
        row = final_connection.execute("SELECT COUNT(*) FROM game_screenshots").fetchone()
        stored_count = int(row[0]) if row else 0
    finally:
        metadata_connection.close()
        final_connection.close()

    print(f"Metadata DB: {metadata_db_path}")
    print(f"Final DB: {final_db_path}")
    print(f"Stored screenshot rows: {stored_count}")
    print("Screenshot sync complete.")
    return stored_count


def run_final_build() -> dict:
    from final_pipeline import run_final_db_build

    summary = run_final_db_build(
        noncanon_db_path=NONCANON_DB_PATH,
        output_db_path=OUTPUT_DB_PATH,
        canon_groups_csv_path=CANON_GROUPS_CSV_PATH,
        batch_size=BATCH_SIZE,
        progress=print_batch_progress,
    )
    screenshot_rows = _sync_screenshots_into_final_db(
        metadata_db_path=METADATA_DB_PATH,
        final_db_path=OUTPUT_DB_PATH,
    )
    summary["screenshot_rows"] = screenshot_rows
    return summary


def print_run_configuration() -> None:
    print(f"Building final canonical DB from {NONCANON_DB_PATH}")
    print(f"Output DB: {OUTPUT_DB_PATH}")
    print(f"Canon groups CSV: {CANON_GROUPS_CSV_PATH}")
    print(f"Batch size: {BATCH_SIZE}")


def print_run_summary(summary: dict) -> None:
    print(f"Run {summary['run_id']} finished with status: {summary['status']}")
    print(f"Processed rows: {summary['processed_rows']}")
    print(f"Canon groups: {summary['canon_groups']}")
    print(f"Screenshots: {summary.get('screenshot_rows', 0)}")
    print(f"Final DB: {summary['output_db_path']}")


def main() -> int:
    print_run_configuration()
    summary = run_final_build()
    print_run_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
