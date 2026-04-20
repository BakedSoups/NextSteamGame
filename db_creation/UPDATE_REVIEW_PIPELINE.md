# Update Review Pipeline

This document is the working plan for the next semantic-data redesign in `db_creation`.

The goal is to make the non-canonical review pipeline better at:

- representing a game's actual focus
- finding hyper-niche identity
- keeping genre classification decisive
- separating vector-worthy dimensions from tag/identity dimensions

This plan is for the review/vector pipeline first.

The visual pipeline is intentionally deferred until after the new vector/tag schema is in place, so visual identity can be added onto the DB cleanly instead of being built against a schema that is about to change.

## Main Decisions

### Keep These As Vectors

These stay as weighted semantic vectors because they describe major focus areas of a game and can meaningfully contain multiple weighted sub-signals:

- `mechanics`
- `narrative`
- `vibe`
- `structure_loop`

Reasoning:

- `mechanics` describes how the game plays
- `narrative` describes what story/themes/character focus the game emphasizes
- `vibe` describes emotional and tonal blend
- `structure_loop` describes cadence over time: daily cycle, mission rhythm, run structure, progression shape

### Remove These From Vectors

These should not be modeled as full vectors:

- `music`
- `uniqueness`

Reasoning:

- `music` is usually a named identity, not a weighted semantic branch
- `uniqueness` usually behaves more like a standout hook or niche descriptor than a tunable focus axis

## New Shape

### 1. Hard Genre Spine

Genre should become decisive:

- `primary`: one tag
- `sub`: one tag
- `sub_sub`: one tag

Reasoning:

- the model should commit to one dominant genre lane
- the genre tree should answer the broad "what kind of game is this?" question
- hyper-specific narrowing should happen through micro-tags and identity metadata, not a parallel `traits` layer

### 2. Focus Vectors

The semantic vectors become:

- `mechanics`
- `narrative`
- `vibe`
- `structure_loop`

These are the "focus of the game" dimensions.

### 3. Tag / Identity Layers

The following should be stored as identity metadata rather than vectors:

- `signature_tag`
- `niche_anchors`
- `music_identity`
- `identity_tags`
- `micro_tags`

Suggested shapes:

- `signature_tag`: one concise defining hook
- `niche_anchors`: 3-8 very specific combined identity phrases
- `music_identity`: dominant music style information
- `identity_tags`: reusable niche identity descriptors such as setting, lifestyle, presentation, or hook flavor
- `micro_tags`: hyper-specific narrowing descriptors

`micro_tags` absorb the role that `traits` would have played for fine-grained similarity and filtering.

For the first schema pass, keep identity metadata intentionally compressed.

Do not split into separate `setting_tags`, `lifestyle_tags`, and `presentation_tags` yet.
Those can be introduced later only if retrieval and UI prove they are needed as distinct fields.

## Music Identity

Music should move out of vectors and into structured metadata.

Target shape:

- `music_primary`
- `music_secondary`

Examples:

- `jazz fusion`
- `acid jazz`

This is a better match for how users think about music than a weighted music vector.

`music_identity` should stay narrower than the general identity fields.
It should only contain music labels, never cross-domain combined hooks.

## Uniqueness / Hook Identity

`uniqueness` should be replaced with sharper hook-style metadata.

Target shape:

- `signature_tag`
- `niche_anchors`

Examples:

- `modern city social sim`
- `after school dungeon loop`
- `jazz fusion soundtrack`
- `time loop mystery`

This captures what makes a game feel singular without forcing that information into an artificial vector.

Do not add `hook_tags` in the first pass.
`signature_tag` plus `niche_anchors` is enough.

## Hyper-Niche Capture

The current worry is that the pipeline is good at broad shape but weak at compound identity.

Examples of niche signals we want to preserve:

- city setting
- student life
- after-school routine
- jazz fusion
- stylish UI
- urban fantasy

To improve this, the review pipeline needs:

1. better protected output fields for niche identity
2. less flattening during canonicalization
3. retrieval text that preserves niche anchors clearly

## Schema Contract

The target schema should follow these boundaries strictly.

### Genre Spine

- `primary`: exactly one broad genre
- `sub`: exactly one subgenre
- `sub_sub`: exactly one narrow genre lane

