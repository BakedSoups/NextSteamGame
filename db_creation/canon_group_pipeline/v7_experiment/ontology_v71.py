from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from db_creation.canon_pipeline.layer_1_normalization import format_display, normalize_tag
from db_creation.canon_group_pipeline.v7_experiment.ontology_v7 import OllamaClient, TagPair


HERE = Path(__file__).resolve().parent
GOLD_PATH = HERE / "sample_review_gold.json"
EQUIVALENCE_STATES = ("equivalent", "not_equivalent", "uncertain")
FRANCHISE_WORDS = {
    "persona", "pokemon", "mario", "zelda", "sonic", "warhammer", "star wars",
    "final fantasy", "dragon quest", "shin megami tensei",
}
MEANINGFUL_QUALIFIERS = {
    "near", "inspired", "casual", "single player", "multiplayer", "seasonal",
    "psychological", "supernatural", "tactical", "arcade", "adult",
}
CONFLICT_GROUPS = (
    {"platformer", "racing", "shooter", "puzzle", "rpg", "strategy"},
    {"soundtrack", "combat", "narrative", "setting"},
)


@dataclass(frozen=True)
class EquivalenceDecision:
    state: str
    confidence: float
    reason: str
    source: str
    blocker: str = ""

    @property
    def equivalent(self) -> bool:
        return self.state == "equivalent" and self.confidence >= 0.85


def _normalized_for_equivalence(tag: str) -> str:
    value = normalize_tag(tag)
    replacements = {
        "collectable": "collectible",
        "story": "narrative",
    }
    return " ".join(replacements.get(token, token) for token in value.split())


def deterministic_decision(pair: TagPair) -> EquivalenceDecision | None:
    left = _normalized_for_equivalence(pair.left)
    right = _normalized_for_equivalence(pair.right)
    if left == right:
        return EquivalenceDecision("equivalent", 1.0, "Same after deterministic normalization", "normalizer")

    left_words = set(left.split())
    right_words = set(right.split())
    for franchise in FRANCHISE_WORDS:
        in_left = franchise in left
        in_right = franchise in right
        if in_left != in_right:
            return EquivalenceDecision(
                "not_equivalent", 1.0, "Franchise-specific and generic concepts cannot be synonyms",
                "hard_rule", "franchise_specificity",
            )

    for qualifier in MEANINGFUL_QUALIFIERS:
        in_left = qualifier in left
        in_right = qualifier in right
        if in_left != in_right and (left_words & right_words):
            return EquivalenceDecision(
                "not_equivalent", 0.99, f"Meaningful qualifier differs: {qualifier}",
                "hard_rule", "meaningful_qualifier",
            )

    for conflict_group in CONFLICT_GROUPS:
        left_kinds = left_words & conflict_group
        right_kinds = right_words & conflict_group
        if left_kinds and right_kinds and left_kinds.isdisjoint(right_kinds):
            return EquivalenceDecision(
                "not_equivalent", 1.0, "Conflicting core game concepts",
                "hard_rule", "conflicting_head_concept",
            )

    if ("concern" in left_words) != ("concern" in right_words):
        return EquivalenceDecision(
            "not_equivalent", 0.99, "A concern is not the same as a positive game trait",
            "hard_rule", "quality_vs_concern",
        )
    return None


def _judge_equivalence_batch(client: OllamaClient, pairs: list[TagPair], model: str) -> list[EquivalenceDecision]:
    schema = {
        "type": "object",
        "properties": {"judgments": {"type": "array", "minItems": len(pairs), "maxItems": len(pairs), "items": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "state": {"type": "string", "enum": list(EQUIVALENCE_STATES)},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "reason": {"type": "string", "maxLength": 120},
            },
            "required": ["id", "state", "confidence", "reason"],
        }}},
        "required": ["judgments"],
    }
    payload = [{"id": index, "left": pair.left, "right": pair.right, "facet": pair.context}
               for index, pair in enumerate(pairs)]
    prompt = f"""Decide only whether each pair of video-game tags is semantically interchangeable.
Equivalent means either tag can replace the other on every game without losing, adding, or
specializing meaning. Subtypes, parent concepts, siblings, co-occurring ideas, franchise-specific
terms, and merely related phrases are not equivalent. Use uncertain when context could change the
answer. Do not choose canonical labels or classify hierarchy.

Examples:
- collectible hunting / collectable hunting: equivalent
- survival horror / horror: not_equivalent
- noir world / noir city: not_equivalent
- character fusion / persona fusion system: not_equivalent

Pairs: {json.dumps(payload, ensure_ascii=False)}
"""
    response = client._post("/api/chat", {
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "stream": False, "think": False, "format": schema, "keep_alive": "10m",
        "options": {"temperature": 0, "num_predict": 1000},
    })
    parsed = json.loads(response["message"]["content"])
    items = parsed["judgments"]
    if len(items) != len(pairs):
        raise ValueError(f"Equivalence judge returned {len(items)} results for {len(pairs)} pairs")
    return [EquivalenceDecision(item["state"], float(item["confidence"]),
                                item["reason"], "model") for item in items]


