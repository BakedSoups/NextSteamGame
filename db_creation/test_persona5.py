#!/usr/bin/env python3

from __future__ import annotations

import json

from noncanon_pipeline.progress import complete_appid
from noncanon_pipeline.pipeline import run_single_game
from paths import analysis_dir


APP_ID = "1599600"
GAME_NAME = "PlateUp!"
OUTPUT_PATH = analysis_dir() / "plateup_single_game.json"


def main() -> int:
    print(f"Running single-game non-canon test for {GAME_NAME} ({APP_ID})")
    result = run_single_game(APP_ID)
    complete_appid(APP_ID, "preview_completed", GAME_NAME)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote output to {OUTPUT_PATH}")
    db_payload = {
        "appid": int(result["appid"]),
        "name": GAME_NAME,
        "review_samples_json": json.dumps(result.get("review_samples", {}), ensure_ascii=False, sort_keys=True),
        "vectors_json": json.dumps(result.get("vectors", {}), ensure_ascii=False, sort_keys=True),
        "metadata_json": json.dumps(result.get("metadata", {}), ensure_ascii=False, sort_keys=True),
    }

    print("\nDB insert preview")
    print(f"appid: {db_payload['appid']}")
    print(f"name: {db_payload['name']}")
    print("\nvectors_json:")
    print(json.dumps(result.get("vectors", {}), indent=2, ensure_ascii=False, sort_keys=True))
    print("\nmetadata_json:")
    print(json.dumps(result.get("metadata", {}), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
