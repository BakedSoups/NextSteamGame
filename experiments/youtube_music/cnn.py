from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def load_labels(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    labels = payload.get("classes", payload) if isinstance(payload, dict) else payload
    if not isinstance(labels, list) or not all(isinstance(label, str) for label in labels):
        raise ValueError(f"Unsupported label metadata: {path}")
    return labels


def top_predictions(scores: np.ndarray, labels: list[str], limit: int = 8) -> list[dict[str, float | str]]:
    vector = np.asarray(scores, dtype=np.float32)
    if vector.ndim > 1:
        vector = vector.mean(axis=0)
    if len(vector) != len(labels):
        raise ValueError(f"Model returned {len(vector)} scores for {len(labels)} labels")
    order = np.argsort(vector)[::-1][:limit]
    return [{"label": labels[index], "score": float(vector[index])} for index in order]


class EssentiaEffNetClassifier:
    """Lazy adapter for Essentia's Discogs-EffNet CNN and classification heads."""

    def __init__(
        self,
        embedding_graph: Path,
        genre_graph: Path,
        genre_labels: Path,
        instrument_graph: Path,
        instrument_labels: Path,
    ) -> None:
        try:
            from essentia.standard import MonoLoader, TensorflowPredict2D, TensorflowPredictEffnetDiscogs
        except ImportError as exc:
            raise RuntimeError("Install Essentia with TensorFlow support to use the CNN adapter") from exc
        self._loader = MonoLoader
        self._embed = TensorflowPredictEffnetDiscogs(
            graphFilename=str(embedding_graph),
            output="PartitionedCall:1",
        )
        self._genre = TensorflowPredict2D(graphFilename=str(genre_graph), output="model/Softmax")
        self._instrument = TensorflowPredict2D(graphFilename=str(instrument_graph), output="model/Softmax")
        self.genre_labels = load_labels(genre_labels)
        self.instrument_labels = load_labels(instrument_labels)

    def predict_file(self, audio_path: Path) -> dict[str, list[dict[str, float | str]]]:
        audio = self._loader(filename=str(audio_path), sampleRate=16000, resampleQuality=4)()
        embeddings = self._embed(audio)
        return {
            "genres": top_predictions(self._genre(embeddings), self.genre_labels),
            "instruments": top_predictions(self._instrument(embeddings), self.instrument_labels),
        }

