import json
import os
from math import floor
import time
from typing import Dict, List

from openai import OpenAI
from openai import RateLimitError
from pydantic import BaseModel, field_validator

from .errors import CreditsExhaustedError
from .review_sampling import sample_reviews


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

APPEAL_AXIS_KEYS = (
    "challenge",
    "complexity",
    "pace",
    "narrative_focus",
    "social_energy",
    "creativity",
)


class GenreTree(BaseModel):
    primary: List[str]
    sub: List[str]
    traits: List[str]


class GameMetadata(BaseModel):
    micro_tags: List[str]
    signature_tag: str
    appeal_axes: Dict[str, int]
    genre_tree: GenreTree

    @field_validator("micro_tags")
    def validate_micro_tags(cls, value: List[str]) -> List[str]:
        return list(dict.fromkeys(value))[:15]

    @field_validator("signature_tag")
    def validate_signature_tag(cls, value: str) -> str:
        cleaned = " ".join(str(value).strip().split())
        if not cleaned:
            raise ValueError("signature_tag must not be empty")
        return cleaned[:80]

    @field_validator("appeal_axes")
    def validate_appeal_axes(cls, value: Dict[str, int]) -> Dict[str, int]:
        cleaned: Dict[str, int] = {}
        for key in APPEAL_AXIS_KEYS:
            raw = value.get(key, 50)
            try:
                score = int(raw)
            except (TypeError, ValueError):
                score = 50
            cleaned[key] = max(0, min(100, score))
        return cleaned


class GameVectors(BaseModel):
    mechanics: Dict[str, int]
    narrative: Dict[str, int]
    vibe: Dict[str, int]
    structure_loop: Dict[str, int]
    uniqueness: Dict[str, int]

    @field_validator("*")
    def validate_sum(cls, value: Dict[str, int]) -> Dict[str, int]:
        total = sum(value.values())
        if total != 100:
            raise ValueError(f"Vector must sum to 100, got {total}")
        return value


class GameSemantics(BaseModel):
    metadata: GameMetadata
    vectors: GameVectors


VECTOR_KEYS = ("mechanics", "narrative", "vibe", "structure_loop", "uniqueness")
RETRY_DELAY_SECONDS = 2.0
MAX_SEMANTICS_RETRIES = 6


def _build_prompt(reviews: List[str]) -> str:
    joined = "\n\n---\n\n".join(review[:600] for review in reviews)

    return f"""
Generate structured game semantics for a video game from player reviews.

RULES:
- tags must be 1-2 words
- be specific, not generic
- avoid duplicates and close synonyms
- micro_tags must contain at most 15 entries
- signature_tag must be a short 2-4 word phrase describing the game's defining hook
- appeal_axes must include exactly these integer 0-100 keys:
  challenge, complexity, pace, narrative_focus, social_energy, creativity
- genre_tree must stay flat
- vector weights must be integers
- EACH vector object sums to EXACTLY 100 on its own
- do NOT make the five top-level vector categories sum to 100 together
- every vector category should usually contain 3-6 tags, not one placeholder tag

OUTPUT JSON:
{{
  "metadata": {{
    "micro_tags": [tags],
    "signature_tag": "portal platformer",
    "appeal_axes": {{
      "challenge": 55,
      "complexity": 40,
      "pace": 65,
      "narrative_focus": 20,
      "social_energy": 10,
      "creativity": 85
    }},
    "genre_tree": {{
      "primary": [broad genres],
      "sub": [recognized subgenres],
      "traits": [defining traits]
    }}
  }},
  "vectors": {{
    "mechanics": {{"combat": 40, "movement": 35, "timing": 25}},
    "narrative": {{"betrayal": 50, "mystery": 30, "grief": 20}},
    "vibe": {{"tense": 45, "bleak": 30, "melancholic": 25}},
    "structure_loop": {{"mission based": 45, "exploration": 30, "backtracking": 25}},
    "uniqueness": {{"time loop": 50, "memory shifts": 30, "identity play": 20}}
  }}
}}

metadata.micro_tags:
- short, searchable descriptors

metadata.signature_tag:
- exactly one concise hook
- 2-4 words when possible
- should capture the game's defining identity, not just restate a broad genre
- examples: "portal platformer", "city life sim", "time loop mystery"

metadata.appeal_axes:
- challenge = how demanding or punishing it feels
- complexity = how mentally/systemically dense it feels
- pace = how fast and energetic moment-to-moment play feels
- narrative_focus = how strongly the game centers story/characters
- social_energy = how much the experience depends on other players or social dynamics
- creativity = how much expression, experimentation, or player-made problem solving it invites
- use integer values from 0 to 100

metadata.genre_tree:
- primary = broad categories like Action, RPG, Strategy
- sub = recognized subgenres like Soulslike, Roguelike, Metroidvania
- traits = defining structural or gameplay traits

vectors:
- mechanics = gameplay systems
- narrative = themes and subject matter
- vibe = emotional tone or feel
- structure_loop = how gameplay flows over time
- uniqueness = what makes the game distinct

REVIEWS:
{joined}
"""


