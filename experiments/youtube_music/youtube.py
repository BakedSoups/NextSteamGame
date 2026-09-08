from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Any, Iterable

import requests

API_ROOT = "https://www.googleapis.com/youtube/v3"

NOISY_TITLE_TERMS = {
    "ambience", "ambient", "chill", "compilation", "extended", "full album",
    "full soundtrack", "hours", "mix", "relax", "sleep", "study", "workout",
}
OFFICIAL_CHANNEL_TERMS = {
    "atlus", "bandai namco", "bethesda", "capcom", "devolver", "ea music",
    "game music", "microsoft", "nintendo", "playstation", "sega", "square enix",
    "ubisoft", "xbox",
}


@dataclass(frozen=True)
class Candidate:
    video_id: str
    title: str
    channel: str
    view_count: int
    duration: str = ""
    source_kind: str = "video"
    playlist_id: str = ""
    playlist_title: str = ""
    playlist_channel: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def chunks(values: list[str], size: int = 50) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def iso8601_seconds(value: str) -> int:
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def normalized_track_title(title: str, game_name: str = "") -> str:
    value = title.casefold()
    for removable in (game_name.casefold(), "official soundtrack", "soundtrack", "ost", "audio"):
        if removable:
            value = value.replace(removable, " ")
    value = re.sub(r"\([^)]*\)|\[[^]]*\]|【[^】]*】", " ", value)
    return " ".join(re.findall(r"[a-z0-9]+", value))


def rank_track(candidate: Candidate, game_name: str) -> tuple[float, list[str]]:
    title = candidate.title.casefold()
    channel = candidate.channel.casefold()
    playlist = candidate.playlist_title.casefold()
    combined_source = f"{channel} {candidate.playlist_channel.casefold()}"
    seconds = iso8601_seconds(candidate.duration)
    signals: list[str] = []
    score = min(math.log10(candidate.view_count + 1) / 8, 0.75) * 0.30

    if 60 <= seconds <= 720:
        score += 0.20
        signals.append("track_length")
    elif 30 <= seconds <= 1200:
        score += 0.06
        signals.append("plausible_length")
    else:
        score -= 0.30
        signals.append("unlikely_track_length")

    game_tokens = {token for token in re.findall(r"[a-z0-9]+", game_name.casefold()) if len(token) > 2}
    if game_tokens and game_tokens.intersection(re.findall(r"[a-z0-9]+", f"{title} {playlist}")):
        score += 0.12
        signals.append("game_title_match")
    if any(term in playlist for term in ("soundtrack", " ost", "music")):
        score += 0.14
        signals.append("soundtrack_playlist")
    if any(term in combined_source for term in OFFICIAL_CHANNEL_TERMS) or "official" in combined_source:
        score += 0.28
        signals.append("publisher_or_official_channel")
    elif channel.endswith(" - topic"):
        score += 0.16
        signals.append("youtube_topic_channel")

    noisy = sorted(term for term in NOISY_TITLE_TERMS if term in title)
    if noisy:
        score -= min(0.42, 0.18 + 0.06 * len(noisy))
        signals.append("penalized:" + ",".join(noisy))
    return round(max(0.0, min(score, 1.0)), 4), signals


def select_tracks(candidates: Iterable[Candidate], game_name: str, limit: int = 3) -> list[dict[str, Any]]:
    ranked: list[tuple[float, Candidate, list[str]]] = []
    for candidate in candidates:
        score, signals = rank_track(candidate, game_name)
        ranked.append((score, candidate, signals))
    ranked.sort(key=lambda item: (item[0], item[1].view_count), reverse=True)

    selected: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    seen_video_ids: set[str] = set()
    for score, candidate, signals in ranked:
        identity = normalized_track_title(candidate.title, game_name) or candidate.video_id
        if candidate.video_id in seen_video_ids or identity in seen_titles:
            continue
        # Very long uploads and clearly noisy results are useful only as fallback evidence.
        if iso8601_seconds(candidate.duration) > 1200 or score < 0.20:
            continue
        record = candidate.to_dict()
        record.update({
            "ranking_score": score,
            "confidence": "high" if score >= 0.68 else "medium" if score >= 0.45 else "low",
            "signals": signals,
            "provenance": {
                "youtube_video_id": candidate.video_id,
                "playlist_id": candidate.playlist_id,
                "playlist_title": candidate.playlist_title,
                "playlist_channel": candidate.playlist_channel,
            },
        })
        selected.append(record)
        seen_video_ids.add(candidate.video_id)
        seen_titles.add(identity)
        if len(selected) == limit:
            break
    return selected


