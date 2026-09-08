from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlopen

import numpy as np

MODEL_BASE = "https://essentia.upf.edu/models"
MODEL_FILES = {
    "embedding_graph": "feature-extractors/discogs-effnet/discogs-effnet-bs64-1.pb",
    "genre_graph": "classification-heads/genre_discogs400/genre_discogs400-discogs-effnet-1.pb",
    "genre_labels": "classification-heads/genre_discogs400/genre_discogs400-discogs-effnet-1.json",
    "instrument_graph": "classification-heads/nsynth_instrument/nsynth_instrument-discogs-effnet-1.pb",
    "instrument_labels": "classification-heads/nsynth_instrument/nsynth_instrument-discogs-effnet-1.json",
}


def ensure_models(directory: Path) -> dict[str, Path]:
    """Download missing model assets from Essentia's official model repository."""
    directory.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, relative_url in MODEL_FILES.items():
        destination = directory / Path(relative_url).name
        paths[name] = destination
        if destination.exists() and destination.stat().st_size:
            continue
        temporary = destination.with_suffix(destination.suffix + ".part")
        with urlopen(f"{MODEL_BASE}/{relative_url}", timeout=120) as response:
            temporary.write_bytes(response.read())
        temporary.replace(destination)
    return paths


def load_labels(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    labels = payload.get("classes", payload) if isinstance(payload, dict) else payload
    if not isinstance(labels, list) or not all(isinstance(label, str) for label in labels):
        raise ValueError(f"Unsupported label metadata: {path}")
    return labels


def model_nodes(path: Path) -> tuple[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema = payload.get("schema", {})
    inputs = schema.get("inputs", [])
    outputs = [item for item in schema.get("outputs", []) if item.get("output_purpose") == "predictions"]
    if not inputs or not outputs:
        raise ValueError(f"Model metadata does not declare prediction nodes: {path}")
    return str(inputs[0]["name"]), str(outputs[0]["name"])


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
            import essentia
            from essentia.standard import MonoLoader, TensorflowPredict2D, TensorflowPredictEffnetDiscogs
        except ImportError as exc:
            raise RuntimeError("Install Essentia with TensorFlow support to use the CNN adapter") from exc
        essentia.log.infoActive = False
        essentia.log.warningActive = False
        self._loader = MonoLoader
        self._embed = TensorflowPredictEffnetDiscogs(
            graphFilename=str(embedding_graph),
            output="PartitionedCall:1",
        )
        genre_input, genre_output = model_nodes(genre_labels)
        instrument_input, instrument_output = model_nodes(instrument_labels)
        self._genre = TensorflowPredict2D(
            graphFilename=str(genre_graph),
            input=genre_input,
            output=genre_output,
        )
        self._instrument = TensorflowPredict2D(
            graphFilename=str(instrument_graph),
            input=instrument_input,
            output=instrument_output,
        )
        self.genre_labels = load_labels(genre_labels)
        self.instrument_labels = load_labels(instrument_labels)

    def predict_file(self, audio_path: Path) -> dict[str, list[dict[str, float | str]]]:
        audio = self._loader(filename=str(audio_path), sampleRate=16000, resampleQuality=4)()
        embeddings = self._embed(audio)
        return {
            "genres": top_predictions(self._genre(embeddings), self.genre_labels),
            "instruments": top_predictions(self._instrument(embeddings), self.instrument_labels),
        }


def aggregate_predictions(
    reports: list[dict[str, list[dict[str, float | str]]]],
    key: str,
    limit: int = 8,
) -> list[dict[str, float | str]]:
    totals: dict[str, list[float]] = {}
    for report in reports:
        for item in report.get(key, []):
            totals.setdefault(str(item["label"]), []).append(float(item["score"]))
    report_count = len(reports)
    ranked = sorted(
        ((label, sum(values) / report_count, len(values)) for label, values in totals.items()),
        key=lambda item: item[1],
        reverse=True,
    )[:limit]
    return [
        {"label": label, "score": score, "evidence_count": count}
        for label, score, count in ranked
    ]


def website_tags(
    predictions: list[dict[str, float | str]],
    minimum_score: float = 0.08,
    limit: int = 6,
) -> list[dict[str, float | str]]:
    tags: list[dict[str, float | str]] = []
    seen: set[str] = set()
    for item in predictions:
        score = float(item["score"])
        if score < minimum_score:
            continue
        parts = str(item["label"]).split("---")
        leaf = parts[-1].replace("_", " ").casefold()
        label = f"{parts[0].casefold()} {leaf}" if leaf == "fusion" and len(parts) > 1 else leaf
        if label in seen:
            continue
        tags.append({"tag": label, "confidence": score})
        seen.add(label)
        if len(tags) == limit:
            break
    return tags
