from __future__ import annotations

import json
from pathlib import Path


class CandidateRetriever:
    def __init__(self, *, chroma_dir: Path, fallback_games: list[dict]) -> None:
        self.chroma_dir = chroma_dir
        self.fallback_games = fallback_games
        self._fallback_by_appid = {int(game["appid"]): game for game in fallback_games}
        self._collection = self._load_collection()

    def _load_collection(self):
        try:
            import chromadb
        except ImportError:
            return None

        if not self.chroma_dir.exists():
            return None

        try:
            client = chromadb.PersistentClient(path=str(self.chroma_dir))
            return client.get_collection("steam_final_canon")
        except Exception:
            return None

    @staticmethod
    def _build_query_text(game: dict) -> str:
        metadata = game.get("metadata", {})
        vectors = game.get("vectors", {})
        parts = [str(game.get("name", "")).strip()]
        if metadata.get("signature_tag"):
            parts.append(str(metadata["signature_tag"]))

        for branch in ("primary", "sub", "sub_sub"):
            raw_value = metadata.get("genre_tree", {}).get(branch)
            if isinstance(raw_value, list):
                parts.extend(str(tag) for tag in raw_value if tag)
            elif raw_value:
                parts.append(str(raw_value))

        parts.extend(str(tag) for tag in metadata.get("micro_tags", []) if tag)
        parts.extend(str(tag) for tag in metadata.get("niche_anchors", []) if tag)
        parts.extend(str(tag) for tag in metadata.get("identity_tags", []) if tag)
        if metadata.get("music_primary"):
            parts.append(str(metadata["music_primary"]))
        if metadata.get("music_secondary"):
            parts.append(str(metadata["music_secondary"]))
        parts.extend(str(tag) for tag in metadata.get("soundtrack_tags", []) if tag)

        for context, tag_weights in vectors.items():
            for tag in tag_weights:
                parts.append(f"{context}:{tag}")
        return "\n".join(part for part in parts if part)

    def retrieve_candidates(self, game: dict, *, limit: int = 400) -> list[dict]:
        if self._collection is None:
            return self.fallback_games

        try:
            result = self._collection.query(
                query_texts=[self._build_query_text(game)],
                n_results=limit,
            )
        except Exception:
            return self.fallback_games

        ids = result.get("ids", [[]])[0]
        candidates = []
        for raw_id in ids:
            try:
                appid = int(raw_id)
            except (TypeError, ValueError):
                continue
            game_payload = self._fallback_by_appid.get(appid)
            if game_payload is not None:
                candidates.append(game_payload)

        return candidates or self.fallback_games
