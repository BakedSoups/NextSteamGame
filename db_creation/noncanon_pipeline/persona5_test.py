from __future__ import annotations

import json
import sys
from pathlib import Path


DEFAULT_APPID = "1687950"


def main() -> int:
    db_creation_dir = Path(__file__).resolve().parent.parent
    if str(db_creation_dir) not in sys.path:
        sys.path.insert(0, str(db_creation_dir))

    from noncanon_pipeline.pipeline import run_single_game

    appid = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_APPID
    result = run_single_game(appid)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
