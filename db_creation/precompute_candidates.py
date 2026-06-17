#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.pg_store import PostgresGameStore, postgres_dsn_from_env
from db_creation.paths import chroma_dir_path


ROOT = Path(__file__).resolve().parents[1]


def load_project_env() -> None:
    env_path = ROOT / ".env"
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Precompute default recommendation candidates from Chroma into Postgres.",
    )
    parser.add_argument("--appid", type=int, help="Only refresh one source appid.")
    parser.add_argument("--per-game", type=int, default=300, help="Candidates to store per game.")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size for Chroma embedding fetch/query.")
    return parser.parse_args()


def chunked(items: list[int], size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def main() -> int:
    load_project_env()

    dsn = postgres_dsn_from_env()
    if not dsn:
        raise RuntimeError("STEAM_REC_POSTGRES_DSN must be set.")

    args = parse_args()
    store = PostgresGameStore(dsn)
    store.ensure_precomputed_candidates_table()

    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("Chroma is not installed.") from exc

    client = chromadb.PersistentClient(path=str(chroma_dir_path()))
    collection = client.get_collection("steam_final_canon")

    appids = [args.appid] if args.appid is not None else store.list_game_appids()
    processed = 0

    for appid_batch in chunked(appids, max(1, args.batch_size)):
        ids = [str(appid) for appid in appid_batch]
        payload = collection.get(ids=ids, include=["embeddings"])
        embeddings = payload.get("embeddings")
        if embeddings is None:
            embeddings = []
        present_ids = payload.get("ids")
        if present_ids is None:
            present_ids = []
        embedding_map = {
            int(raw_id): embedding
            for raw_id, embedding in zip(present_ids, embeddings)
            if raw_id is not None and embedding is not None
        }
        query_appids = [appid for appid in appid_batch if appid in embedding_map]
        if not query_appids:
            continue

        query_result = collection.query(
            query_embeddings=[embedding_map[appid] for appid in query_appids],
            n_results=max(2, args.per_game + 1),
        )
        candidate_groups = query_result.get("ids", [])

        for appid, raw_candidates in zip(query_appids, candidate_groups):
            candidate_appids: list[int] = []
            for raw_candidate in raw_candidates:
                try:
                    candidate_appid = int(raw_candidate)
                except (TypeError, ValueError):
                    continue
                if candidate_appid == appid:
                    continue
                candidate_appids.append(candidate_appid)
                if len(candidate_appids) >= args.per_game:
                    break
            store.replace_precomputed_candidates(appid, candidate_appids, source="chroma")
            processed += 1
            if processed % 100 == 0:
                print(f"processed={processed}/{len(appids)}")

    print(f"completed processed={processed} total={len(appids)} per_game={args.per_game}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
