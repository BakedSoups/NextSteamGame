#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_project_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip("\"'")


def postgres_dsn() -> str:
    load_project_env()
    value = os.getenv("STEAM_REC_POSTGRES_DSN")
    if not value:
        raise RuntimeError("STEAM_REC_POSTGRES_DSN is not set")
    return value


def main() -> int:
    import psycopg
    from psycopg.rows import dict_row

    dsn = postgres_dsn()

    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM ui_diagnostics")
            total = int(cursor.fetchone()["total"])

            cursor.execute(
                """
                SELECT event_type, COUNT(*) AS count
                FROM ui_diagnostics
                GROUP BY event_type
                ORDER BY count DESC, event_type
                """
            )
            event_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    COALESCE(NULLIF(game_name, ''), '(unknown)') AS game_name,
                    appid,
                    COUNT(*) AS count
                FROM ui_diagnostics
                GROUP BY game_name, appid
                ORDER BY count DESC, game_name
                LIMIT 20
                """
            )
            top_games = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    COALESCE(NULLIF(game_name, ''), '(unknown)') AS game_name,
                    appid,
                    COUNT(*) AS count
                FROM ui_diagnostics
                WHERE event_type IN (
                    'opened_recommendation_on_steam',
                    'opened_game_on_steam_without_insightful_reviews'
                )
                GROUP BY game_name, appid
                ORDER BY count DESC, game_name
                LIMIT 20
                """
            )
            top_opened_games = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    COALESCE(NULLIF(game_name, ''), '(unknown)') AS game_name,
                    appid,
                    COUNT(*) AS count
                FROM ui_diagnostics
                WHERE event_type = 'selected_game_from_search'
                GROUP BY game_name, appid
                ORDER BY count DESC, game_name
                LIMIT 20
                """
            )
            top_selected_games = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    id,
                    created_at,
                    event_type,
                    appid,
                    game_name,
                    details
                FROM ui_diagnostics
                ORDER BY created_at DESC, id DESC
                LIMIT 30
                """
            )
            recent_rows = cursor.fetchall()

    print("Diagnostics Summary")
    print(f"Total rows: {total}")
    print()

    print("By event type")
    if not event_rows:
        print("- none")
    else:
        for row in event_rows:
            print(f"- {row['event_type']}: {row['count']}")
    print()

    print("Top games")
    if not top_games:
        print("- none")
    else:
        for row in top_games:
            appid = row["appid"]
            appid_text = str(appid) if appid is not None else "n/a"
            print(f"- {row['game_name']} (appid={appid_text}): {row['count']}")
    print()

    print("Top games opened on Steam")
    if not top_opened_games:
        print("- none")
    else:
        for row in top_opened_games:
            appid = row["appid"]
            appid_text = str(appid) if appid is not None else "n/a"
            print(f"- {row['game_name']} (appid={appid_text}): {row['count']}")
    print()

    print("Top games selected from search")
    if not top_selected_games:
        print("- none")
    else:
        for row in top_selected_games:
            appid = row["appid"]
            appid_text = str(appid) if appid is not None else "n/a"
            print(f"- {row['game_name']} (appid={appid_text}): {row['count']}")
    print()

    print("Recent activity")
    if not recent_rows:
        print("- none")
    else:
        for row in recent_rows:
            details = row.get("details") or {}
            if not isinstance(details, dict):
                try:
                    details = json.loads(details)
                except (TypeError, ValueError, json.JSONDecodeError):
                    details = {"raw": str(details)}
            detail_text = ", ".join(f"{key}={value}" for key, value in details.items()) or "no details"
            print(
                f"- {row['created_at']}: {row['event_type']} | "
                f"{row['game_name']} (appid={row['appid']}) | {detail_text}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
