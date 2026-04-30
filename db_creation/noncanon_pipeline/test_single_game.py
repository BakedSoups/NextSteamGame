from __future__ import annotations

import json
from pathlib import Path


APPID = "1599600"
WRITE_OUTPUT = True


def _output_path(appid: str) -> Path:
    return Path(__file__).resolve().parent.parent / "analysis" / f"single_game_semantics_{appid}.json"


def main() -> int:
    db_creation_dir = Path(__file__).resolve().parent.parent
    import sys

    if str(db_creation_dir) not in sys.path:
        sys.path.insert(0, str(db_creation_dir))

    from noncanon_pipeline.pipeline import run_single_game
    from noncanon_pipeline.llm.review_sampling import sample_reviews

    result = run_single_game(APPID)
    result["prompt_reviews"] = sample_reviews(result["review_samples"])
    if WRITE_OUTPUT:
        output_path = _output_path(APPID)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Output JSON: {output_path}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
