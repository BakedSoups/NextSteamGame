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

GENERIC_HEADS = {
    "action",
    "adventure",
    "aesthetic",
    "atmosphere",
    "challenge",
    "design",
    "experience",
    "feature",
    "game",
    "gameplay",
    "graphic",
    "interface",
    "level",
    "limit",
    "mechanic",
    "mode",
    "music",
    "nostalgia",
    "pacing",
    "platformer",
    "puzzle",
    "racing",
    "rpg",
    "setting",
    "simulation",
    "story",
    "strategy",
    "style",
    "system",
    "theme",
    "turn",
    "visual",
    "weapon",
}

VAGUE_LEADERS = {
    "arbitrary",
    "authentic",
    "captivating",
    "engaging",
    "fun",
    "good",
    "great",
    "immersive",
    "interesting",
    "nice",
    "random",
    "unique",
    "varied",
    "various",
}

STOPLIKE = {"a", "an", "and", "co", "op", "for", "in", "of", "on", "the", "to", "with"}

KNOWN_SHORT_OK = {
    "2d",
    "3d",
    "4x",
    "4k",
    "8bit",
    "16bit",
    "18xx",
    "ai",
    "hp",
    "ui",
    "vr",
    "pvp",
    "pve",
    "rts",
    "fps",
    "mmo",
    "jrpg",
    "rpg",
}

SUSPICIOUS_FRAGMENT_ENDINGS = (
    "driv",
    "generat",
    "licen",
    "matche",
    "narrat",
    "profil",
    "sett",
    "spott",
    "styliz",
)


def _normalize_label(text: str) -> str:
    return " ".join(str(text).strip().lower().replace("_", " ").replace("-", " ").split())


def _tokens(text: str) -> List[str]:
    return [token for token in _normalize_label(text).split() if token]


def _is_numberish(token: str) -> bool:
    compact = token.replace("s", "").replace("x", "")
    return compact.isdigit()


def _looks_like_fragment(token: str) -> bool:
    if token in KNOWN_SHORT_OK:
        return False
    return any(token.endswith(ending) for ending in SUSPICIOUS_FRAGMENT_ENDINGS)


def _informative_tokens(tag: str) -> List[str]:
    return [
        token
        for token in _tokens(tag)
        if token not in STOPLIKE and not _is_numberish(token)
    ]


def _is_low_quality_tag(tag: str, field_name: str) -> bool:
    tokens = _tokens(tag)
    if not tokens or len(tokens) > 5:
        return True
    if any(_looks_like_fragment(token) for token in tokens):
        return True
    if tokens[0] in VAGUE_LEADERS:
        return True

    informative = _informative_tokens(tag)
    if not informative:
        return True

    if field_name in {"micro_tags", "identity_tags", "setting_tags"}:
        if len(tokens) < 2 or len(tokens) > 4:
            return True
        if informative[-1] in GENERIC_HEADS and len(informative) < 2:
            return True
        if not any(len(token) >= 4 or token in KNOWN_SHORT_OK for token in informative):
            return True

    if field_name == "niche_anchors" and len(tokens) < 2:
        return True

    return False