### Focus Vectors

- `mechanics`: weighted gameplay systems
- `narrative`: weighted story/theme emphasis
- `vibe`: weighted tone/mood emphasis
- `structure_loop`: weighted cadence/progression/loop emphasis

### Identity Metadata

- `signature_tag`: exactly one concise defining hook, ideally 2-4 words
- `niche_anchors`: 3-8 compound identities, combining multiple aspects when needed
- `identity_tags`: reusable niche descriptors that are not part of the genre spine
- `music_primary`: one dominant music identity
- `music_secondary`: one optional supporting music identity
- `micro_tags`: atomic hyper-specific descriptors for narrowing/filtering

## Deduplication Rules

The extractor should not repeat the same idea across fields.

- `signature_tag` must not be duplicated in `niche_anchors`
- `music_primary` and `music_secondary` must not appear in `micro_tags`
- `identity_tags` should not duplicate the genre spine
- `micro_tags` should stay atomic and should not repeat `signature_tag` or `niche_anchors`
- `niche_anchors` should prefer compound phrases over atomic descriptors

## Planned Pipeline Changes

### Phase 1: Review / Semantics Schema Update

Update `noncanon_pipeline` and the LLM semantics schema to:

- remove `music` vector
- remove `uniqueness` vector
- keep `mechanics`, `narrative`, `vibe`, `structure_loop`
- make `genre_tree.primary` a single value
- make `genre_tree.sub` a single value
- make `genre_tree.sub_sub` a single value
- remove `genre_tree.traits`
- add niche metadata fields

### Phase 2: Final / Canon Pipeline Alignment

Update downstream stages so they understand the new schema:

- `canon_pipeline`
- `final_pipeline`
- Postgres load stage
- Chroma migration / retrieval document builders
- backend recommender score model
- frontend types / transparent score UI
- retrieval text builders

Key rule:

- canonicalization should stay conservative for niche metadata
- do not over-merge niche anchors into generic labels
- explicitly remove `uniqueness` from the transparent vector breakdown
- explicitly remove vector-based `music` handling and replace it with music identity handling

### Phase 3: Retrieval Update

Update retrieval document construction so it uses:

- genre spine
- focus vectors
- signature tag
- niche anchors
- music identity
- identity tags
- micro-tags

This should improve recall and precision for compound tastes.

## Traits Decision

`traits` are removed from the target schema.

Reasoning:

- they overlap too much with both the genre spine and micro-tags
- they create an unnecessary middle layer between broad similarity and niche identity
- the genre tree is enough for broad structural similarity
- micro-tags are enough for hyper-specific narrowing

New rule:

- use `primary`, `sub`, `sub_sub` for broad similarity
- use `micro_tags` and other identity metadata for specificity

## Visual Pipeline Status

The visual pipeline is not part of the immediate schema rewrite.

Decision:

- do not integrate visual identity into the DB at the same time as this vector/tag redesign
- finish the review/vector schema first
- then add visual identity as a follow-up feature on top of the new DB shape

Reasoning:

- otherwise two schema changes will overlap
- the visual stage should target the final semantic structure, not a temporary one

Planned later visual fields:

- `render_family`
- `render_style_primary`
- `render_style_secondary`
- `presentation_style`
- `visual_traits`

That should be added later as a DB extension step after the new review/vector schema is stable.

## Order Of Work

1. Rewrite the review semantics schema
2. Lock the vector vs tag split
3. Make genre spine single-value at each major level
4. Update final/canon/postgres/Chroma/backend/frontend schema consumers to match
5. Rebuild semantic DB outputs
6. Add visual pipeline into the DB after the schema is stable

## Non-Goals Right Now

- visual DB integration in the same pass
- UI refactor for the new schema in the same pass
- replacing retrieval model infrastructure before the semantic schema is corrected

## Migration Impact

The following parts of the codebase must be treated as schema consumers during implementation:

- `db_creation/noncanon_pipeline`
- `db_creation/canon_pipeline`
- `db_creation/final_pipeline`
- `db_creation/postgres`
- `db_creation/chroma_pipeline`
- `backend/recommender.py`
- `backend/retrieval.py`
- frontend type definitions and any UI that exposes transparent score structure
