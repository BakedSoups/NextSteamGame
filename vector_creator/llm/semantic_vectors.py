import json
import os
from typing import Dict, List

from openai import OpenAI
from openai import RateLimitError
from pydantic import BaseModel, field_validator

from .errors import CreditsExhaustedError
from .review_sampling import sample_reviews


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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


def _build_prompt(reviews: List[str]) -> str:
    joined = "\n\n---\n\n".join(review[:600] for review in reviews)

    return f"""
Generate semantic vectors for a video game.

RULES:
- tags must be 1-2 words only
- tags must be specific (NOT generic like "fun", "good")
- avoid duplicates and synonyms
- weights must be integers
- each vector must sum to EXACTLY 100

VECTORS:

mechanics -> gameplay systems (what player does)
narrative -> themes, story, subject matter
vibe -> emotional tone or feel
structure_loop -> how gameplay flows over time
uniqueness -> what makes the game distinct

OUTPUT:
Return valid JSON matching the schema exactly.

REVIEWS:
{joined}
"""


def _generate_vectors(sampled_reviews: List[str]) -> Dict:
    prompt = _build_prompt(sampled_reviews)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate structured semantic representations for games. "
                        "Return a JSON object with exactly these top-level keys: "
                        "mechanics, narrative, vibe, structure_loop, uniqueness. "
                        "Each value must be an object mapping short tags to integer weights summing to 100."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )
    except RateLimitError as exc:
        message = str(exc).lower()
        if "insufficient_quota" in message or "quota" in message or "credit" in message:
            raise CreditsExhaustedError("OpenAI API credits exhausted.") from exc
        raise

    content = response.choices[0].message.content or "{}"

    try:
        parsed = json.loads(content)
        vectors = GameVectors.model_validate(parsed)
    except Exception:
        print("\nFAILED TO PARSE OR VALIDATE RESPONSE:\n")
        print(content)
        raise

    return vectors.model_dump()


def generate_game_vectors(review_samples: Dict) -> Dict:
    sampled_reviews = sample_reviews(review_samples)
    return _generate_vectors(sampled_reviews)


embedsteam_review = generate_game_vectors
