from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from .audio import SpectralBaselineClassifier, detect_music_segments, read_wav_mono
from .cnn import EssentiaEffNetClassifier, aggregate_predictions, ensure_models, website_tags
from .scrape import YtDlpMetadataDiscovery, acquire_authorized_audio
from .youtube import YouTubeDiscovery


def output_path(appid: int | None, suffix: str) -> Path:
    directory = Path(__file__).resolve().parent / "output"
    directory.mkdir(parents=True, exist_ok=True)
    identifier = appid if appid is not None else "unknown"
    return directory / f"{identifier}.{suffix}.json"


def discover(args: argparse.Namespace) -> int:
    result = YouTubeDiscovery(os.getenv("YOUTUBE_API_KEY", "")).discover(args.game, args.appid)
    path = output_path(args.appid, "discovery")
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(path)
    return 0


def scrape(args: argparse.Namespace) -> int:
    result = YtDlpMetadataDiscovery(result_count=args.results).discover(args.game, args.appid)
    path = output_path(args.appid, "discovery")
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(path)
    return 0


def acquire(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    audio_dir = Path(args.audio_dir)
    acquired = []
    for item in manifest.get("selected", []):
        video_id = str(item["video_id"])
        path = acquire_authorized_audio(
            video_id,
            audio_dir / video_id,
            authorized=args.confirm_authorized,
        )
        acquired.append({"video_id": video_id, "audio_path": str(path)})
    report = {"manifest": str(manifest_path), "acquired": acquired}
    path = output_path(manifest.get("appid"), "audio")
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(path)
    return 0


def download_models(args: argparse.Namespace) -> int:
    for name, path in ensure_models(Path(args.model_dir)).items():
        print(f"{name}: {path}")
    return 0


def classify(args: argparse.Namespace) -> int:
    model_paths = ensure_models(Path(args.model_dir))
    classifier = EssentiaEffNetClassifier(**model_paths)
    tracks = []
    predictions = []
    for value in args.audio:
        audio_path = Path(value)
        result = classifier.predict_file(audio_path)
        predictions.append(result)
        tracks.append({"audio_path": str(audio_path), **result})
    genres = aggregate_predictions(predictions, "genres")
    instruments = aggregate_predictions(predictions, "instruments")
    report = {
        "appid": args.appid,
        "model": "essentia-discogs-effnet",
        "tracks": tracks,
        "aggregate": {
            "genres": genres,
            "instruments": instruments,
        },
        "website_tags": {
            "genres": website_tags(genres),
            "instruments": website_tags(instruments, minimum_score=0.10),
        },
    }
    path = output_path(args.appid, "classification")
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(path)
    return 0


def analyze(args: argparse.Namespace) -> int:
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    audio, sample_rate = read_wav_mono(Path(args.audio))
    segments = detect_music_segments(audio, sample_rate) if args.source_kind == "walkthrough" else []
    if not segments:
        segments = detect_music_segments(audio, sample_rate, min_segment_seconds=max(30, len(audio) / sample_rate))
    classifier = SpectralBaselineClassifier()
    results = []
    for segment in segments:
        start = int(segment.start_seconds * sample_rate)
        end = int(segment.end_seconds * sample_rate)
        results.append({"segment": asdict(segment), "predictions": classifier.predict(audio[start:end], sample_rate)})
    report = {"discovery": manifest, "audio": str(args.audio), "sample_rate": sample_rate, "segments": results}
    path = output_path(manifest.get("appid"), "analysis")
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(path)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Experimental YouTube game-music analyzer")
    commands = root.add_subparsers(dest="command", required=True)
    discovery = commands.add_parser("discover")
    discovery.add_argument("--appid", type=int)
    discovery.add_argument("--game", required=True)
    discovery.set_defaults(handler=discover)
    scraping = commands.add_parser("scrape", help="Discover and rank metadata without an API key")
    scraping.add_argument("--appid", type=int)
    scraping.add_argument("--game", required=True)
    scraping.add_argument("--results", type=int, default=20)
    scraping.set_defaults(handler=scrape)
    acquisition = commands.add_parser("acquire", help="Acquire audio that you have rights to analyze")
    acquisition.add_argument("--manifest", required=True)
    acquisition.add_argument("--audio-dir", default="experiments/youtube_music/audio_cache")
    acquisition.add_argument("--confirm-authorized", action="store_true", required=True)
    acquisition.set_defaults(handler=acquire)
    models = commands.add_parser("download-models")
    models.add_argument("--model-dir", default="experiments/youtube_music/models")
    models.set_defaults(handler=download_models)
    classification = commands.add_parser("classify")
    classification.add_argument("--appid", type=int)
    classification.add_argument("--audio", nargs="+", required=True)
    classification.add_argument("--model-dir", default="experiments/youtube_music/models")
    classification.set_defaults(handler=classify)
    analysis = commands.add_parser("analyze")
    analysis.add_argument("--manifest", required=True)
    analysis.add_argument("--audio", required=True)
    analysis.add_argument("--source-kind", choices=("ost", "walkthrough"), required=True)
    analysis.set_defaults(handler=analyze)
    return root


def main() -> int:
    args = parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
