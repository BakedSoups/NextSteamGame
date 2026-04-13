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


class GenreTree(BaseModel):
    primary: List[str]
    sub: List[str]
    traits: List[str]


class GameMetadata(BaseModel):
    micro_tags: List[str]
    genre_tree: GenreTree

    @field_validator("micro_tags")
    def validate_micro_tags(cls, value: List[str]) -> List[str]:
        return list(dict.fromkeys(value))[:15]


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


def _build_prompt(reviews: List[str]) -> str:
    joined = "\n\n---\n\n".join(review[:600] for review in reviews)

    return f"""
Generate structured game semantics for a video game from player reviews.

RULES:
- tags must be 1-2 words
- be specific, not generic
- avoid duplicates and close synonyms
- micro_tags must contain at most 15 entries
- genre_tree must stay flat
- vector weights must be integers
- EACH vector object sums to EXACTLY 100 on its own
- do NOT make the five top-level vector categories sum to 100 together
- every vector category should usually contain 3-6 tags, not one placeholder tag

OUTPUT JSON:
{{
  "metadata": {{
    "micro_tags": [tags],
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
                "metadata and vectors. metadata must contain micro_tags and "
                "genre_tree. vectors must contain mechanics, narrative, vibe, "
                "structure_loop, and uniqueness."
            ),
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]

    attempt = 0
    while True:
        attempt += 1
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


def generate_game_semantics(review_samples: Dict) -> Dict:
    sampled_reviews = sample_reviews(review_samples)
    return _generate_semantics(sampled_reviews)
