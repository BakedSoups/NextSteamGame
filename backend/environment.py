"""Load the project's simple KEY=value settings consistently across entry points."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_project_env(env_path: Path | None = None) -> None:
    """Apply .env defaults without overriding shell or container configuration.

    Values are literal: shell expansion and inline-comment parsing are deliberately
    unsupported, matching the original entry-point loaders.
    """
    env_path = env_path if env_path is not None else PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        # An explicitly empty environment value is still an override.
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip("\"'")
