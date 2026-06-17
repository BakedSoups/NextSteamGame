# `metadata_pipeline`

This pipeline refreshes the Steam metadata database from Steam Store APIs for appids that already exist in the local catalog.

Primary code:

- `db_creation/metadata_pipeline/pipeline.py`
- entry point: `db_creation/metadata_db.py`

## What It Does

- enriches existing games through Steam Store `appdetails`
- writes normalized metadata tables into `steam_metadata.db`

Important output DB:

- `data/steam_metadata.db`

## Run It

```bash
venv/bin/python db_creation/metadata_db.py
```

## Main Classes

- `RetryConfig`
- `SteamMetadataBuilder`

## Notes

- This is the API-facing stage for storefront refreshes.
- SteamSpy discovery is currently disabled; this stage expects `games.appid` rows to already exist in `steam_metadata.db`.
- Downstream stages do not talk to Steam metadata endpoints directly; they consume this DB.
- The entry script owns the runtime configuration. The folder code owns the implementation.
