from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CandidateRetriever:
    def __init__(self, *, chroma_dir: Path, fallback_games: list[dict], store: Any | None = None) -> None:
        self.chroma_dir = chroma_dir
        self.fallback_games = fallback_games
        self._fallback_by_appid = {int(game["appid"]): game for game in fallback_games}
        self.store = store
        self._collection = self._load_collection()

    @staticmethod
    def _merge_candidate_ids(*candidate_lists: list[int], limit: int) -> list[int]:
        merged: list[int] = []
        seen: set[int] = set()
        indices = [0 for _ in candidate_lists]

        while len(merged) < limit:
            progressed = False
            for list_index, candidate_ids in enumerate(candidate_lists):
                while indices[list_index] < len(candidate_ids):
                    appid = candidate_ids[indices[list_index]]
                    indices[list_index] += 1
                    if appid in seen:
                        continue
                    seen.add(appid)
                    merged.append(appid)
                    progressed = True
                    break
                if len(merged) >= limit:
                    break
            if not progressed:
                break

        return merged

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
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load Chroma collection 'steam_final_canon' from {self.chroma_dir}"
            ) from exc

    @staticmethod
    def _build_query_text(
        game: dict,
        *,
        context_percentages: dict[str, float | int] | None = None,
        tag_boosts: dict[str, dict[str, float]] | None = None,
        soundtrack_boosts: dict[str, float] | None = None,
    ) -> str:
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
        parts.extend(str(tag) for tag in metadata.get("setting_tags", []) if tag)
        if metadata.get("music_primary"):
            parts.append(str(metadata["music_primary"]))
        if metadata.get("music_secondary"):
            parts.append(str(metadata["music_secondary"]))

        for context, tag_weights in vectors.items():
            for tag in tag_weights:
                parts.append(f"{context}:{tag}")

        active_contexts = context_percentages or {}
        for context, weight in active_contexts.items():
            numeric_weight = max(float(weight), 0.0)
            if numeric_weight <= 0:
                continue
            emphasis_count = max(1, min(int(round(numeric_weight / 18.0)), 5))
            parts.extend([f"focus:{context}"] * emphasis_count)

            if context in vectors:
                ranked_tags = sorted(
                    (vectors.get(context) or {}).items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:4]
                for tag, _value in ranked_tags:
                    parts.extend([str(tag)] * emphasis_count)

            if context == "identity":
                identity_tags = [
                    str(metadata.get("signature_tag", "")).strip(),
                    *(str(tag).strip() for tag in metadata.get("niche_anchors", []) or []),
                    *(str(tag).strip() for tag in metadata.get("identity_tags", []) or []),
                ]
                for tag in [tag for tag in identity_tags if tag][:4]:
                    parts.extend([tag] * emphasis_count)
            elif context == "setting":
                setting_tags = [str(tag).strip() for tag in metadata.get("setting_tags", []) or [] if str(tag).strip()]
                for tag in setting_tags[:4]:
                    parts.extend([tag] * emphasis_count)
            elif context == "music":
                music_tags = []
                if metadata.get("music_primary"):
                    music_tags.append(str(metadata.get("music_primary")).strip())
                if metadata.get("music_secondary"):
                    music_tags.append(str(metadata.get("music_secondary")).strip())
                for tag in [tag for tag in music_tags if tag]:
                    parts.extend([tag] * emphasis_count)

        for context, weighted_tags in (tag_boosts or {}).items():
            ranked_tags = sorted(weighted_tags.items(), key=lambda item: item[1], reverse=True)[:6]
            for tag, weight in ranked_tags:
                emphasis_count = max(1, min(int(round(float(weight) / 24.0)), 4))
                parts.extend([str(tag)] * emphasis_count)
                parts.extend([f"{context}:{tag}"] * emphasis_count)

        for tag, weight in sorted((soundtrack_boosts or {}).items(), key=lambda item: item[1], reverse=True)[:4]:
            emphasis_count = max(1, min(int(round(float(weight) / 24.0)), 4))
            parts.extend([str(tag)] * emphasis_count)

        return "\n".join(part for part in parts if part)

    def retrieve_candidates(
        self,
        game: dict,
        *,
        chroma_limit: int = 450,
        prescreen_limit: int = 2200,
        merged_limit: int = 1600,
        context_percentages: dict[str, float | int] | None = None,
        tag_boosts: dict[str, dict[str, float]] | None = None,
        soundtrack_boosts: dict[str, float] | None = None,
    ) -> list[dict]:
        prescreen_ids: list[int] = []
        if self.store is not None:
            prescreen_ids = self.store.prescreen_candidate_appids(
                game,
                context_percentages=context_percentages,
                tag_boosts=tag_boosts,
                soundtrack_boosts=soundtrack_boosts,
                limit=prescreen_limit,
            )

        chroma_ids: list[int] = []
        if self._collection is None:
            merged_ids = prescreen_ids
        else:
            try:
                result = self._collection.query(
                    query_texts=[
                    self._build_query_text(
                        game,
                        context_percentages=context_percentages,
                        tag_boosts=tag_boosts,
                        soundtrack_boosts=soundtrack_boosts,
                    )
                ],
                n_results=chroma_limit,
            )
            except Exception as exc:
                appid = game.get("appid", "unknown")
                name = str(game.get("name", "")).strip() or "unknown"
                raise RuntimeError(
                    f"Chroma candidate retrieval failed for appid={appid} name={name!r}"
                ) from exc

            ids = result.get("ids", [[]])[0]
            for raw_id in ids:
                try:
                    appid = int(raw_id)
                except (TypeError, ValueError):
                    continue
                chroma_ids.append(appid)

            merged_ids = self._merge_candidate_ids(prescreen_ids, chroma_ids, limit=merged_limit)

        candidates = []
        for appid in merged_ids:
            try:
                appid = int(appid)
            except (TypeError, ValueError):
                continue
            game_payload = self._fallback_by_appid.get(appid)
            if game_payload is not None:
                candidates.append(game_payload)

        return candidates or self.fallback_games
