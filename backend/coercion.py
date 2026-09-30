from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any


def normalize_search_text(text: str) -> str:
    # The loader and search API must produce the same indexed title tokens.
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(lowered.split())


def coerce_json_dict(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def coerce_json_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
    return []


def unique_appids(raw_appids: Iterable[Any]) -> list[int]:
    """Coerce valid IDs and deduplicate without changing retrieval/rank order."""
    appids: list[int] = []
    seen: set[int] = set()
    for raw_appid in raw_appids:
        try:
            appid = int(raw_appid)
        except (TypeError, ValueError):
            continue
        if appid not in seen:
            seen.add(appid)
            appids.append(appid)
    return appids