def judge_equivalence(client: OllamaClient, pairs: list[TagPair], model: str, batch_size: int = 1) -> list[EquivalenceDecision]:
    decisions = []
    for start in range(0, len(pairs), batch_size):
        decisions.extend(_judge_equivalence_batch(client, pairs[start:start + batch_size], model))
    return decisions


def _choose_label_batch(client: OllamaClient, pairs: list[TagPair], model: str) -> list[str]:
    if not pairs:
        return []
    schema = {
        "type": "object",
        "properties": {"labels": {"type": "array", "minItems": len(pairs), "maxItems": len(pairs), "items": {
            "type": "object",
            "properties": {"id": {"type": "integer"}, "label": {"type": "string"}},
            "required": ["id", "label"],
        }}}, "required": ["labels"],
    }
    payload = [{"id": i, "left": p.left, "right": p.right, "facet": p.context}
               for i, p in enumerate(pairs)]
    prompt = f"""Choose one clean canonical video-game tag for each already-confirmed equivalent pair.
Prefer the clearest established community phrase. Use singular concepts, correct spelling, and
concise natural wording. Avoid awkward generated wording and franchise names. You may improve the
wording instead of copying either input, but do not broaden or narrow its meaning.

Pairs: {json.dumps(payload, ensure_ascii=False)}
"""
    response = client._post("/api/chat", {
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "stream": False, "think": False, "format": schema, "keep_alive": "10m",
        "options": {"temperature": 0, "num_predict": 400},
    })
    parsed = json.loads(response["message"]["content"])
    items = parsed["labels"]
    if len(items) < len(pairs):
        raise ValueError(f"Label selector returned {len(items)} results for {len(pairs)} pairs")
    return [format_display(item["label"]) for item in items[:len(pairs)]]


def choose_canonical_labels(client: OllamaClient, pairs: list[TagPair], model: str, batch_size: int = 1) -> list[str]:
    labels = []
    for start in range(0, len(pairs), batch_size):
        labels.extend(_choose_label_batch(client, pairs[start:start + batch_size], model))
    return [validated_canonical_label(pair, label) for pair, label in zip(pairs, labels)]


def validated_canonical_label(pair: TagPair, proposed: str) -> str:
    """Reject fluent labels that silently broaden, narrow, or rename the concept."""
    proposed_tokens = set(_normalized_for_equivalence(proposed).split())
    source_tokens = set(_normalized_for_equivalence(pair.left).split())
    replacement_tokens = set(_normalized_for_equivalence(pair.right).split())
    known_vocabulary = source_tokens | replacement_tokens
    preserves_source = bool(source_tokens) and len(proposed_tokens & source_tokens) / len(source_tokens) >= 0.8
    introduces_new_meaning = bool(proposed_tokens - known_vocabulary)
    if not preserves_source or introduces_new_meaning:
        return format_display(pair.left)
    return format_display(proposed)


def run_staged_pipeline(pairs: list[TagPair], client: OllamaClient, model: str) -> list[dict]:
    decisions: list[EquivalenceDecision | None] = [deterministic_decision(pair) for pair in pairs]
    pending_indexes = [index for index, decision in enumerate(decisions) if decision is None]
    model_decisions = judge_equivalence(client, [pairs[index] for index in pending_indexes], model)
    for index, decision in zip(pending_indexes, model_decisions):
        decisions[index] = decision

    accepted_indexes = [index for index, decision in enumerate(decisions) if decision and decision.equivalent]
    labels = choose_canonical_labels(client, [pairs[index] for index in accepted_indexes], model)
    label_by_index = dict(zip(accepted_indexes, labels))
    rows = []
    for index, (pair, decision) in enumerate(zip(pairs, decisions)):
        assert decision is not None
        outcome = label_by_index.get(index, format_display(pair.left))
        rows.append({**asdict(pair), **asdict(decision), "safe_to_replace": decision.equivalent,
                     "canonical_outcome": outcome})
    return rows


def load_gold() -> dict[tuple[str, str], dict]:
    entries = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    return {(normalize_tag(item["left"]), normalize_tag(item["right"])): item for item in entries}
