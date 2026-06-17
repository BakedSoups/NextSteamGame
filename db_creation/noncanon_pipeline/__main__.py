from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    db_creation_dir = Path(__file__).resolve().parent.parent
    if str(db_creation_dir) not in sys.path:
        sys.path.insert(0, str(db_creation_dir))

    from initial_noncanon_db import main as run_initial_noncanon_db

    return run_initial_noncanon_db()


if __name__ == "__main__":
    raise SystemExit(main())
