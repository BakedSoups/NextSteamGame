from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from .audio import SpectralBaselineClassifier, detect_music_segments, read_wav_mono
from .youtube import YouTubeDiscovery


def output_path(appid: int | None, suffix: str) -> Path:
    directory = Path(__file__).resolve().parent / "output"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{appid or 'unknown'}.{suffix}.json"


def discover(args: argparse.Namespace) -> int:
    result = YouTubeDiscovery(os.getenv("YOUTUBE_API_KEY", "")).discover(args.game, args.appid)
    path = output_path(args.appid, "discovery")
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
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

