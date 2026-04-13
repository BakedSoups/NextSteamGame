# `final_pipeline`

This pipeline builds the final canonical database from:

- the non-canonical DB
- the canonical CSV mappings produced by `canon_pipeline`

Primary code:

- `db_creation/final_pipeline/pipeline.py`
- entry point: `db_creation/final_db.py`

## What It Does

- reads `data/steam_initial_noncanon.db`
- reads:
  - `db_creation/analysis/metadata_canon_full.csv`
  - `db_creation/analysis/vectors_canon_full.csv`
- applies those mappings game-by-game
- writes `data/steam_final_canon.db`

## Run It

```bash
venv/bin/python db_creation/final_db.py
```

## Notes

- This stage does not regenerate mappings.
- If you change the canon CSVs, rerun this stage to rebuild the final DB.
- This stage is intentionally separate from the export step so mapping review and final DB build stay independent.