def _normalize_weight_map(weight_map: Dict[str, int]) -> Dict[str, int]:
    cleaned: Dict[str, int] = {}
    for raw_tag, raw_weight in weight_map.items():
        tag = str(raw_tag).strip()
        if not tag:
            continue
        try:
            weight = int(raw_weight)
        except (TypeError, ValueError):
            continue
        if weight > 0:
            cleaned[tag] = cleaned.get(tag, 0) + weight

    if not cleaned:
        raise ValueError("Vector category contained no positive integer weights.")

    total = sum(cleaned.values())
    if total == 100:
        return cleaned

    scaled = {tag: (weight * 100.0) / total for tag, weight in cleaned.items()}
    normalized = {tag: floor(value) for tag, value in scaled.items()}
    remainder = 100 - sum(normalized.values())

    if remainder > 0:
        ranked = sorted(
            scaled,
            key=lambda tag: (scaled[tag] - normalized[tag], cleaned[tag], tag),
            reverse=True,
        )
        for tag in ranked[:remainder]:
            normalized[tag] += 1
    elif remainder < 0:
        ranked = sorted(
            normalized,
            key=lambda tag: (normalized[tag] - scaled[tag], normalized[tag], tag),
            reverse=True,
        )
        for tag in ranked:
            if remainder == 0:
                break
            if normalized[tag] > 1:
                normalized[tag] -= 1
                remainder += 1

    return {tag: weight for tag, weight in normalized.items() if weight > 0}


def _repair_semantics_payload(payload: Dict) -> Dict:
    repaired = dict(payload)
    vectors = dict(repaired.get("vectors") or {})
    repaired_vectors: Dict[str, Dict[str, int]] = {}

    for key in VECTOR_KEYS:
        repaired_vectors[key] = _normalize_weight_map(dict(vectors.get(key) or {}))

    repaired["vectors"] = repaired_vectors
    return repaired


def _generate_semantics(sampled_reviews: List[str]) -> Dict:
    prompt = _build_prompt(sampled_reviews)
    messages = [
        {
            "role": "system",
            "content": (
                "You generate structured game metadata and semantic vectors. "
                "Return one JSON object with exactly two top-level keys: "
                "metadata and vectors. metadata must contain micro_tags, "
                "signature_tag, appeal_axes, and genre_tree. vectors must contain "
                "mechanics, narrative, vibe, structure_loop, and uniqueness."
            ),
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]

    attempt = 0
    while attempt < MAX_SEMANTICS_RETRIES:
        attempt += 1
        print(f"Generating semantics attempt {attempt}")
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=messages,
            )
        except RateLimitError as exc:
            message = str(exc).lower()
            if "insufficient_quota" in message or "quota" in message or "credit" in message:
                raise CreditsExhaustedError("OpenAI API credits exhausted.") from exc
            raise

        content = response.choices[0].message.content or "{}"

        try:
            parsed = json.loads(content)
            semantics = GameSemantics.model_validate(_repair_semantics_payload(parsed))
            return semantics.model_dump()
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"\nRetrying invalid semantics response (attempt {attempt}): {exc}")
            if attempt >= MAX_SEMANTICS_RETRIES:
                raise RuntimeError(
                    f"Failed to generate valid semantics after {MAX_SEMANTICS_RETRIES} attempts."
                ) from exc
            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "That response was invalid. Return corrected JSON only. "
                        "Each of mechanics, narrative, vibe, structure_loop, and "
                        "uniqueness must be an object whose integer weights sum to 100 "
                        "independently."
                    ),
                }
            )
            time.sleep(RETRY_DELAY_SECONDS)

    raise RuntimeError(
        f"Failed to generate valid semantics after {MAX_SEMANTICS_RETRIES} attempts."
    )


def generate_game_semantics(review_samples: Dict) -> Dict:
    sampled_reviews = sample_reviews(review_samples)
    return _generate_semantics(sampled_reviews)
