#!/usr/bin/env python3

from __future__ import annotations

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "data" / "steam_initial_noncanon.db"


QUERY = """
WITH all_tags AS (
    SELECT value AS tag
    FROM raw_game_semantics, json_each(metadata_json, '$.micro_tags')

    UNION

    SELECT value AS tag
    FROM raw_game_semantics, json_each(metadata_json, '$.genre_tree.primary')

    UNION

    SELECT value AS tag
    FROM raw_game_semantics, json_each(metadata_json, '$.genre_tree.sub')

    UNION

    SELECT value AS tag
    FROM raw_game_semantics, json_each(metadata_json, '$.genre_tree.traits')
)
SELECT DISTINCT tag
FROM all_tags
WHERE tag IS NOT NULL AND tag <> ''
ORDER BY tag
"""


def main() -> None:
    connection = sqlite3.connect(DB_PATH)
    try:
        rows = connection.execute(QUERY).fetchall()
    finally:
        connection.close()

    for (tag,) in rows:
        print(tag)


if __name__ == "__main__":
    main()
