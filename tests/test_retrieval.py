from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from backend.recommender import default_context_percentages
from backend.retrieval import CandidateRetriever


class FakeStore:
    def __init__(self) -> None:
        self.precomputed_calls: list[int] = []
        self.prescreen_calls: list[dict[str, Any]] = []
        self.hydrated_appids: list[list[int]] = []

    def load_precomputed_candidate_appids(self, source_appid: int, *, limit: int) -> list[int]:
        self.precomputed_calls.append(source_appid)
        return [101, 102][:limit]

    def prescreen_candidate_appids(self, base_game: dict[str, Any], **kwargs: Any) -> list[int]:
        self.prescreen_calls.append(kwargs)
        return [201, 202][: kwargs["limit"]]

    def load_games_by_appids(self, appids: list[int]) -> list[dict[str, Any]]:
        self.hydrated_appids.append(appids)
        return [{"appid": appid, "name": f"Game {appid}"} for appid in appids]


class CandidateRetrieverTests(unittest.TestCase):
    def make_retriever(self, store: FakeStore) -> CandidateRetriever:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return CandidateRetriever(chroma_dir=Path(temp_dir.name) / "missing-chroma", store=store)

    def test_default_request_uses_precomputed_candidates(self) -> None:
        store = FakeStore()
        retriever = self.make_retriever(store)

        candidates = retriever.retrieve_candidates({"appid": 10}, merged_limit=300)

        self.assertEqual([candidate["appid"] for candidate in candidates], [101, 102])
        self.assertEqual(store.precomputed_calls, [10])
        self.assertEqual(store.prescreen_calls, [])

    def test_tuned_tag_request_bypasses_precomputed_candidates(self) -> None:
        store = FakeStore()
        retriever = self.make_retriever(store)

        candidates = retriever.retrieve_candidates(
            {"appid": 10},
            tag_boosts={"identity": {"social deduction": 80}},
            prescreen_limit=450,
            merged_limit=300,
        )

        self.assertEqual([candidate["appid"] for candidate in candidates], [201, 202])
        self.assertEqual(store.precomputed_calls, [])
        self.assertEqual(len(store.prescreen_calls), 1)

    def test_tuned_context_request_bypasses_precomputed_candidates(self) -> None:
        store = FakeStore()
        retriever = self.make_retriever(store)
        context_percentages = default_context_percentages()
        context_percentages["identity"] += 10
        context_percentages["music"] = max(0, context_percentages["music"] - 10)

        candidates = retriever.retrieve_candidates(
            {"appid": 10},
            context_percentages=context_percentages,
            prescreen_limit=450,
            merged_limit=300,
        )

        self.assertEqual([candidate["appid"] for candidate in candidates], [201, 202])
        self.assertEqual(store.precomputed_calls, [])
        self.assertEqual(len(store.prescreen_calls), 1)


if __name__ == "__main__":
    unittest.main()
