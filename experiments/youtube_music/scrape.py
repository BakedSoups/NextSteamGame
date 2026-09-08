from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .youtube import Candidate, select_tracks


def seconds_to_iso8601(seconds: int) -> str:
    seconds = max(0, int(seconds))
    return f"PT{seconds // 3600}H{seconds % 3600 // 60}M{seconds % 60}S"


class YtDlpMetadataDiscovery:
    """Metadata-only discovery fallback that does not download media."""

    def __init__(self, result_count: int = 20, timeout: int = 180) -> None:
        if not shutil.which("yt-dlp"):
            raise RuntimeError("yt-dlp is required for metadata discovery")
        self.result_count = result_count
        self.timeout = timeout

    def discover(self, game_name: str, appid: int | None = None) -> dict[str, Any]:
        query = f"{game_name} official soundtrack OST"
        process = subprocess.run(
            [
                "yt-dlp", "--no-playlist", "--skip-download", "--dump-json",
                f"ytsearch{self.result_count}:{query}",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        candidates: list[Candidate] = []
        errors: list[str] = []
        for line in process.stdout.splitlines():
            try:
                item = json.loads(line)
                candidates.append(Candidate(
                    video_id=str(item.get("id", "")),
                    title=str(item.get("title", "")),
                    channel=str(item.get("channel") or item.get("uploader") or ""),
                    view_count=int(item.get("view_count") or 0),
                    duration=seconds_to_iso8601(int(item.get("duration") or 0)),
                    source_kind="ost_track",
                ))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                errors.append(str(exc))
        selected = select_tracks(candidates, game_name)
        return {
            "appid": appid,
            "game_name": game_name,
            "strategy": "ost" if selected else "none",
            "discovery_provider": "yt-dlp-metadata",
            "query": query,
            "candidate_count": len(candidates),
            "selected": selected,
            "errors": errors,
        }


def acquire_authorized_audio(
    video_id: str,
    destination: Path,
    authorized: bool = False,
    timeout: int = 600,
) -> Path:
    """Acquire audio only after the caller confirms they have permission."""
    if not authorized:
        raise PermissionError("Audio acquisition requires explicit rights confirmation")
    if not shutil.which("yt-dlp") or not shutil.which("ffmpeg"):
        raise RuntimeError("yt-dlp and ffmpeg are required for audio acquisition")
    destination.parent.mkdir(parents=True, exist_ok=True)
    template = str(destination.with_suffix(".%(ext)s"))
    subprocess.run(
        [
            "yt-dlp", "--no-playlist", "--extract-audio", "--audio-format", "wav",
            "--postprocessor-args", "ffmpeg:-ac 1 -ar 16000 -sample_fmt s16",
            "--output", template, f"https://www.youtube.com/watch?v={video_id}",
        ],
        check=True,
        timeout=timeout,
    )
    wav_path = destination.with_suffix(".wav")
    if not wav_path.exists():
        raise RuntimeError(f"Audio conversion did not create {wav_path}")
    return wav_path