def _clean_tag_list(tags: List[str], *, field_name: str, max_items: int) -> List[str]:
    cleaned: List[str] = []
    seen = set()
    max_len = 80 if field_name == "niche_anchors" else 60
    for raw_tag in tags:
        tag = " ".join(str(raw_tag).strip().split())
        if not tag:
            continue
        normalized = _normalize_label(tag)
        if normalized in seen or _is_low_quality_tag(tag, field_name):
            continue
        seen.add(normalized)
        cleaned.append(tag[:max_len])
    return cleaned[:max_items]


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
    setting_tags: List[str]
    music_primary: str
    music_secondary: str
    appeal_axes: Dict[str, int]
    genre_tree: GenreTree

    @field_validator("micro_tags")
    def validate_micro_tags(cls, value: List[str]) -> List[str]:
        return _clean_tag_list(list(value), field_name="micro_tags", max_items=10)

    @field_validator("signature_tag")
    def validate_signature_tag(cls, value: str) -> str:
        cleaned = " ".join(str(value).strip().split())
        if not cleaned:
            raise ValueError("signature_tag must not be empty")
        return cleaned[:80]

    @field_validator("niche_anchors")
    def validate_niche_anchors(cls, value: List[str]) -> List[str]:
        return _clean_tag_list(list(value), field_name="niche_anchors", max_items=6)

    @field_validator("identity_tags")
    def validate_identity_tags(cls, value: List[str]) -> List[str]:
        return _clean_tag_list(list(value), field_name="identity_tags", max_items=8)

    @field_validator("setting_tags")
    def validate_setting_tags(cls, value: List[str]) -> List[str]:
        return _clean_tag_list(list(value), field_name="setting_tags", max_items=3)

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
            if (
                not normalized
                or normalized in blocked
                or normalized in seen_anchors
                or _is_low_quality_tag(tag, "niche_anchors")
            ):
                continue
            seen_anchors.add(normalized)
            cleaned_anchors.append(tag)
        self.niche_anchors = cleaned_anchors[:6]

        blocked.update(seen_anchors)

        cleaned_identity_tags = []
        seen_identity_tags = set()
        for tag in self.identity_tags:
            normalized = _normalize_label(tag)
            if (
                not normalized
                or normalized in blocked
                or normalized in seen_identity_tags
                or _is_low_quality_tag(tag, "identity_tags")
            ):
                continue
            seen_identity_tags.add(normalized)
            cleaned_identity_tags.append(tag)
        self.identity_tags = cleaned_identity_tags[:8]

        blocked.update(seen_identity_tags)

        cleaned_setting_tags = []
        seen_setting_tags = set()
        for tag in self.setting_tags:
            normalized = _normalize_label(tag)
            if (
                not normalized
                or normalized in blocked
                or normalized in seen_setting_tags
                or _is_low_quality_tag(tag, "setting_tags")
            ):
                continue
            seen_setting_tags.add(normalized)
            cleaned_setting_tags.append(tag)
        self.setting_tags = cleaned_setting_tags[:3]

        blocked.update(seen_setting_tags)

        cleaned_micro_tags = []
        seen_micro_tags = set()
        for tag in self.micro_tags:
            normalized = _normalize_label(tag)
            if (
                not normalized
                or normalized in blocked
                or normalized in seen_micro_tags
                or _is_low_quality_tag(tag, "micro_tags")
            ):
                continue
            seen_micro_tags.add(normalized)
            cleaned_micro_tags.append(tag)
        self.micro_tags = cleaned_micro_tags[:10]
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


class EvidenceSignals(BaseModel):
    repeated_systems: List[str]
    repeated_differentiators: List[str]
    repeated_complaints: List[str]
    hidden_depth: List[str]
    music_signals: List[str]

    @field_validator("*")
    def validate_lists(cls, value: List[str]) -> List[str]:
        cleaned: List[str] = []
        seen = set()
        for item in value or []:
            text = " ".join(str(item).strip().split())
            if not text:
                continue
            normalized = _normalize_label(text)
            if normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append(text[:80])
        return cleaned[:6]


VECTOR_KEYS = ("mechanics", "narrative", "vibe", "structure_loop")
RETRY_DELAY_SECONDS = 2.0
MAX_SEMANTICS_RETRIES = 6
MAX_EVIDENCE_RETRIES = 4


def _build_evidence_prompt(reviews: List[str]) -> str:
    joined = "\n\n---\n\n".join(review[:600] for review in reviews)
    return f"""
Extract concrete recommendation evidence from player reviews.

RULES:
- focus on repeated, concrete, recommendation-useful evidence
- preserve non-obvious differentiators when they appear
- include deeper system depth if reviews mention mastery, optimization, routing, buildcraft, automation, logistics, scheduling, combo depth, strategy layers, or unusual progression
- include concrete complaints when they identify a real part of the game
- do not output vague praise like "fun gameplay" or "great story"
- use short phrases, not sentences
- omit anything weakly supported

OUTPUT JSON:
{{
  "repeated_systems": ["..."],
  "repeated_differentiators": ["..."],
  "repeated_complaints": ["..."],
  "hidden_depth": ["..."],
  "music_signals": ["..."]
}}

REVIEWS:
{joined}
"""


