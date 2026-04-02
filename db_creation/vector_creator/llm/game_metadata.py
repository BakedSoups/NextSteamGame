import json
import os
from typing import Dict, List

from openai import OpenAI
from pydantic import BaseModel, field_validator

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


def _build_prompt(reviews: List[str]) -> str:
    joined = "\n\n---\n\n".join(review[:600] for review in reviews)

    return f"""
Generate structured metadata for a video game.

RULES:
- tags must be 1-2 words
- specific, not generic
- no duplicates
- keep micro_tags to at most 15
- genre_tree must stay flat

OUTPUT JSON:
{{
  "micro_tags": [tags],
  "genre_tree": {{
    "primary": [broad genres],
    "sub": [recognized subgenres],
    "traits": [defining traits]
  }}
}}

micro_tags:
- short, searchable descriptors
- examples: "bar vibes", "fall panic", "choice guilt"

genre_tree:
- primary = broad categories like Action, RPG, Strategy
- sub = recognized subgenres like Soulslike, Roguelike, Metroidvania
- traits = defining structural or gameplay traits

REVIEWS:
{joined}
"""


def _generate_metadata(sampled_reviews: List[str]) -> Dict:
    prompt = _build_prompt(sampled_reviews)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate structured game metadata. "
                    "Return a JSON object with exactly these top-level keys: "
                    "micro_tags and genre_tree. "
                    "genre_tree must contain exactly primary, sub, and traits."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    content = response.choices[0].message.content or "{}"

    try:
        parsed = json.loads(content)
        metadata = GameMetadata.model_validate(parsed)
    except Exception:
        print("\nFAILED TO PARSE OR VALIDATE RESPONSE:\n")
        print(content)
        raise

    return metadata.model_dump()


def generate_game_metadata(review_samples: Dict) -> Dict:
    sampled_reviews = sample_reviews(review_samples)
    return _generate_metadata(sampled_reviews)
