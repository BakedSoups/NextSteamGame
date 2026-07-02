# `chroma_pipeline`

This stage migrates recommendation retrieval data from `steam_final_canon.db`
into a local Chroma collection.

The intended split is:

- `sqlite` remains the source of truth for page/search/render content
- `chroma` becomes the candidate-retrieval layer for nearest-neighbor lookups

## Current Scope

The migration currently:

1. Reads canonical rows from `canonical_game_semantics`
2. Prepares a retrieval document per game
3. Writes those records into a local Chroma collection directory

This stage is designed so the app can later:

1. load a selected game from `sqlite`
2. retrieve top `k` candidate neighbors from Chroma
3. rerank those candidates locally using the live UI weighting controls

## Run

```bash
venv/bin/python db_creation/chroma_db_migration.py
```

## Inputs

- `data/steam_final_canon.db`

## Outputs

- `data/chroma/`

## Notes

- Chroma is for retrieval, not page content
- `appid` is the join key back into `sqlite`
- this stage intentionally keeps metadata payloads lightweight
