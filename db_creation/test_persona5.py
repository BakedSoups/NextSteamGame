#!/usr/bin/env python3

from __future__ import annotations

import json

from noncanon_pipeline.pipeline import run_single_game
from paths import analysis_dir


APP_ID = "1687950"
GAME_NAME = "Persona 5 Royal"
OUTPUT_PATH = analysis_dir() / "persona5_single_game.json"


def main() -> int:
    print(f"Running single-game non-canon test for {GAME_NAME} ({APP_ID})")
    result = run_single_game(APP_ID)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote output to {OUTPUT_PATH}")
    print("Metadata preview:")
    print(json.dumps(result.get("metadata", {}), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
