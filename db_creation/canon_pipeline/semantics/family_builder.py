from __future__ import annotations

from ..normalization.surface_forms import head_token, tokenize


def build_family_index(tags: list[str]) -> dict[str, list[int]]:
    families: dict[str, list[int]] = {}
    for index, tag in enumerate(tags):
        head = head_token(tokenize(tag))
        families.setdefault(head, []).append(index)
    return families