def _build_evidence_block(evidence: Dict) -> str:
    lines = ["EVIDENCE SIGNALS:"]
    for key in (
        "repeated_systems",
        "repeated_differentiators",
        "repeated_complaints",
        "hidden_depth",
        "music_signals",
    ):
        values = list(evidence.get(key) or [])
        label = key.replace("_", " ")
        if values:
            lines.append(f"- {label}: " + "; ".join(values))
        else:
            lines.append(f"- {label}: none")
    return "\n".join(lines)


def _flatten_evidence_terms(evidence: Dict) -> set[str]:
    terms: set[str] = set()
    for key in (
        "repeated_systems",
        "repeated_differentiators",
        "repeated_complaints",
        "hidden_depth",
    ):
        for item in evidence.get(key) or []:
            normalized = _normalize_label(item)
            if normalized:
                terms.add(normalized)
    return terms


def _metadata_terms(metadata: Dict) -> set[str]:
    terms: set[str] = set()
    for field in ("signature_tag", "music_primary", "music_secondary"):
        value = _normalize_label(str(metadata.get(field, "")))
        if value:
            terms.add(value)
    for field in ("micro_tags", "niche_anchors", "identity_tags", "setting_tags"):
        for item in metadata.get(field, []) or []:
            normalized = _normalize_label(item)
            if normalized:
                terms.add(normalized)
    return terms


def _evidence_is_reflected(evidence: Dict, semantics: Dict) -> bool:
    evidence_terms = _flatten_evidence_terms(evidence)
    if not evidence_terms:
        return True
    metadata_terms = _metadata_terms(semantics.get("metadata", {}))
    if not metadata_terms:
        return False
    for evidence_term in evidence_terms:
        evidence_tokens = set(_tokens(evidence_term))
        if not evidence_tokens:
            continue
        for metadata_term in metadata_terms:
            metadata_tokens = set(_tokens(metadata_term))
            if evidence_tokens & metadata_tokens:
                return True
    return False


def _extract_evidence_signals(sampled_reviews: List[str], appid: str | int | None = None) -> Dict:
    prompt = _build_evidence_prompt(sampled_reviews)
    messages = [
        {
            "role": "system",
            "content": "You extract concrete evidence signals from player reviews. Return one JSON object only.",
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]

    attempt = 0
    while attempt < MAX_EVIDENCE_RETRIES:
        attempt += 1
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.1,
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
            evidence = EvidenceSignals.model_validate(parsed)
            return evidence.model_dump()
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            log_stage("evidence", appid=appid, detail=f"retrying evidence ({attempt}/{MAX_EVIDENCE_RETRIES})")
            if attempt >= MAX_EVIDENCE_RETRIES:
                raise RuntimeError(
                    f"Failed to generate valid evidence after {MAX_EVIDENCE_RETRIES} attempts."
                ) from exc
            messages.append({"role": "assistant", "content": content})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "That response was invalid. Return corrected JSON only with exactly these keys: "
                        "repeated_systems, repeated_differentiators, repeated_complaints, hidden_depth, music_signals."
                    ),
                }
            )
            time.sleep(RETRY_DELAY_SECONDS)


