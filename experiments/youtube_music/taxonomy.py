from __future__ import annotations

from typing import Any

VAGUE_STYLES = {
    "abstract", "experimental", "field recording", "music hall", "noise",
    "promotional", "score", "soundtrack", "theme",
}
NON_MUSIC_FAMILY = "non-music"
TRAIT_STYLES = {
    "ambient", "chiptune", "dark ambient", "downtempo", "drone", "lo-fi",
    "modern classical", "new age", "sound collage",
}


def split_style(label: str) -> tuple[str, str]:
    parts = label.split("---", 1)
    family = parts[0].replace("_", " ").strip().casefold()
    style = (parts[1] if len(parts) > 1 else parts[0]).replace("_", " ").strip().casefold()
    if family == "jazz" and style == "fusion":
        style = "jazz fusion"
    return family, style


def _supported(item: dict[str, Any], track_count: int) -> bool:
    score = float(item.get("score", 0))
    evidence = int(item.get("evidence_count", 1))
    return score >= 0.22 or (track_count >= 2 and evidence >= 2 and score >= 0.07)


def _ranked_unique(items: list[tuple[str, float]], limit: int) -> list[dict[str, float | str]]:
    best: dict[str, float] = {}
    for label, score in items:
        best[label] = max(best.get(label, 0.0), score)
    return [
        {"tag": label, "confidence": score}
        for label, score in sorted(best.items(), key=lambda pair: pair[1], reverse=True)[:limit]
    ]


def build_music_profile(
    genre_predictions: list[dict[str, Any]],
    instrument_predictions: list[dict[str, Any]],
    track_count: int,
) -> dict[str, Any]:
    families: list[tuple[str, float]] = []
    subgenres: list[tuple[str, float]] = []
    traits: list[tuple[str, float]] = []
    suppressed: list[str] = []

    for item in genre_predictions:
        family, style = split_style(str(item.get("label", "")))
        score = float(item.get("score", 0))
        if not _supported(item, track_count):
            continue
        if family == NON_MUSIC_FAMILY or style in VAGUE_STYLES:
            suppressed.append(style)
            continue
        families.append((family, score))
        if style in TRAIT_STYLES:
            traits.append((style, score))
        elif style != family:
            subgenres.append((style, score))

    instruments = [
        (str(item.get("label", "")).replace("_", " ").casefold(), float(item.get("score", 0)))
        for item in instrument_predictions
        if float(item.get("score", 0)) >= 0.12
        or (track_count >= 2 and int(item.get("evidence_count", 1)) >= 2 and float(item.get("score", 0)) >= 0.06)
    ]
    primary_genres = _ranked_unique(families, 3)
    specific_styles = _ranked_unique(subgenres, 5)
    musical_traits = _ranked_unique(traits, 4)
    instrument_tags = _ranked_unique(instruments, 6)
    identity = specific_styles + [item for item in primary_genres if item["tag"] not in {x["tag"] for x in specific_styles}]
    return {
        "music_primary": identity[0]["tag"] if identity else "",
        "music_secondary": identity[1]["tag"] if len(identity) > 1 else "",
        "primary_genres": primary_genres,
        "subgenres": specific_styles,
        "musical_traits": musical_traits,
        "instruments": instrument_tags,
        "track_count": track_count,
        "suppressed_vague_labels": sorted(set(suppressed)),
    }
