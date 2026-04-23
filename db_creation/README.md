# `db_creation`

This folder contains the full data-building side of the project.

The core idea is:

- keep raw Steam/store metadata separate from semantic interpretation
- keep raw semantic interpretation separate from canonical cleanup
- keep retrieval/indexing separate from both

That separation is intentional. It lets you:

- rerun only the expensive stage you changed
- inspect intermediate artifacts instead of debugging the final DB blind
- preserve raw semantic evidence before canonical grouping flattens it
- evolve the ontology without rebuilding the whole world every time

## Stage Map

The main stage entrypoints are:

1. `metadata_db.py`
2. `initial_noncanon_db.py`
3. `canon_export.py`
4. `final_db.py`
5. `chroma_db_migration.py`
6. `postgres_db.py`
7. `visual_pipeline.py`

The important databases/artifacts are:

- `data/steam_metadata.db`
- `data/steam_initial_noncanon.db`
- `data/steam_final_canon.db`
- `data/chroma/`

Path handling is centralized in:

- `db_creation/paths.py`

## Why The Stages Are Split

This pipeline is not just ETL. It is an ontology-building workflow.

The stages exist because they solve different problems:

- metadata stage:
  - what factual/storefront information exists?
- non-canon stage:
  - what do players seem to mean about this game in their own language?
- canon stage:
  - which of those expressions should collapse into a shared vocabulary?
- final stage:
  - what cleaned, stable representation should downstream systems consume?
- retrieval stage:
  - what text/index form best supports candidate generation?

If you collapse all of that into one build step, you lose the ability to:

- audit model mistakes
- preserve source evidence
- fix grouping without re-calling the LLM
- distinguish “bad extraction” from “over-aggressive canonicalization”

## Pipeline Folders

- `metadata_pipeline`
  - Steam metadata ingestion and asset enrichment
- `noncanon_pipeline`
  - review fetch, review sampling, semantic extraction
- `canon_pipeline`
  - grouping and canonical representative generation
- `final_pipeline`
  - canonical DB build
- `chroma_pipeline`
  - retrieval document build + Chroma migration
- `visual_stage`
  - early visual-identity experiments
- `db_builders`
  - lower-level write/resume/orchestration logic used by stage wrappers

## Running The Main Stages

Metadata:

```bash
python db_creation/metadata_db.py
```

Non-canonical semantics:

```bash
python db_creation/initial_noncanon_db.py
```

Canon export:

```bash
python db_creation/canon_export.py
```

Final canonical DB:

```bash
python db_creation/final_db.py
```

Chroma migration:

```bash
python db_creation/chroma_db_migration.py
```

Postgres load:

```bash
python db_creation/postgres_db.py
```

Visual pipeline:

```bash
python db_creation/visual_pipeline.py
```

Single-game non-canon test:

```bash
python db_creation/noncanon_pipeline/test_single_game.py 1599600
```

## Non-Canonical Stage

This is the most important stage conceptually.

It is not “the final truth.”
It is the raw semantic interpretation layer.

The non-canon DB should preserve:

- what reviews were selected
- what the model inferred before grouping
- enough source detail that later cleanup can be audited

That is why each row stores:

- `review_samples_json`
- `vectors_json`
- `metadata_json`

and not just a final list of tags.

### What The Non-Canon Stage Is Trying To Solve

The main problem is not “find games in the same store genre.”
It is:

- capture what players actually value
- distinguish broad similarity from niche identity
- preserve hidden differentiators instead of only surface resemblance

Examples:

- `PlateUp!`
  - not just “co-op cooking chaos”
  - also automation, layout optimization, run-based scaling
- `Persona 5`
  - not just “JRPG”
  - also modern Tokyo, school routine, stylish UI, jazz fusion
- `Dark Souls`
  - not just dark fantasy
  - maybe build variety, stamina combat, orchestral intensity

That is why the non-canon stage is review-driven instead of relying only on Steam tags.

### Current Non-Canon Schema Direction

The semantic representation is being narrowed to:

#### Focus vectors

- `mechanics`
- `narrative`
- `vibe`
- `structure_loop`

These are the parts that still behave like real blended dimensions.

The current working view is:

- vectors should describe the game’s major focus
- not every important concept deserves to be a vector

#### Genre spine

- `primary`
- `sub`
- `sub_sub`

These are single-value fields, not lists.

The genre tree is being pushed toward:

- recommendation-useful structure
- not broad store taxonomy

So the target is more like:

- `JRPG -> calendar-driven RPG -> social dungeon crawler`

and less like:

- `RPG -> JRPG -> dungeon crawler`

#### Identity metadata

- `signature_tag`
- `niche_anchors`
- `identity_tags`
- `music_primary`
- `music_secondary`
- `micro_tags`

This is where hyper-specificity should live.

The point of this split is:

- vectors = focus
- genre spine = structure
- identity metadata = specificity / hook / niche

### What Was Removed Or De-Emphasized

The current redesign intentionally moves away from:

- `music` as a full vector
- `uniqueness` as a full vector
- multi-valued genre branches
- `traits` as a middle genre-ish layer

Reasoning:

- `music` behaves more like named identity than a blended vector
- `uniqueness` behaves more like hook identity than a weighted semantic branch
- `traits` overlapped too much with both genre and micro-tags

### Review Fetch Design

The review fetcher currently tries to balance:

- Steam helpfulness ordering
- enough corpus size for downstream sampling
- bounded runtime

