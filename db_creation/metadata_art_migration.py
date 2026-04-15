#!/usr/bin/env python3

from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

from paths import metadata_db_path


ART_COLUMNS: dict[str, str] = {
    "capsule_imagev5": "TEXT",
    "background_image": "TEXT",
    "background_image_raw": "TEXT",
    "logo_image": "TEXT",
    "icon_image": "TEXT",
    "library_hero_image": "TEXT",
    "library_capsule_image": "TEXT",
}


def first_non_empty(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return None


def extract_art_fields(app_data: dict[str, Any]) -> dict[str, Optional[str]]:
    return {
        "capsule_imagev5": first_non_empty(app_data.get("capsule_imagev5")),
        "background_image": first_non_empty(
            app_data.get("background_image"),
            app_data.get("background"),
        ),
        "background_image_raw": first_non_empty(
            app_data.get("background_image_raw"),
            app_data.get("background_raw"),
        ),
        "logo_image": first_non_empty(
            app_data.get("logo_image"),
            app_data.get("logo"),
        ),
        "icon_image": first_non_empty(
            app_data.get("icon_image"),
            app_data.get("icon"),
        ),
        "library_hero_image": first_non_empty(
            app_data.get("library_hero_image"),
            app_data.get("library_hero"),
        ),
        "library_capsule_image": first_non_empty(
            app_data.get("library_capsule_image"),
            app_data.get("library_capsule"),
        ),
    }


def ensure_columns(connection: sqlite3.Connection) -> list[str]:
    existing = {
        row[1]
        for row in connection.execute("PRAGMA table_info(games)").fetchall()
    }

    added: list[str] = []
    for column_name, column_type in ART_COLUMNS.items():
        if column_name in existing:
            continue
        connection.execute(f"ALTER TABLE games ADD COLUMN {column_name} {column_type}")
        added.append(column_name)
    return added


def backfill_art_fields(connection: sqlite3.Connection) -> tuple[int, dict[str, int]]:
    rows = connection.execute(
        """
        SELECT appid, payload_json
        FROM raw_steam_app_details
        WHERE region_code = 'us' AND success = 1
        ORDER BY appid
        """
    ).fetchall()

    updated_rows = 0
    populated_counts = {column_name: 0 for column_name in ART_COLUMNS}

    for appid, payload_json in rows:
        payload = json.loads(payload_json)
        wrapper = payload.get(str(appid), {})
        app_data = wrapper.get("data") or {}
        art = extract_art_fields(app_data)
        if not any(art.values()):
            continue

        result = connection.execute(
            """
            UPDATE games
            SET capsule_imagev5 = COALESCE(?, capsule_imagev5),
                background_image = COALESCE(?, background_image),
                background_image_raw = COALESCE(?, background_image_raw),
                logo_image = COALESCE(?, logo_image),
                icon_image = COALESCE(?, icon_image),
                library_hero_image = COALESCE(?, library_hero_image),
                library_capsule_image = COALESCE(?, library_capsule_image)
            WHERE appid = ?
            """,
            (
                art["capsule_imagev5"],
                art["background_image"],
                art["background_image_raw"],
                art["logo_image"],
                art["icon_image"],
                art["library_hero_image"],
                art["library_capsule_image"],
                appid,
            ),
        )
        if result.rowcount:
            updated_rows += 1
            for column_name, value in art.items():
                if value:
                    populated_counts[column_name] += 1

    return updated_rows, populated_counts


def main() -> int:
    db_path = metadata_db_path()
    print(f"Extending metadata DB art columns in {db_path}")

    connection = sqlite3.connect(db_path)
    try:
        added = ensure_columns(connection)
        updated_rows, populated_counts = backfill_art_fields(connection)
        connection.commit()
    finally:
        connection.close()

    if added:
        print("Added columns:")
        for column_name in added:
            print(f"- {column_name}")
    else:
        print("No schema changes needed; art columns already exist.")

    print(f"Backfilled art fields for {updated_rows} games from stored Steam appdetails payloads.")
    print("Populated columns:")
    for column_name in ART_COLUMNS:
        print(f"- {column_name}: {populated_counts[column_name]}")

    if not any(populated_counts[column_name] for column_name in ("logo_image", "icon_image", "library_hero_image", "library_capsule_image")):
        print(
            "Steam appdetails payloads in the current pipeline do not include logo/icon/library assets, "
            "so those columns remain empty until a separate ingestion step is added."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
