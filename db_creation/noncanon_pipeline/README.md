# `noncanon_pipeline`

This pipeline builds raw semantic outputs from Steam reviews before any canonical grouping happens.

Primary code:

- `db_creation/noncanon_pipeline/pipeline.py`
- `db_creation/noncanon_pipeline/steam_review.py`
- `db_creation/noncanon_pipeline/llm/game_semantics.py`
- entry point: `db_creation/initial_noncanon_db.py`
- DB builder: `db_creation/db_builders/initial_noncanon_db/builder.py`

## What It Does

For each game:

1. fetch Steam reviews
2. filter them
3. select insightful review samples
4. call the semantics model once to generate:
   - `vectors`
   - `metadata`
5. write the raw result into the non-canon DB

Important output DB:

- `data/steam_initial_noncanon.db`

## Run It

```bash
venv/bin/python db_creation/initial_noncanon_db.py
```

## Notes

- This stage resumes automatically using existing `appid` rows already stored in `raw_game_semantics`.
- It intentionally stores raw semantic output, not canonicalized output.
- Skip reasons like `No reviews`, `No insightful reviews`, and `no_steam_review` are part of this stage.
- This is the slowest stage because it depends on Steam review fetches and LLM generation.
