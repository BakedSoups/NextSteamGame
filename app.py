#!/usr/bin/env python3

from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.db import FinalGameStore
from backend.recommender import recommend_games
from db_creation.paths import final_canon_db_path, metadata_db_path


ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "frontend" / "templates"
STATIC_DIR = ROOT / "frontend" / "static"

HOST = "127.0.0.1"
PORT = 8000

env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

store = FinalGameStore(final_canon_db_path(), metadata_db_path())
ALL_GAMES = store.load_all_games()


def render(template_name: str, **context) -> bytes:
    template = env.get_template(template_name)
    return template.render(**context).encode("utf-8")


def response(start_response, body: bytes, content_type: str = "text/html; charset=utf-8", status: str = "200 OK"):
    start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(body)))])
    return [body]


def not_found(start_response):
    return response(start_response, b"Not found", "text/plain; charset=utf-8", "404 Not Found")


def parse_request_data(environ) -> dict[str, list[str]]:
    if environ["REQUEST_METHOD"] == "POST":
        size = int(environ.get("CONTENT_LENGTH") or 0)
        raw = environ["wsgi.input"].read(size).decode("utf-8")
        return parse_qs(raw, keep_blank_values=True)
    return parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)


def parse_adjustments(data: dict[str, list[str]]) -> tuple[dict[str, dict[str, float]], dict[str, list[str]], bool]:
    extra_vector_boosts: dict[str, dict[str, float]] = {}
    selected_genres = {"primary": [], "sub": [], "traits": []}
    saw_genre_input = False

    for key, values in data.items():
        if key.startswith("boost__"):
            _, context, tag = key.split("__", 2)
            try:
                multiplier = float(values[-1]) / 100.0
            except (TypeError, ValueError):
                multiplier = 1.0
            extra_vector_boosts.setdefault(context, {})[tag] = multiplier
        elif key.startswith("genre_"):
            branch = key.split("_", 1)[1]
            if branch in selected_genres:
                saw_genre_input = True
                selected_genres[branch] = values

    return extra_vector_boosts, selected_genres, saw_genre_input


def handle_index(start_response):
    body = render("index.html", title="Steam Canon Recommender", initial_query="Counter-Strike")
    return response(start_response, body)


def handle_search(environ, start_response):
    data = parse_request_data(environ)
    query = data.get("q", [""])[-1]
    results = store.search_games(query)
    body = render("partials/search_results.html", results=results)
    return response(start_response, body)


def handle_game(appid: int, start_response):
    game = store.get_game(appid)
    if game is None:
        body = render("partials/game_placeholder.html", selected_appid=appid, unavailable=True)
        return response(start_response, body)
    body = render("partials/game_panel.html", game=game)
    return response(start_response, body)


def handle_recommend(environ, start_response):
    data = parse_request_data(environ)
    appid_raw = data.get("appid", [""])[-1]
    try:
        appid = int(appid_raw)
    except ValueError:
        return response(start_response, b"Missing or invalid appid", "text/plain; charset=utf-8", "400 Bad Request")

    game = store.get_game(appid)
    if game is None:
        body = render("partials/recommendations.html", results=[], unavailable=True)
        return response(start_response, body)

    extra_vector_boosts, selected_genres, saw_genre_input = parse_adjustments(data)
    added_genres = {"primary": [], "sub": [], "traits": []}
    removed_genres = {"primary": [], "sub": [], "traits": []}
    if saw_genre_input:
        base_tree = game["metadata"].get("genre_tree", {})
        for branch in ("primary", "sub", "traits"):
            base_tags = set(base_tree.get(branch, []))
            selected_tags = set(selected_genres.get(branch, []))
            added_genres[branch] = sorted(selected_tags - base_tags)
            removed_genres[branch] = sorted(base_tags - selected_tags)

    recommendations = recommend_games(
        game,
        ALL_GAMES,
        extra_vector_boosts=extra_vector_boosts,
        added_genres=added_genres,
        removed_genres=removed_genres,
        limit=20,
    )
    body = render("partials/recommendations.html", results=recommendations, base_game=game)
    return response(start_response, body)


def handle_static(path: str, start_response):
    target = (STATIC_DIR / path.removeprefix("/static/")).resolve()
    if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.exists() or not target.is_file():
        return not_found(start_response)
    content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    return response(start_response, target.read_bytes(), content_type)


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")

    if path == "/":
        return handle_index(start_response)
    if path == "/search":
        return handle_search(environ, start_response)
    if path.startswith("/game/"):
        try:
            appid = int(path.rsplit("/", 1)[-1])
        except ValueError:
            return not_found(start_response)
        return handle_game(appid, start_response)
    if path == "/recommend":
        return handle_recommend(environ, start_response)
    if path.startswith("/static/"):
        return handle_static(path, start_response)
    return not_found(start_response)


def main() -> int:
    print(f"Serving on http://{HOST}:{PORT}")
    with make_server(HOST, PORT, application) as server:
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
