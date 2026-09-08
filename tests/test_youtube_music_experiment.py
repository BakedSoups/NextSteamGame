from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from experiments.youtube_music.audio import detect_music_segments
from experiments.youtube_music.cnn import aggregate_predictions, model_nodes, top_predictions, website_tags
from experiments.youtube_music.scrape import acquire_authorized_audio, seconds_to_iso8601
from experiments.youtube_music.youtube import Candidate, chunks, iso8601_seconds, select_tracks


class YouTubeMusicExperimentTests(unittest.TestCase):
    def test_chunks_respects_youtube_batch_limit(self) -> None:
        batches = list(chunks([str(index) for index in range(101)], 50))
        self.assertEqual([len(batch) for batch in batches], [50, 50, 1])

    def test_iso_duration_parser(self) -> None:
        self.assertEqual(iso8601_seconds("PT1H2M3S"), 3723)

    def test_track_ranking_prefers_official_song_over_popular_mix(self) -> None:
        candidates = [
            Candidate(
                "mix", "Persona 5 Music to Study and Relax Mix", "Fan Channel",
                5_000_000, "PT2H", playlist_title="Persona 5 OST",
            ),
            Candidate(
                "song", "Last Surprise", "ATLUS GAME MUSIC", 900_000, "PT3M55S",
                playlist_title="Persona 5 Original Soundtrack",
                playlist_channel="ATLUS GAME MUSIC",
            ),
        ]
        selected = select_tracks(candidates, "Persona 5 Royal")
        self.assertEqual([item["video_id"] for item in selected], ["song"])
        self.assertIn("publisher_or_official_channel", selected[0]["signals"])
        self.assertEqual(selected[0]["provenance"]["playlist_title"], "Persona 5 Original Soundtrack")

    def test_track_selection_deduplicates_normalized_titles(self) -> None:
        candidates = [
            Candidate("one", "Persona 4 OST - Reach Out To The Truth", "SEGA", 1000, "PT2M50S"),
            Candidate("two", "Reach Out To The Truth [OST]", "Fan", 900, "PT2M50S"),
        ]
        selected = select_tracks(candidates, "Persona 4")
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["video_id"], "one")

    def test_segmenter_returns_ordered_covering_segments(self) -> None:
        sample_rate = 100
        first = np.sin(2 * np.pi * 4 * np.arange(6000) / sample_rate)
        second = np.sin(2 * np.pi * 30 * np.arange(6000) / sample_rate)
        segments = detect_music_segments(
            np.concatenate([first, second]).astype(np.float32),
            sample_rate,
            window_seconds=10,
            min_segment_seconds=30,
            change_threshold=0.05,
        )
        self.assertGreaterEqual(len(segments), 2)
        self.assertEqual(segments[0].start_seconds, 0)
        self.assertAlmostEqual(segments[-1].end_seconds, 120)

    def test_cnn_predictions_are_ranked_and_averaged(self) -> None:
        result = top_predictions(
            np.asarray([[0.1, 0.8, 0.2], [0.3, 0.6, 0.4]], dtype=np.float32),
            ["horn", "guitar", "piano"],
            limit=2,
        )
        self.assertEqual([item["label"] for item in result], ["guitar", "piano"])

    def test_prediction_aggregation_preserves_evidence_count(self) -> None:
        reports = [
            {"genres": [{"label": "Jazz", "score": 0.8}]},
            {"genres": [{"label": "Jazz", "score": 0.6}, {"label": "Rock", "score": 0.5}]},
        ]
        result = aggregate_predictions(reports, "genres")
        self.assertEqual(result[0], {"label": "Jazz", "score": 0.7, "evidence_count": 2})
        self.assertEqual(result[1], {"label": "Rock", "score": 0.25, "evidence_count": 1})

    def test_website_tags_normalizes_model_taxonomy(self) -> None:
        result = website_tags([
            {"label": "Jazz---Fusion", "score": 0.8},
            {"label": "Electronic---Jazz_Fusion", "score": 0.5},
            {"label": "Rock---Noise", "score": 0.01},
        ])
        self.assertEqual(result, [
            {"tag": "jazz fusion", "confidence": 0.8},
        ])

    def test_model_nodes_uses_declared_prediction_output(self) -> None:
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            metadata = Path(directory) / "model.json"
            metadata.write_text(json.dumps({"schema": {
                "inputs": [{"name": "input"}],
                "outputs": [
                    {"name": "hidden", "output_purpose": ""},
                    {"name": "scores", "output_purpose": "predictions"},
                ],
            }}))
            self.assertEqual(model_nodes(metadata), ("input", "scores"))

    def test_audio_acquisition_requires_rights_confirmation(self) -> None:
        with self.assertRaises(PermissionError):
            acquire_authorized_audio("example", Path("unused.wav"))

    def test_seconds_to_iso8601(self) -> None:
        self.assertEqual(seconds_to_iso8601(3723), "PT1H2M3S")


if __name__ == "__main__":
    unittest.main()
