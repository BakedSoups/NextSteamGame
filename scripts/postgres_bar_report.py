#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HTML_OUT = PROJECT_ROOT / "data" / "postgres_bar_report.html"
DEFAULT_JSON_OUT = PROJECT_ROOT / "data" / "postgres_bar_report.json"


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


def connect(dsn: str):
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise SystemExit(
            "Missing psycopg. Run this inside the api container or install requirements.txt."
        ) from exc

    return psycopg.connect(dsn, row_factory=dict_row)


def fetch_rows(connection: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        try:
            cursor.execute(sql, params)
        except Exception as exc:
            compact_sql = " ".join(sql.split())
            raise RuntimeError(f"Postgres report query failed: {compact_sql}") from exc
        return [dict(row) for row in cursor.fetchall()]


def fetch_value(connection: Any, sql: str, params: tuple[Any, ...] = ()) -> Any:
    rows = fetch_rows(connection, sql, params)
    if not rows:
        return None
    return next(iter(rows[0].values()))


def table_exists(connection: Any, table_name: str) -> bool:
    value = fetch_value(
        connection,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        )
        """,
        (table_name,),
    )
    return bool(value)


def as_int(value: Any) -> int:
    if value is None:
        return 0
    return int(value)


def run_report(connection: Any, *, limit: int) -> dict[str, Any]:
    tables = [
        "games",
        "game_screenshots",
        "precomputed_candidates",
        "canonical_tag_groups",
        "canonical_tag_members",
        "pipeline_runs",
        "ui_diagnostics",
    ]
    available_tables = [table for table in tables if table_exists(connection, table)]

    summary_rows = []
    for table in available_tables:
        summary_rows.append(
            {
                "label": table,
                "value": as_int(fetch_value(connection, f"SELECT COUNT(*) FROM {table}")),
            }
        )

    charts: list[dict[str, Any]] = [
        {
            "title": "Table Rows",
            "subtitle": "Core Postgres table sizes",
            "rows": summary_rows,
        }
    ]

    if "games" in available_tables:
        charts.extend(
            [
                {
                    "title": "Games By Release Year",
                    "subtitle": "Top release years represented in the catalog",
                    "rows": fetch_rows(
                        connection,
                        """
                        SELECT label, COUNT(*)::bigint AS value
                        FROM (
                            SELECT NULLIF(SUBSTRING(release_date_parsed FROM '^[0-9]{4}'), '') AS label
                            FROM games
                            WHERE release_date_parsed IS NOT NULL
                              AND release_date_parsed <> ''
                        ) years
                        WHERE label IS NOT NULL
                        GROUP BY label
                        ORDER BY value DESC, label DESC
                        LIMIT %s
                        """,
                        (limit,),
                    ),
                },
                {
                    "title": "Estimated Review Count Buckets",
                    "subtitle": "How review volume is distributed",
                    "rows": fetch_rows(
                        connection,
                        """
                        SELECT bucket AS label, COUNT(*)::bigint AS value
                        FROM (
                            SELECT CASE
                                WHEN COALESCE(estimated_review_count, positive + negative, 0) >= 100000 THEN '100k+'
                                WHEN COALESCE(estimated_review_count, positive + negative, 0) >= 50000 THEN '50k-99k'
                                WHEN COALESCE(estimated_review_count, positive + negative, 0) >= 10000 THEN '10k-49k'
                                WHEN COALESCE(estimated_review_count, positive + negative, 0) >= 1000 THEN '1k-9k'
                                WHEN COALESCE(estimated_review_count, positive + negative, 0) > 0 THEN '1-999'
                                ELSE 'missing'
                            END AS bucket
                            FROM games
                        ) buckets
                        GROUP BY bucket
                        ORDER BY CASE bucket
                            WHEN '100k+' THEN 1
                            WHEN '50k-99k' THEN 2
                            WHEN '10k-49k' THEN 3
                            WHEN '1k-9k' THEN 4
                            WHEN '1-999' THEN 5
                            ELSE 6
                        END
                        """,
                    ),
                },
                {
                    "title": "Steam Review Positivity Buckets",
                    "subtitle": "Positive review share where review counts are available",
                    "rows": fetch_rows(
                        connection,
                        """
                        SELECT bucket AS label, COUNT(*)::bigint AS value
                        FROM (
                            SELECT CASE
                                WHEN COALESCE(positive, 0) + COALESCE(negative, 0) = 0 THEN 'missing'
                                WHEN positive::numeric / NULLIF(positive + negative, 0) >= 0.95 THEN '95-100%%'
                                WHEN positive::numeric / NULLIF(positive + negative, 0) >= 0.90 THEN '90-94%%'
                                WHEN positive::numeric / NULLIF(positive + negative, 0) >= 0.80 THEN '80-89%%'
                                WHEN positive::numeric / NULLIF(positive + negative, 0) >= 0.70 THEN '70-79%%'
                                WHEN positive::numeric / NULLIF(positive + negative, 0) >= 0.50 THEN '50-69%%'
                                ELSE '<50%%'
                            END AS bucket
                            FROM games
                        ) buckets
                        GROUP BY bucket
                        ORDER BY CASE bucket
                            WHEN '95-100%%' THEN 1
                            WHEN '90-94%%' THEN 2
                            WHEN '80-89%%' THEN 3
                            WHEN '70-79%%' THEN 4
                            WHEN '50-69%%' THEN 5
                            WHEN '<50%%' THEN 6
                            ELSE 7
                        END
                        """,
                    ),
                },
                {
                    "title": "Top Primary Genres",
                    "subtitle": "From canonical_metadata.genre_tree.primary",
                    "rows": fetch_rows(
                        connection,
                        """
                        SELECT genre.value AS label, COUNT(*)::bigint AS value
                        FROM games
                        CROSS JOIN LATERAL jsonb_array_elements_text(
                            CASE
                                WHEN jsonb_typeof(canonical_metadata -> 'genre_tree' -> 'primary') = 'array'
                                    THEN canonical_metadata -> 'genre_tree' -> 'primary'
                                ELSE '[]'::jsonb
                            END
                        ) AS genre(value)
                        GROUP BY genre.value
                        ORDER BY value DESC, label
                        LIMIT %s
                        """,
                        (limit,),
                    ),
                },
                {
                    "title": "Top Signature Hooks",
                    "subtitle": "Most common canonical signature_tag values",
                    "rows": fetch_rows(
                        connection,
                        """
                        SELECT canonical_metadata ->> 'signature_tag' AS label, COUNT(*)::bigint AS value
                        FROM games
                        WHERE COALESCE(canonical_metadata ->> 'signature_tag', '') <> ''
                        GROUP BY label
                        ORDER BY value DESC, label
                        LIMIT %s
                        """,
                        (limit,),
                    ),
                },
                {
                    "title": "Asset Coverage",
                    "subtitle": "How many games have each major image field",
                    "rows": fetch_rows(
                        connection,
                        """
                        SELECT *
                        FROM (
                            SELECT 'header image' AS label, COUNT(*) FILTER (WHERE header_image <> '')::bigint AS value FROM games
                            UNION ALL
                            SELECT 'capsule image', COUNT(*) FILTER (WHERE capsule_image <> '')::bigint FROM games
                            UNION ALL
                            SELECT 'library hero', COUNT(*) FILTER (WHERE library_hero_image <> '')::bigint FROM games
                            UNION ALL
                            SELECT 'library capsule', COUNT(*) FILTER (WHERE library_capsule_image <> '')::bigint FROM games
                            UNION ALL
                            SELECT 'background image', COUNT(*) FILTER (WHERE background_image <> '')::bigint FROM games
                        ) coverage
                        ORDER BY value DESC
                        """,
                    ),
                },
            ]
        )

    if "canonical_tag_groups" in available_tables:
        charts.extend(
            [
                {
                    "title": "Canonical Tag Occurrences By Context",
                    "subtitle": "Sum of total_occurrences across canonical groups",
                    "rows": fetch_rows(
                        connection,
                        """
                        SELECT context AS label, SUM(total_occurrences)::bigint AS value
                        FROM canonical_tag_groups
                        GROUP BY context
                        ORDER BY value DESC, label
                        """,
                    ),
                },
                {
                    "title": "Canonical Group Count By Context",
                    "subtitle": "Number of canonical groups created per context",
                    "rows": fetch_rows(
                        connection,
                        """
                        SELECT context AS label, COUNT(*)::bigint AS value
                        FROM canonical_tag_groups
                        GROUP BY context
                        ORDER BY value DESC, label
                        """,
                    ),
                },
                {
                    "title": "Top Canonical Tags",
                    "subtitle": "Representative tags by total occurrence count",
                    "rows": fetch_rows(
                        connection,
                        """
                        SELECT representative_tag AS label, total_occurrences::bigint AS value
                        FROM canonical_tag_groups
                        ORDER BY total_occurrences DESC, representative_tag
                        LIMIT %s
                        """,
                        (limit,),
                    ),
                },
            ]
        )

    if "games" in available_tables and "game_screenshots" in available_tables:
        charts.append(
            {
                "title": "Screenshot Count Per Game",
                "subtitle": "Number of games by screenshot count",
                "rows": fetch_rows(
                    connection,
                    """
                    SELECT screenshot_count::text AS label, COUNT(*)::bigint AS value
                    FROM (
                        SELECT g.appid, COUNT(s.screenshot_id)::int AS screenshot_count
                        FROM games g
                        LEFT JOIN game_screenshots s ON s.appid = g.appid
                        GROUP BY g.appid
                    ) counts
                    GROUP BY screenshot_count
                    ORDER BY screenshot_count::int
                    """,
                ),
            }
        )

    if "games" in available_tables and "precomputed_candidates" in available_tables:
        charts.append(
            {
                "title": "Precomputed Candidates Per Source Game",
                "subtitle": "How complete the candidate cache is",
                "rows": fetch_rows(
                    connection,
                    """
                    SELECT bucket AS label, COUNT(*)::bigint AS value
                    FROM (
                        SELECT CASE
                            WHEN candidate_count >= 300 THEN '300+'
                            WHEN candidate_count >= 200 THEN '200-299'
                            WHEN candidate_count >= 100 THEN '100-199'
                            WHEN candidate_count >= 50 THEN '50-99'
                            WHEN candidate_count > 0 THEN '1-49'
                            ELSE '0'
                        END AS bucket
                        FROM (
                            SELECT g.appid, COUNT(c.candidate_appid)::int AS candidate_count
                            FROM games g
                            LEFT JOIN precomputed_candidates c ON c.source_appid = g.appid
                            GROUP BY g.appid
                        ) counts
                    ) buckets
                    GROUP BY bucket
                    ORDER BY CASE bucket
                        WHEN '300+' THEN 1
                        WHEN '200-299' THEN 2
                        WHEN '100-199' THEN 3
                        WHEN '50-99' THEN 4
                        WHEN '1-49' THEN 5
                        ELSE 6
                    END
                    """,
                ),
            }
        )

    if "ui_diagnostics" in available_tables:
        charts.extend(
            [
                {
                    "title": "User Activity Events",
                    "subtitle": "Counts by event_type in ui_diagnostics",
                    "rows": fetch_rows(
                        connection,
                        """
                        SELECT event_type AS label, COUNT(*)::bigint AS value
                        FROM ui_diagnostics
                        GROUP BY event_type
                        ORDER BY value DESC, label
                        LIMIT %s
                        """,
                        (limit,),
                    ),
                },
                {
                    "title": "Top Titles Opened On Steam",
                    "subtitle": "Recommendation cards and no-review Steam links clicked",
                    "rows": fetch_rows(
                        connection,
                        """
                        SELECT
                            COALESCE(NULLIF(game_name, ''), '(unknown)') AS label,
                            COUNT(*)::bigint AS value
                        FROM ui_diagnostics
                        WHERE event_type IN (
                            'opened_recommendation_on_steam',
                            'opened_game_on_steam_without_insightful_reviews',
                            'checked_out_game_without_insightful_reviews'
                        )
                        GROUP BY game_name, appid
                        ORDER BY value DESC, label
                        LIMIT %s
                        """,
                        (limit,),
                    ),
                },
                {
                    "title": "Top Games Picked From Search",
                    "subtitle": "Games users selected as their starting point",
                    "rows": fetch_rows(
                        connection,
                        """
                        SELECT
                            COALESCE(NULLIF(game_name, ''), '(unknown)') AS label,
                            COUNT(*)::bigint AS value
                        FROM ui_diagnostics
                        WHERE event_type = 'selected_game_from_search'
                        GROUP BY game_name, appid
                        ORDER BY value DESC, label
                        LIMIT %s
                        """,
                        (limit,),
                    ),
                },
                {
                    "title": "Recommendation Clicks By Source Game",
                    "subtitle": "Which starting games caused users to open recommendation results",
                    "rows": fetch_rows(
                        connection,
                        """
                        SELECT
                            COALESCE(NULLIF(details ->> 'selectedGameTitle', ''), '(unknown source)') AS label,
                            COUNT(*)::bigint AS value
                        FROM ui_diagnostics
                        WHERE event_type = 'opened_recommendation_on_steam'
                        GROUP BY label
                        ORDER BY value DESC, label
                        LIMIT %s
                        """,
                        (limit,),
                    ),
                },
                {
                    "title": "Top Search Queries That Became Picks",
                    "subtitle": "Search query text attached to selected_game_from_search",
                    "rows": fetch_rows(
                        connection,
                        """
                        SELECT
                            COALESCE(NULLIF(details ->> 'query', ''), '(empty query)') AS label,
                            COUNT(*)::bigint AS value
                        FROM ui_diagnostics
                        WHERE event_type = 'selected_game_from_search'
                        GROUP BY label
                        ORDER BY value DESC, label
                        LIMIT %s
                        """,
                        (limit,),
                    ),
                },
                {
                    "title": "Daily User Activity",
                    "subtitle": "All ui_diagnostics rows grouped by day",
                    "rows": fetch_rows(
                        connection,
                        """
                        SELECT to_char(created_at::date, 'YYYY-MM-DD') AS label, COUNT(*)::bigint AS value
                        FROM ui_diagnostics
                        GROUP BY created_at::date
                        ORDER BY created_at::date DESC
                        LIMIT %s
                        """,
                        (limit,),
                    ),
                },
            ]
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "charts": charts,
    }


def format_number(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def render_chart(chart: dict[str, Any]) -> str:
    rows = [
        {"label": str(row.get("label") or "unknown"), "value": as_int(row.get("value"))}
        for row in chart.get("rows", [])
    ]
    rows = [row for row in rows if row["value"] >= 0]
    max_value = max((row["value"] for row in rows), default=1)

    bars = []
    for row in rows:
        width = 0 if max_value <= 0 else max(2, (row["value"] / max_value) * 100)
        bars.append(
            f"""
            <div class="bar-row">
              <div class="bar-label" title="{html.escape(row['label'])}">{html.escape(row['label'])}</div>
              <div class="bar-track">
                <div class="bar-fill" style="width: {width:.2f}%"></div>
              </div>
              <div class="bar-value">{format_number(row['value'])}</div>
            </div>
            """
        )

    return f"""
    <section class="chart-card">
      <div class="chart-header">
        <h2>{html.escape(str(chart.get("title", "Chart")))}</h2>
        <p>{html.escape(str(chart.get("subtitle", "")))}</p>
      </div>
      <div class="bars">
        {''.join(bars) if bars else '<div class="empty">No rows returned.</div>'}
      </div>
    </section>
    """


def render_html(report: dict[str, Any]) -> str:
    generated_at = html.escape(str(report.get("generated_at", "")))
    charts = "\n".join(render_chart(chart) for chart in report.get("charts", []))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Steam Recommender Postgres Report</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #07111d;
      --panel: #102132;
      --panel-2: #172a3b;
      --text: #edf7ff;
      --muted: #9fb4c7;
      --line: rgba(143, 215, 255, 0.18);
      --accent: #72d2ff;
      --accent-2: #87efac;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top left, rgba(114, 210, 255, 0.10), transparent 34rem), var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      width: min(1480px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 32px 0 48px;
    }}
    header {{
      margin-bottom: 24px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(16, 33, 50, 0.82);
      padding: 22px 24px;
      box-shadow: 0 18px 48px rgba(0, 0, 0, 0.28);
    }}
    h1, h2, p {{ margin: 0; }}
    h1 {{ font-size: clamp(28px, 3vw, 42px); letter-spacing: -0.02em; }}
    header p {{ margin-top: 8px; color: var(--muted); font-size: 15px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(460px, 1fr));
      gap: 18px;
    }}
    .chart-card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      background: linear-gradient(180deg, rgba(23, 42, 59, 0.90), rgba(16, 33, 50, 0.92));
      padding: 18px;
      box-shadow: 0 16px 42px rgba(0, 0, 0, 0.22);
    }}
    .chart-header {{
      min-height: 64px;
      margin-bottom: 12px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      padding-bottom: 12px;
    }}
    .chart-header h2 {{ font-size: 19px; }}
    .chart-header p {{ margin-top: 5px; color: var(--muted); font-size: 14px; line-height: 1.45; }}
    .bars {{ display: grid; gap: 9px; }}
    .bar-row {{
      display: grid;
      grid-template-columns: minmax(140px, 0.42fr) minmax(180px, 1fr) 86px;
      align-items: center;
      gap: 10px;
    }}
    .bar-label {{
      overflow: hidden;
      color: #dbeafe;
      font-size: 14px;
      font-weight: 650;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .bar-track {{
      height: 20px;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.055);
    }}
    .bar-fill {{
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--accent), var(--accent-2));
      box-shadow: 0 0 18px rgba(114, 210, 255, 0.22);
    }}
    .bar-value {{
      color: #c4e7ff;
      font-variant-numeric: tabular-nums;
      font-size: 14px;
      font-weight: 700;
      text-align: right;
    }}
    .empty {{ color: var(--muted); font-size: 14px; }}
    @media (max-width: 720px) {{
      main {{ width: min(100vw - 20px, 1480px); padding-top: 16px; }}
      .grid {{ grid-template-columns: 1fr; }}
      .bar-row {{ grid-template-columns: 1fr; gap: 5px; }}
      .bar-value {{ text-align: left; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Steam Recommender Postgres Report</h1>
      <p>Generated at {generated_at}. All charts are read-only aggregate queries from Postgres.</p>
    </header>
    <div class="grid">
      {charts}
    </div>
  </main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a standalone HTML bar-chart report from the Steam recommender Postgres DB.")
    parser.add_argument("--dsn", default=None, help="Postgres DSN. Defaults to STEAM_REC_POSTGRES_DSN.")
    parser.add_argument("--out", type=Path, default=DEFAULT_HTML_OUT, help=f"HTML output path. Default: {DEFAULT_HTML_OUT}")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT, help=f"JSON output path. Default: {DEFAULT_JSON_OUT}")
    parser.add_argument("--limit", type=int, default=20, help="Max rows for top-N charts.")
    args = parser.parse_args()

    load_project_env()
    dsn = args.dsn or os.getenv("STEAM_REC_POSTGRES_DSN")
    if not dsn:
        raise SystemExit("STEAM_REC_POSTGRES_DSN is not set. Pass --dsn or export the env var.")

    with connect(dsn) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        report = run_report(connection, limit=max(1, args.limit))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_html(report), encoding="utf-8")
    args.json_out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"Wrote HTML report: {args.out}")
    print(f"Wrote JSON data:   {args.json_out}")


if __name__ == "__main__":
    main()
