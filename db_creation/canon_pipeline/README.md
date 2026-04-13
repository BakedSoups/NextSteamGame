# `canon_pipeline`

This pipeline turns the non-canonical semantic output into canonical grouping artifacts.

Primary code:

- `db_creation/canon_pipeline/pipeline.py`
- `db_creation/canon_pipeline/full_export.py`
- `db_creation/canon_pipeline/candidate_search.py`
- `db_creation/canon_pipeline/tag_loader.py`
- entry points:
  - `db_creation/canon_preview.py`
  - `db_creation/canon_export.py`

## What It Does

- reads `steam_initial_noncanon.db`
- collects raw metadata and vector tags
- normalizes surface variants
- groups similar tags into canonical representatives
- writes canonical CSV outputs for review

## Non-Canon To Canon

This stage turns raw semantic output into a controlled vocabulary.

In the non-canon database, every game stores direct review-derived model output. That output is useful, but intentionally messy. Different games can express the same idea with:

- casing differences
- hyphen vs underscore vs space differences
- singular/plural drift
- descriptive variants
- near-synonyms
- broader head terms mixed with subtype terms

The canon stage exists to clean that up without flattening meaningful distinctions.

### 1. Surface Normalization

Raw tags are first normalized into a common comparison form.

This handles formatting-level drift such as:

- `action-packed`
- `action_packed`
- `action packed`

### 2. Family Building

Tags are grouped into local semantic families before merge decisions are made.

A family is a local cluster of tags that appear to share a core idea or head term, for example:

- `interaction`
- `social interaction`
- `character interaction`
- `environment interaction`

This keeps the pipeline from comparing unrelated tags globally. It narrows the merge decision space to tags that are plausibly related.

### 3. Specificity Analysis

Inside a family, the pipeline tries to distinguish:

- weak or descriptive modifiers
- process-like modifiers
- subtype-bearing modifiers
- domain-specific modifiers
- broader parent concepts

This is where the canon layer decides what should collapse and what should remain separate.

Examples:

- `hectic action` may collapse into a broader action family
- `action RPG` should remain distinct from plain `action`
- `family betrayal` should remain distinct from plain `betrayal`
- `character betrayal` may collapse if the modifier is too generic

### 4. Representative Selection

After a group is accepted, one tag is chosen as the canonical representative.

That representative becomes the stable label used downstream.

### 5. CSV Export

The result is written as reviewable CSV group files.

Those CSVs show:

- context
- canonical representative
- grouped members
- occurrence totals

That makes the canon layer inspectable before it is applied to the final database.

## Why This Stage Exists

The non-canon DB preserves what the model originally said.

The canon stage creates the shared language that the rest of the system can rely on.

That gives you a clear separation:

- non-canon DB = raw semantic memory
- canon CSVs = reviewed grouping layer
- final canon DB = consistent, queryable semantic database

So this stage is the normalization and vocabulary-construction layer between raw LLM output and the final production database.

Important outputs:

- `db_creation/analysis/metadata_canon_full.csv`
- `db_creation/analysis/vectors_canon_full.csv`

## Run It

Preview mode:

```bash
venv/bin/python db_creation/canon_preview.py
```

Full export mode:

```bash
venv/bin/python db_creation/canon_export.py
```

## Notes

- This stage creates mapping artifacts, not the final DB.
- The CSVs produced here are the source of truth for the next stage.
- `normalization/` and `semantics/` contain the canonical grouping logic.
