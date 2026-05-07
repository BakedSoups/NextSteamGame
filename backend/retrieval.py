from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.recommender import default_context_percentages


logger = logging.getLogger(__name__)


def _timed_call(func, *args, **kwargs):
    started = time.perf_counter()
    result = func(*args, **kwargs)
    return result, time.perf_counter() - started


class CandidateRetriever:
    def __init__(self, *, chroma_dir: Path, store: Any | None = None) -> None:
        self.chroma_dir = chroma_dir
        self.store = store
        self._collection = self._load_collection()
        self._default_context_percentages = {
            key: float(value) for key, value in default_context_percentages().items()
        }

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

    def _query_chroma_candidate_ids(
        self,
        game: dict,
        *,
        chroma_limit: int,
        context_percentages: dict[str, float | int] | None = None,
        tag_boosts: dict[str, dict[str, float]] | None = None,
        soundtrack_boosts: dict[str, float] | None = None,
    ) -> list[int]:
        if self._collection is None:
            return []

        try:
            if self._can_use_stored_embedding(
                context_percentages=context_percentages,
                tag_boosts=tag_boosts,
                soundtrack_boosts=soundtrack_boosts,
            ):
                query_embedding = self._stored_embedding_for_appid(int(game["appid"]))
                if query_embedding is not None:
                    result = self._collection.query(
                        query_embeddings=[query_embedding],
                        n_results=chroma_limit,
                    )
                else:
                    result = self._collection.query(
                        query_texts=[self._build_query_text(game)],
                        n_results=chroma_limit,
                    )
            else:
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

        chroma_ids: list[int] = []
        ids = result.get("ids", [[]])[0]
        for raw_id in ids:
            try:
                appid = int(raw_id)
            except (TypeError, ValueError):
                continue
            chroma_ids.append(appid)
        return chroma_ids

    def _can_use_stored_embedding(
        self,
        *,
        context_percentages: dict[str, float | int] | None,
        tag_boosts: dict[str, dict[str, float]] | None,
        soundtrack_boosts: dict[str, float] | None,
    ) -> bool:
        if tag_boosts:
            return False
        if soundtrack_boosts:
            return False
        if context_percentages is None:
            return True

        for context, default_value in self._default_context_percentages.items():
            actual_value = float(context_percentages.get(context, 0.0))
            if abs(actual_value - default_value) > 0.001:
                return False
        return True

    @lru_cache(maxsize=1024)
    def _stored_embedding_for_appid(self, appid: int):
        if self._collection is None:
            return None

        result = self._collection.get(ids=[str(appid)], include=["embeddings"])
        embeddings = result.get("embeddings")
        if embeddings is None or len(embeddings) == 0:
            return None
        embedding = embeddings[0]
        if embedding is None:
            return None
        return embedding

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
        chroma_limit: int = 300,
        prescreen_limit: int = 450,
        merged_limit: int = 300,
        context_percentages: dict[str, float | int] | None = None,
        tag_boosts: dict[str, dict[str, float]] | None = None,
        soundtrack_boosts: dict[str, float] | None = None,
    ) -> list[dict]:
        prescreen_ids: list[int] = []
        chroma_ids: list[int] = []
        started = time.perf_counter()
        prescreen_elapsed = 0.0
        chroma_elapsed = 0.0
        use_default_chroma_path = self._can_use_stored_embedding(
            context_percentages=context_percentages,
            tag_boosts=tag_boosts,
            soundtrack_boosts=soundtrack_boosts,
        )

        with ThreadPoolExecutor(max_workers=2) as executor:
            prescreen_future = None
            chroma_future = None

            if self.store is not None and not use_default_chroma_path:
                prescreen_future = executor.submit(
                    _timed_call,
                    self.store.prescreen_candidate_appids,
                    game,
                    context_percentages=context_percentages,
                    tag_boosts=tag_boosts,
                    soundtrack_boosts=soundtrack_boosts,
                    limit=prescreen_limit,
                )

            if self._collection is not None:
                chroma_future = executor.submit(
                    _timed_call,
                    self._query_chroma_candidate_ids,
                    game,
                    chroma_limit=chroma_limit,
                    context_percentages=context_percentages,
                    tag_boosts=tag_boosts,
                    soundtrack_boosts=soundtrack_boosts,
                )

            if prescreen_future is not None:
                prescreen_ids, prescreen_elapsed = prescreen_future.result()
            if chroma_future is not None:
                chroma_ids, chroma_elapsed = chroma_future.result()

        merge_started = time.perf_counter()
        merged_ids = self._merge_candidate_ids(prescreen_ids, chroma_ids, limit=merged_limit)
        merge_elapsed = time.perf_counter() - merge_started

        if self.store is not None and merged_ids:
            hydrate_started = time.perf_counter()
            candidates = self.store.load_games_by_appids(merged_ids)
            hydrate_elapsed = time.perf_counter() - hydrate_started
            total_elapsed = time.perf_counter() - started
            logger.info(
                "retrieve_candidates appid=%s prescreen_count=%s chroma_count=%s merged_count=%s "
                "candidate_count=%s prescreen_wait=%.3fs chroma_wait=%.3fs merge=%.3fs hydrate=%.3fs total=%.3fs",
                game.get("appid"),
                len(prescreen_ids),
                len(chroma_ids),
                len(merged_ids),
                len(candidates),
                prescreen_elapsed,
                chroma_elapsed,
                merge_elapsed,
                hydrate_elapsed,
                total_elapsed,
            )
            if candidates:
                return candidates

        total_elapsed = time.perf_counter() - started
        logger.info(
            "retrieve_candidates appid=%s prescreen_count=%s chroma_count=%s merged_count=%s "
            "candidate_count=0 prescreen_wait=%.3fs chroma_wait=%.3fs merge=%.3fs total=%.3fs",
            game.get("appid"),
            len(prescreen_ids),
            len(chroma_ids),
            len(merged_ids),
            prescreen_elapsed,
            chroma_elapsed,
            merge_elapsed,
            total_elapsed,
        )
        return []
