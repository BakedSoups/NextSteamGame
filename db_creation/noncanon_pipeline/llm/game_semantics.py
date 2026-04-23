import json
import os
from math import floor
import time
from typing import Any, Dict, List

from openai import OpenAI
from openai import RateLimitError
from pydantic import BaseModel, field_validator, model_validator

from .errors import CreditsExhaustedError
from ..progress import log_stage
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


def _normalize_label(text: str) -> str:
    return " ".join(str(text).strip().lower().replace("_", " ").replace("-", " ").split())


class GenreTree(BaseModel):
    primary: str
    sub: str
    sub_sub: str

    @field_validator("primary", "sub", "sub_sub", mode="before")
    def validate_branch_value(cls, value: Any) -> str:
        if isinstance(value, list):
            for item in value:
                cleaned = " ".join(str(item).strip().split())
                if cleaned:
                    return cleaned
            return ""
        return " ".join(str(value or "").strip().split())

    @model_validator(mode="after")
    def ensure_non_empty_branches(self) -> "GenreTree":
        for branch_name in ("primary", "sub", "sub_sub"):
            if not getattr(self, branch_name):
                raise ValueError(f"{branch_name} must not be empty")
        return self


class GameMetadata(BaseModel):
    micro_tags: List[str]
    signature_tag: str
    niche_anchors: List[str]
    identity_tags: List[str]
    music_primary: str
    music_secondary: str
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

    @field_validator("niche_anchors")
    def validate_niche_anchors(cls, value: List[str]) -> List[str]:
        cleaned = []
        seen = set()
        for item in value:
            tag = " ".join(str(item).strip().split())
            if not tag:
                continue
            lowered = tag.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            cleaned.append(tag[:80])
        return cleaned[:8]

    @field_validator("identity_tags")
    def validate_identity_tags(cls, value: List[str]) -> List[str]:
        cleaned = []
        seen = set()
        for item in value:
            tag = " ".join(str(item).strip().split())
            if not tag:
                continue
            lowered = tag.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            cleaned.append(tag[:60])
        return cleaned[:12]

    @field_validator("music_primary", "music_secondary")
    def validate_music_identity_field(cls, value: str) -> str:
        return " ".join(str(value or "").strip().split())[:60]

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

    @model_validator(mode="after")
    def dedupe_metadata_fields(self) -> "GameMetadata":
        blocked = {_normalize_label(self.signature_tag)}
        blocked.add(_normalize_label(self.genre_tree.primary))
        blocked.add(_normalize_label(self.genre_tree.sub))
        blocked.add(_normalize_label(self.genre_tree.sub_sub))
        if self.music_primary:
            blocked.add(_normalize_label(self.music_primary))
        if self.music_secondary:
            blocked.add(_normalize_label(self.music_secondary))

        cleaned_anchors = []
        seen_anchors = set()
        for tag in self.niche_anchors:
            normalized = _normalize_label(tag)
            if not normalized or normalized in blocked or normalized in seen_anchors:
                continue
            seen_anchors.add(normalized)
            cleaned_anchors.append(tag)
        self.niche_anchors = cleaned_anchors[:8]

        blocked.update(seen_anchors)

        cleaned_identity_tags = []
        seen_identity_tags = set()
        for tag in self.identity_tags:
            normalized = _normalize_label(tag)
            if not normalized or normalized in blocked or normalized in seen_identity_tags:
                continue
            seen_identity_tags.add(normalized)
            cleaned_identity_tags.append(tag)
        self.identity_tags = cleaned_identity_tags[:12]

        blocked.update(seen_identity_tags)

        cleaned_micro_tags = []
        seen_micro_tags = set()
        for tag in self.micro_tags:
            normalized = _normalize_label(tag)
            if not normalized or normalized in blocked or normalized in seen_micro_tags:
                continue
            seen_micro_tags.add(normalized)
            cleaned_micro_tags.append(tag)
        self.micro_tags = cleaned_micro_tags[:15]
        return self


