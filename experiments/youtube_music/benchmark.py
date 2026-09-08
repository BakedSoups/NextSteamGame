from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .scrape import YtDlpMetadataDiscovery

SAMPLE_GAMES = [
    (1687950, "Persona 5 Royal", {"jazz fusion", "jazz-funk", "acid jazz"}),
    (1113000, "Persona 4 Golden", {"j-pop", "pop rock"}),
    (524220, "NieR:Automata", {"orchestral", "classical", "ambient"}),
    (782330, "DOOM Eternal", {"industrial metal", "heavy metal", "djent"}),
    (1145360, "Hades", {"folk rock", "metal", "mediterranean"}),
    (1091500, "Cyberpunk 2077", {"industrial", "techno", "electronic"}),
    (504230, "Celeste", {"chiptune", "electronic", "ambient"}),
    (391540, "Undertale", {"chiptune", "electronic"}),
    (367520, "Hollow Knight", {"orchestral", "classical", "ambient"}),
    (413150, "Stardew Valley", {"chiptune", "folk", "ambient"}),
    (489830, "The Elder Scrolls V: Skyrim Special Edition", {"orchestral", "classical", "folk"}),
    (292030, "The Witcher 3: Wild Hunt", {"folk", "orchestral", "slavic folk"}),
    (1245620, "Elden Ring", {"orchestral", "choral", "classical"}),
    (374320, "Dark Souls III", {"orchestral", "choral", "classical"}),
    (39210, "FINAL FANTASY XIV Online", {"orchestral", "rock", "classical"}),
    (1462040, "FINAL FANTASY VII REMAKE INTERGRADE", {"orchestral", "rock", "classical"}),
    (1971650, "OCTOPATH TRAVELER II", {"orchestral", "classical", "folk"}),
    (1229240, "Chained Echoes", {"orchestral", "chiptune", "classical"}),
    (268910, "Cuphead", {"big band", "jazz", "ragtime"}),
    (1057090, "Ori and the Will of the Wisps", {"orchestral", "ambient", "classical"}),
    (1086940, "Baldur's Gate 3", {"orchestral", "classical", "folk"}),
    (1328670, "Mass Effect Legendary Edition", {"electronic", "ambient", "orchestral"}),
    (1240440, "Halo Infinite", {"orchestral", "ambient", "rock"}),
    (632360, "Risk of Rain 2", {"progressive rock", "electronic", "ambient"}),
    (219150, "Hotline Miami", {"synthwave", "electronic", "techno"}),
]


def _scrape(game: tuple[int, str, set[str]], results: int) -> dict[str, Any]:
    appid, name, expected = game
    discovery = YtDlpMetadataDiscovery(result_count=results).discover(name, appid)
    selected = discovery.get("selected", [])
    return {
        "appid": appid,
        "game": name,
        "expected_genres": sorted(expected),
        "candidate_count": discovery.get("candidate_count", 0),
        "selected_count": len(selected),
        "selected": [
            {
                "title": item.get("title"),
                "channel": item.get("channel"),
                "confidence": item.get("confidence"),
                "ranking_score": item.get("ranking_score"),
                "video_id": item.get("video_id"),
            }
            for item in selected
        ],
    }


def run(output: Path, workers: int = 4, results: int = 15) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_scrape, game, results): game for game in SAMPLE_GAMES}
        for future in as_completed(futures):
            appid, name, expected = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                rows.append({"appid": appid, "game": name, "expected_genres": sorted(expected), "error": str(exc)})
    rows.sort(key=lambda item: item["game"].casefold())
    report = {
        "sample_size": len(rows),
        "games_with_selection": sum(bool(item.get("selected")) for item in rows),
        "total_selected_tracks": sum(len(item.get("selected", [])) for item in rows),
        "games": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("experiments/youtube_music/output/benchmark-25.json"))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--results", type=int, default=15)
    args = parser.parse_args()
    report = run(args.output, args.workers, args.results)
    print(args.output)
    print(f"games with selections: {report['games_with_selection']}/{report['sample_size']}")
    print(f"selected tracks: {report['total_selected_tracks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