def _build_prompt(reviews: List[str], evidence: Dict) -> str:
    joined = "\n\n---\n\n".join(review[:600] for review in reviews)
    evidence_block = _build_evidence_block(evidence)

    return f"""
Generate structured game semantics for a video game from player reviews.

RULES:
- micro_tags, identity_tags, and setting_tags should usually be 2-4 words when needed for clarity
- be specific, not generic
- avoid duplicates and close synonyms
- prefer concrete system, setting, presentation, or music language over praise words
- do not output malformed shorthand, clipped words, or partial stems
- avoid vague adjective+noun sludge like "unique gameplay", "varied level", "great story", "immersive atmosphere", "arbitrary control"
- preserve anchor concepts like "AI", "8 bit", "co-op", "calendar", or "exorcism" when they are the meaningful part of the tag
- extract what players actually value, not what sounds respectable in a taxonomy
- some sampled reviews may be weak, repetitive, jokey, nostalgic, or off-target; do not treat every review as equally reliable
- prefer repeated concrete evidence over one vivid but low-signal review
- micro_tags must contain at most 10 entries
- micro_tags should add extra searchable detail and should not repeat genre_tree labels, signature_tag, music identity, niche_anchors, or identity_tags
- signature_tag must be a short 2-4 word phrase describing the game's defining hook
- niche_anchors must contain 3-6 combined identity phrases
- identity_tags must contain reusable niche identity descriptors and should not collapse into generic head words
- setting_tags must contain 1-3 concrete world/era/location setting descriptors when strongly supported
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
- if reviews repeatedly describe automation, routing, optimization, logistics, throughput, or setup planning, surface that explicitly instead of collapsing it into generic strategy language
- the strongest repeated evidence from the evidence block below must visibly survive into the final metadata and/or vectors
- avoid generic filler such as "fun gameplay", "great story", "immersive atmosphere", "timeless classic", "unique gameplay", "memorable experience", "rewarding challenge" unless the reviews give unusually concrete evidence for them
- if a field is weakly supported, use fewer stronger tags rather than padding it with vague ones
- sparse but correct is better than complete but invented
- do not infer specific features unless the reviews clearly support them
- if a tag would be vague, malformed, clipped, or weakly supported, omit it instead of padding the field
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
    "setting_tags": ["medieval fantasy", "frozen wilderness"],
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
- should still read like natural tag phrases, not clipped fragments
- prefer 2-4 word clarity over 1-word vagueness

metadata.signature_tag:
- exactly one concise hook
- 2-4 words when possible
- should capture the game's defining identity, not just restate a broad genre
- should reflect the strongest actual reason players value the game, especially if it differs from the obvious surface pitch
- examples: "team shooter", "factory builder", "co-op survival", "kart racer"

metadata.niche_anchors:
- 3-6 compound identity phrases
- each phrase can be 2-5 words when needed
- should combine multiple aspects when useful
- should capture the compound hooks that make this game distinct from nearby lookalikes
- examples: "harsh wilderness survival", "co-op base building", "tactical extraction sandbox"

metadata.identity_tags:
- reusable niche identity descriptors
- these are not part of the genre spine
- prefer concrete identity details like setting, presentation, system flavor, or special hooks
- critical but concrete descriptors are allowed if they are well-supported
- do not emit generic containers like "theme", "mechanic", "feature", "system", or "visual" unless the full phrase is concrete
- if players repeatedly praise automation or optimization, prefer concrete labels like "kitchen automation", "workflow routing", or "throughput planning" over broad tags like "strategy"
- examples: "frozen wilderness", "heavy machinery", "stylized ui", "urban fantasy"

metadata.setting_tags:
- 1-3 concrete setting descriptors
- focus on world context, era, environment, civilization style, or place
- prefer labels like "medieval fantasy", "modern city", "cyberpunk dystopia", "space station", "post-apocalyptic wasteland", "urban fantasy"
- do not use social-container labels like "high school setting", "party dynamics", or "workplace drama" unless the world itself is defined by that environment
- do not use mood words, mechanic words, or genre labels here
- if the setting is only weakly implied, omit it rather than guessing

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
- when a review highlights deeper optimization, automation, or routing mastery, preserve that layer in the output instead of only surface descriptors like "co-op chaos" or "time management"

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

{evidence_block}

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
    metadata["setting_tags"] = list(metadata.get("setting_tags") or [])
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
    evidence = _extract_evidence_signals(sampled_reviews, appid=appid)
    prompt = _build_prompt(sampled_reviews, evidence)
    messages = [
        {
            "role": "system",
            "content": (
                "You generate structured game metadata and semantic vectors. "
                "Return one JSON object with exactly two top-level keys: "
                "metadata and vectors. metadata must contain micro_tags, "
                "signature_tag, niche_anchors, identity_tags, setting_tags, music_primary, music_secondary, appeal_axes, and genre_tree. "
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
            dumped = semantics.model_dump()
            if not _evidence_is_reflected(evidence, dumped):
                raise ValueError("Final semantics did not preserve strong evidence signals.")
            dumped["evidence_signals"] = evidence
            return dumped
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
                        "genre_tree.sub, and genre_tree.sub_sub must each be one string. "
                        "Remove vague, malformed, clipped, or low-signal metadata tags instead of padding. "
                        "Make sure the strongest evidence signals are visibly reflected in the final metadata or vectors."
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