class GameVectors(BaseModel):
    mechanics: Dict[str, int]
    narrative: Dict[str, int]
    vibe: Dict[str, int]
    structure_loop: Dict[str, int]

    @field_validator("*")
    def validate_sum(cls, value: Dict[str, int]) -> Dict[str, int]:
        total = sum(value.values())
        if total != 100:
            raise ValueError(f"Vector must sum to 100, got {total}")
        return value


class GameSemantics(BaseModel):
    metadata: GameMetadata
    vectors: GameVectors


VECTOR_KEYS = ("mechanics", "narrative", "vibe", "structure_loop")
RETRY_DELAY_SECONDS = 2.0
MAX_SEMANTICS_RETRIES = 6


def _build_prompt(reviews: List[str]) -> str:
    joined = "\n\n---\n\n".join(review[:600] for review in reviews)

    return f"""
Generate structured game semantics for a video game from player reviews.

RULES:
- micro_tags and identity_tags should usually be 1-2 words
- be specific, not generic
- avoid duplicates and close synonyms
- prefer concrete system, setting, presentation, or music language over praise words
- extract what players actually value, not what sounds respectable in a taxonomy
- some sampled reviews may be weak, repetitive, jokey, nostalgic, or off-target; do not treat every review as equally reliable
- prefer repeated concrete evidence over one vivid but low-signal review
- micro_tags must contain at most 15 entries
- micro_tags should add extra searchable detail and should not repeat genre_tree labels, signature_tag, music identity, niche_anchors, or identity_tags
- signature_tag must be a short 2-4 word phrase describing the game's defining hook
- niche_anchors must contain 3-8 combined identity phrases
- identity_tags must contain reusable niche identity descriptors
- music_primary must be one dominant music identity
- music_secondary must be one optional supporting music identity
- appeal_axes must include exactly these integer 0-100 keys:
  challenge, complexity, pace, narrative_focus, social_energy, creativity
- prefer self-explanatory tags over franchise-specific jargon when possible
- genre_tree must stay flat
- primary, sub, and sub_sub must each be exactly one string, not a list
- genre_tree should optimize for recommendation usefulness, not store-taxonomy broadness
- vector weights must be integers
- EACH vector object sums to EXACTLY 100 on its own
- do NOT make the four top-level vector categories sum to 100 together
- every vector category should usually contain 3-6 tags, not one placeholder tag
- when reviews reveal a deeper mastery layer, prefer that over the most obvious surface-level comparison
- explicitly look for what separates this game from nearby games in the same broad lane
- if reviews repeatedly point to a hidden differentiator, surface it in signature_tag, niche_anchors, identity_tags, mechanics, or structure_loop
- avoid generic filler such as "fun gameplay", "great story", "immersive atmosphere", "timeless classic", "unique gameplay", "memorable experience", "rewarding challenge" unless the reviews give unusually concrete evidence for them
- if a field is weakly supported, use fewer stronger tags rather than padding it with vague ones
- sparse but correct is better than complete but invented
- do not infer specific features unless the reviews clearly support them
- emotional praise alone is not enough to claim specific narrative structure or character writing
- do not confuse the game's setting, marketing surface, or franchise reputation with the actual reason players keep recommending it
- treat "why fans stay with this game after first impressions" as more important than "what the store page suggests"
- keep concrete criticism when it identifies a real property of the game; negative evidence like "ugly graphics", "dated visuals", or "weak soundtrack" is still useful evidence about the game's identity

OUTPUT JSON:
These example values are only here to show the intended level of specificity and structure.
They are generic examples, not target labels to copy.
Derive the actual output from the reviews, even if the right tags look very different from these examples.
{{
  "metadata": {{
    "micro_tags": [tags],
    "signature_tag": "co-op survival",
    "niche_anchors": ["harsh wilderness survival", "co-op base building"],
    "identity_tags": ["frozen wilderness", "co-op crafting", "weather pressure"],
    "music_primary": "ambient",
    "music_secondary": "orchestral",
    "appeal_axes": {{
      "challenge": 55,
      "complexity": 40,
      "pace": 65,
      "narrative_focus": 20,
      "social_energy": 10,
      "creativity": 85
    }},
    "genre_tree": {{
      "primary": "broad genre",
      "sub": "recognized subgenre",
      "sub_sub": "more specific playstyle lane"
    }}
  }},
  "vectors": {{
    "mechanics": {{"squad tactics": 40, "stealth routing": 35, "factory automation": 25}},
    "narrative": {{"political intrigue": 40, "coming of age": 35, "moral ambiguity": 25}},
    "vibe": {{"melancholic": 40, "bleak": 35, "dreamlike": 25}},
    "structure_loop": {{"mission based": 40, "daily cycle": 35, "zone extraction": 25}}
  }}
}}

metadata.micro_tags:
- short, searchable descriptors

metadata.signature_tag:
- exactly one concise hook
- 2-4 words when possible
- should capture the game's defining identity, not just restate a broad genre
- should reflect the strongest actual reason players value the game, especially if it differs from the obvious surface pitch
- examples: "team shooter", "factory builder", "co-op survival", "kart racer"

metadata.niche_anchors:
- 3-8 compound identity phrases
- each phrase can be 2-5 words when needed
- should combine multiple aspects when useful
- should capture the compound hooks that make this game distinct from nearby lookalikes
- examples: "harsh wilderness survival", "co-op base building", "tactical extraction sandbox"

metadata.identity_tags:
- reusable niche identity descriptors
- these are not part of the genre spine
- prefer concrete identity details like setting, presentation, system flavor, or special hooks
- critical but concrete descriptors are allowed if they are well-supported
- examples: "frozen wilderness", "heavy machinery", "stylized ui", "urban fantasy"

metadata.appeal_axes:
- challenge = how demanding or punishing it feels
- complexity = how mentally/systemically dense it feels
- pace = how fast and energetic moment-to-moment play feels
- narrative_focus = how strongly the game centers story/characters
- social_energy = how much the experience depends on other players or social dynamics
- creativity = how much expression, experimentation, or player-made problem solving it invites
- use integer values from 0 to 100

metadata.music_primary / metadata.music_secondary:
- short music genre/style descriptors
- prefer concrete labels like "jazz fusion", "bossa nova", "orchestral", "metal"
- avoid vague mood words like "good music" or "emotional"
- avoid evaluative labels like "bland", "boring", "forgettable", "amazing", or "generic"
- describe what the music is like, not whether the reviewer liked it
- if reviews imply elevator music, lounge music, cafe jazz, or similar, prefer that concrete style over a vague label like "ambient"
- music_primary should be the strongest identity
- music_secondary is optional support

When wording tags:
- prefer descriptive phrases that still make sense outside franchise knowledge
- example: "monster fusion" is usually better than a franchise-specific label unless the proper noun is essential
- do not overfit to one famous game pattern just because a niche phrase sounds distinctive
- if reviews imply "this is not just X, because of Y", capture Y
- if a game has a deeper secondary identity beneath a broad surface label, capture the deeper identity
- prefer labels that would help distinguish this game from superficial neighbors in search and recommendation

metadata.genre_tree:
- primary = the most useful player-facing genre family, not the broadest market umbrella
- sub = the structural subtype, progression model, or major gameplay format inside that family
- sub_sub = the most specific practical play lane inside that subtype
- each level must add new information instead of restating the parent more vaguely
- prefer labels that help distinguish the game from nearby lookalikes
- derive the genre path from how the game is actually played, not just how it is marketed
- avoid vague ladders like "RPG -> JRPG -> dungeon crawler" when a more discriminative path is available
- examples of strong genre paths:
  - "JRPG -> calendar-driven RPG -> social dungeon crawler"
  - "Soulslike -> build-driven action RPG -> stamina-based melee dodge combat"
  - "Factory Builder -> automation sandbox -> conveyor logistics sim"
- examples of weak genre paths:
  - "RPG -> JRPG -> dungeon crawler"
  - "Adventure -> Exploration -> story game"
  - "Action -> Action Adventure -> combat game"
- each branch must be exactly one string

vectors:
- mechanics = gameplay systems
- narrative = themes and subject matter
- vibe = emotional tone or feel
- structure_loop = how gameplay flows over time

Evidence discipline:
- do not output "character development" unless reviews clearly discuss characters changing, growing, or being written in depth
- do not output "narrative choices" unless reviews clearly discuss meaningful player choice or branching outcomes
- do not output "social simulation" unless reviews clearly discuss relationship management, daily-life scheduling, or social-stat style systems
- do not output "exploration" as a mechanics tag unless the reviews describe exploration as something the player actively does, not just scenery they admire
- do not turn atmosphere alone into fake mechanics or fake narrative structure
- when a game is mostly about mood or audiovisual immersion, keep narrative/mechanics tags narrower rather than inventing extra systems

General anti-inference examples:
- these are examples of the kind of mistake to avoid, not labels you must use
- the reviews are the source of truth; if the reviews support something different, follow the reviews
- a meditative exploration game with emotional praise is not automatically "character development"
- a symbolic or wordless story is not automatically "narrative choices"
- a visually impressive game is not automatically "artistic design" unless the reviews actually discuss the presentation as a defining identity
- a beloved old game is not automatically "nostalgic" unless players repeatedly frame the appeal through memory, legacy, or time-capsule language

Before writing the JSON, reason from the reviews about:
1. what this game looks like on the surface
2. what committed players actually praise repeatedly
3. what differentiates it from superficially similar games
4. which tags would best preserve that distinction in a recommendation system

Then output only the JSON.

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
    metadata = dict(repaired.get("metadata") or {})
    genre_tree = dict(metadata.get("genre_tree") or {})

    def _first_text(value: Any) -> str:
        if isinstance(value, list):
            for item in value:
                cleaned = " ".join(str(item).strip().split())
                if cleaned:
                    return cleaned
            return ""
        return " ".join(str(value or "").strip().split())

    soundtrack_tags = metadata.get("soundtrack_tags") or []
    if not metadata.get("music_primary") and soundtrack_tags:
        metadata["music_primary"] = _first_text(soundtrack_tags[:1])
    if not metadata.get("music_secondary") and len(soundtrack_tags) > 1:
        metadata["music_secondary"] = _first_text(soundtrack_tags[1:2])

    metadata["niche_anchors"] = list(metadata.get("niche_anchors") or [])
    metadata["identity_tags"] = list(metadata.get("identity_tags") or [])
    metadata["micro_tags"] = list(metadata.get("micro_tags") or [])
    metadata["music_primary"] = _first_text(metadata.get("music_primary"))
    metadata["music_secondary"] = _first_text(metadata.get("music_secondary"))
    metadata["genre_tree"] = {
        "primary": _first_text(genre_tree.get("primary")),
        "sub": _first_text(genre_tree.get("sub")),
        "sub_sub": _first_text(genre_tree.get("sub_sub")),
    }
    repaired["metadata"] = metadata
    return repaired


def _generate_semantics(sampled_reviews: List[str], appid: str | int | None = None) -> Dict:
    prompt = _build_prompt(sampled_reviews)
    messages = [
        {
            "role": "system",
            "content": (
                "You generate structured game metadata and semantic vectors. "
                "Return one JSON object with exactly two top-level keys: "
                "metadata and vectors. metadata must contain micro_tags, "
                "signature_tag, niche_anchors, identity_tags, music_primary, music_secondary, appeal_axes, and genre_tree. "
                "vectors must contain mechanics, narrative, vibe, and structure_loop."
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
            log_stage("semantics", appid=appid, detail=f"retrying semantics ({attempt}/{MAX_SEMANTICS_RETRIES})")
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
                        "Each of mechanics, narrative, vibe, and structure_loop must be an object "
                        "whose integer weights sum to 100 independently. genre_tree.primary, "
                        "genre_tree.sub, and genre_tree.sub_sub must each be one string."
                    ),
                }
            )
            time.sleep(RETRY_DELAY_SECONDS)

    raise RuntimeError(
        f"Failed to generate valid semantics after {MAX_SEMANTICS_RETRIES} attempts."
    )


def generate_game_semantics(review_samples: Dict, appid: str | int | None = None) -> Dict:
    sampled_reviews = sample_reviews(review_samples)
    return _generate_semantics(sampled_reviews, appid=appid)