Current strategy:

- start with `filter=all`
- if Steam stalls too early, fall back to `filter=recent`
- dedupe globally by `recommendationid`
- stop on:
  - page budgets
  - duplicate-page limits
  - cursor stalls
  - low-yield windows
  - enough filtered reviews

This is important because the naive version was too expensive:

- it spent far too long proving there was no more useful data

So the current fetcher is explicitly yield-aware, not just duplication-aware.

### Review Sampling Design

The sampler does not just pass arbitrary reviews to the LLM.

It currently tries to surface four different evidence lanes:

- `descriptive`
- `artistic`
- `music`
- `systems_depth`

That last one exists because surface reviews often miss the deeper reason a game is valuable.

Examples:

- `PlateUp!`
  - the hidden differentiator is automation and layout scaling
- many reviews only say:
  - fun
  - chaotic
  - co-op

So `systems_depth` is meant to recover:

- hidden mastery
- optimization
- system-level distinctiveness

### Review Quality Heuristics

Before reviews reach the LLM, the pipeline now tries to:

- reject obvious template/scorecard reviews
- downrank meme/joke reviews
- downrank repeated formatting patterns
- upweight concrete system/setting/sound/visual language

This matters because bad sample quality was one of the biggest reasons for:

- fake music tags
- fake artistic signal
- generic nostalgia sludge

### LLM Prompt Design

The prompt is now being steered toward:

- hidden differentiators
- sparse-but-correct outputs
- review-derived labels instead of example-copying
- match-useful genre paths
- concrete music style labels instead of value judgments

Important current rules:

- examples in the prompt are generic examples only
- reviews are the source of truth
- concrete criticism is valid evidence
- sparse and correct is better than complete and invented

This is especially important for `gpt-4o-mini`, which will follow examples aggressively if the prompt does not explicitly tell it not to.

### Resume Behavior

The non-canon stage is long-running by design.

Resume happens at the game-row level:

- completed `appid`s already written to `raw_game_semantics` are skipped
- interrupted in-flight games are retried

That is why you can safely rerun:

```bash
python db_creation/initial_noncanon_db.py
```

after a crash or interruption.

## Canon Stage

The canon stage exists because raw extraction should be expressive, not prematurely standardized.

What non-canon may contain:

- franchise-adjacent wording
- over-specific phrases
- multiple surface forms for the same idea

What canon should do:

- group similar raw labels
- choose a useful representative
- preserve source-membership traceability

This is where things like:

- `persona fusion`
- `fusion system`
- `monster fusion`

should be reconciled.

The canon stage is not meant to fix every bad extraction.
It is meant to standardize good-but-varied extraction.

That distinction matters:

- wrong one-off labels are a prompt/sampling problem
- over-specific but valid labels are a canon problem

## Final DB Stage

The final DB is the cleaned semantic DB for downstream consumers.

It should preserve:

- canonical vectors
- canonical metadata
- source review samples
- source vectors
- source metadata

That source traceability is important because canonicalization is not lossless in intent even when it is lossless in storage.

## Retrieval Stage

Retrieval is intentionally separate from semantic scoring.

The Chroma stage builds retrieval documents from:

- title
- signature tag
- genre spine
- micro-tags
- niche anchors
- identity tags
- music identity
- vector tags

This should optimize candidate recall.

Then the recommender can do the more structured re-ranking step afterward.

## Postgres Stage

Runtime is now Postgres-backed.

That means:

- the build pipeline still produces SQLite artifacts first
- Postgres is the runtime store loaded from those artifacts

Current wrapper:

```bash
python db_creation/postgres_db.py
```

This stage is specifically a SQLite-to-Postgres migration/load step.

Current role:

- read the finalized SQLite artifacts
- insert runtime-facing game records into Postgres
- make the FastAPI app run against Postgres instead of the old SQLite path

Important architectural point:

- Postgres is the runtime serving store
- SQLite stages are still the build-time authoring pipeline

So the source-of-truth flow remains:

1. metadata SQLite
2. non-canon SQLite
3. final canonical SQLite
4. Postgres load for runtime

That keeps the build pipeline inspectable and stage-based while still letting the live app use Postgres.

## Visual Stage

The visual pipeline is intentionally separated and currently secondary to the review/vector pipeline.

Reason:

- the semantic schema is still moving
- visual identity should be layered onto a stable schema
- otherwise you end up integrating a visual subsystem into an ontology that is still being redesigned

Current wrapper:

```bash
python db_creation/visual_pipeline.py
```

Current purpose:

- pull a game's stored image URLs from metadata
- analyze representative storefront images
- produce structured visual identity output

Current visual direction:

- render style
- presentation style
- visual traits

The intent is for this to eventually enrich the semantic DB after the review-derived schema stabilizes, not compete with the non-canon stage at the same time.

So visual work exists, but it is intentionally an add-on layer, not yet the main architecture driver.

## Running Stages Independently

Each stage can be rerun independently if its inputs already exist.

Examples:

- metadata already exists:
  - rerun non-canon only
- non-canon already exists:
  - rerun canon export only
- canonical CSVs already exist:
  - rerun final DB only
- final DB already exists:
  - rerun Chroma only
  - rerun Postgres load only

That independence is deliberate. It is one of the main reasons this repo remains workable while the semantic model is changing.

This README is the operational/design overview for what `db_creation` is and why it is organized this way.