class YouTubeDiscovery:
    def __init__(self, api_key: str, timeout: int = 20) -> None:
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY is required")
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, resource: str, **params: Any) -> dict[str, Any]:
        response = self.session.get(
            f"{API_ROOT}/{resource}",
            params={**params, "key": self.api_key},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def search(self, query: str, resource_type: str, max_results: int = 10) -> list[dict[str, Any]]:
        payload = self._get(
            "search",
            part="id,snippet",
            q=query,
            type=resource_type,
            maxResults=min(max_results, 50),
            safeSearch="moderate",
        )
        return list(payload.get("items", []))

    def playlist_video_ids(self, playlist_id: str, max_items: int = 200) -> list[str]:
        ids: list[str] = []
        page_token = ""
        while len(ids) < max_items:
            payload = self._get(
                "playlistItems",
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=page_token or None,
            )
            ids.extend(
                item.get("contentDetails", {}).get("videoId", "")
                for item in payload.get("items", [])
            )
            ids = [video_id for video_id in ids if video_id]
            page_token = str(payload.get("nextPageToken", ""))
            if not page_token:
                break
        return ids[:max_items]

    def video_details(self, video_ids: list[str]) -> list[Candidate]:
        candidates: list[Candidate] = []
        for batch in chunks(list(dict.fromkeys(video_ids))):
            payload = self._get(
                "videos",
                part="snippet,statistics,contentDetails",
                id=",".join(batch),
            )
            for item in payload.get("items", []):
                snippet = item.get("snippet", {})
                candidates.append(
                    Candidate(
                        video_id=str(item.get("id", "")),
                        title=str(snippet.get("title", "")),
                        channel=str(snippet.get("channelTitle", "")),
                        view_count=int(item.get("statistics", {}).get("viewCount", 0)),
                        duration=str(item.get("contentDetails", {}).get("duration", "")),
                    )
                )
        return candidates

    def discover(self, game_name: str, appid: int | None = None) -> dict[str, Any]:
        playlist_hits = self.search(f'"{game_name}" official soundtrack OST', "playlist", 8)
        playlists: list[dict[str, Any]] = []
        track_pool: list[Candidate] = []
        for hit in playlist_hits:
            playlist_id = str(hit.get("id", {}).get("playlistId", ""))
            if not playlist_id:
                continue
            snippet = hit.get("snippet", {})
            playlist_title = str(snippet.get("title", ""))
            playlist_channel = str(snippet.get("channelTitle", ""))
            ids = self.playlist_video_ids(playlist_id)
            tracks = self.video_details(ids)
            playlists.append({
                "playlist_id": playlist_id,
                "title": playlist_title,
                "channel": playlist_channel,
                "track_count": len(tracks),
            })
            track_pool.extend(
                Candidate(**{
                    **track.to_dict(),
                    "source_kind": "ost_track",
                    "playlist_id": playlist_id,
                    "playlist_title": playlist_title,
                    "playlist_channel": playlist_channel,
                })
                for track in tracks
            )

        top_tracks = select_tracks(track_pool, game_name)
        walkthroughs: list[Candidate] = []
        if not top_tracks:
            hits = self.search(f'"{game_name}" full game walkthrough no commentary', "video", 10)
            ids = [str(hit.get("id", {}).get("videoId", "")) for hit in hits]
            walkthroughs = [
                Candidate(**{**item.to_dict(), "source_kind": "walkthrough"})
                for item in self.video_details([item for item in ids if item])
            ]
            walkthroughs.sort(key=lambda item: item.view_count, reverse=True)

        return {
            "appid": appid,
            "game_name": game_name,
            "strategy": "ost" if top_tracks else "walkthrough",
            "playlists": playlists,
            "selected": top_tracks or [item.to_dict() for item in walkthroughs[:1]],
        }
