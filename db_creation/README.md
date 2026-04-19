# `db_creation`

This folder contains the full database build flow for the project.

The stages are intentionally separate:

1. `metadata_db.py`
   Builds the raw/canonical Steam metadata database from the Steam APIs and then backfills extra storefront art assets.
2. `initial_noncanon_db.py`
   Builds the first semantic database from review-derived LLM output.
3. `canon_export.py`
   Reads the non-canon DB and exports canonical group CSVs.
4. `final_db.py`
   Reads the non-canon DB plus the canonical CSV mappings and builds the final canonical DB.
5. `chroma_db_migration.py`
   Reads the final canonical DB and migrates retrieval records into a local Chroma collection.
6. `final_db_viz.py`
   Reads the final DB and generates QA visualizations.

## Main Files

- `db_creation/metadata_db.py`
- `db_creation/initial_noncanon_db.py`
- `db_creation/canon_preview.py`
- `db_creation/canon_export.py`
- `db_creation/final_db.py`
- `db_creation/chroma_db_migration.py`
- `db_creation/final_db_viz.py`
- `db_creation/paths.py`

## Pipeline Folders

- `db_creation/metadata_pipeline`
  Builds the raw Steam metadata database from SteamSpy and Steam Store API data.
- `db_creation/noncanon_pipeline`
  Builds raw review-derived semantic outputs before any canonical grouping.
- `db_creation/canon_pipeline`
  Converts messy non-canonical tags into canonical CSV mapping artifacts.
- `db_creation/final_pipeline`
  Applies canonical mappings and builds the final canonical SQLite database.
- `db_creation/chroma_pipeline`
  Migrates retrieval records from the final DB into the local Chroma collection.
- `db_creation/db_builders`
  Contains lower-level database builder implementations used by entry scripts.

## Databases

By default the databases live in `data/`:

- `steam_metadata.db`
- `steam_initial_noncanon.db`
- `steam_final_canon.db`
- `chroma/`

`paths.py` centralizes where those files are read and written.

## How The Stages Fit Together

### 1. API / Metadata Stage

Run:

```bash
venv/bin/python db_creation/metadata_db.py
```

This stage talks to SteamSpy and Steam Store APIs, fills `steam_metadata.db`,
and then runs storefront asset enrichment for logos and library art.

### 2. Non-Canonical Semantic Stage

Run:

```bash
venv/bin/python db_creation/initial_noncanon_db.py
```

This stage reads `steam_metadata.db`, fetches Steam reviews, selects insightful review samples, calls the semantics model, and writes `steam_initial_noncanon.db`.

It stores more than just tags. Each game row in the non-canon DB keeps:

- selected review samples
- non-canonical semantic vectors
- non-canonical metadata

That means the non-canon DB is the raw semantic source of truth for the later canon stage, not just a temporary tag table.

This stage resumes automatically based on already-written `appid` rows in `raw_game_semantics`.

### 3. Canon Mapping Export Stage

Preview a smaller mapping run:

```bash
venv/bin/python db_creation/canon_preview.py
```

Export the full canonical group CSVs:

```bash
venv/bin/python db_creation/canon_export.py
```

This stage does not build the final DB. It generates the canonical mapping CSVs under `db_creation/analysis/`.

Important outputs:

- `metadata_canon_full.csv`
- `vectors_canon_full.csv`

### 4. Final Canonical DB Stage

Run:

```bash
venv/bin/python db_creation/final_db.py
```

This stage assumes the canonical CSVs already exist. It reads:

- `steam_initial_noncanon.db`
- `metadata_canon_full.csv`
- `vectors_canon_full.csv`

Then it builds `steam_final_canon.db`.

### 5. Chroma Retrieval Migration Stage

Run:

```bash
venv/bin/python db_creation/chroma_db_migration.py
```

This stage reads the final DB and writes Chroma retrieval records into
`data/chroma/`.

The intended architecture is:

- `sqlite` for page/search/render content
- `chroma` for candidate retrieval

### 6. Visualization / QA Stage

Run:

```bash
venv/bin/python db_creation/final_db_viz.py
```

This stage reads the final DB and writes QA charts into `db_creation/analysis/final_db_viz/`.

## Pipeline Reference

### `metadata_pipeline`

Purpose:
Builds `data/steam_metadata.db` from Steam metadata APIs. This is the raw metadata source for downstream stages.

Run:

```bash
venv/bin/python db_creation/metadata_db.py
```

### `noncanon_pipeline`

Purpose:
Reads `steam_metadata.db`, fetches reviews, runs the semantics model, and writes raw non-canonical outputs into `data/steam_initial_noncanon.db`.

Run:

```bash
venv/bin/python db_creation/initial_noncanon_db.py
```

### `canon_pipeline`

Purpose:
Reads `steam_initial_noncanon.db`, groups raw tags into canonical representatives, and writes reviewable CSV mapping artifacts.

Run preview:

```bash
venv/bin/python db_creation/canon_preview.py
```

Run full export:

```bash
venv/bin/python db_creation/canon_export.py
```

### `final_pipeline`

Purpose:
Reads the non-canon DB plus canonical CSV mappings and builds `data/steam_final_canon.db`.

Run:

```bash
venv/bin/python db_creation/final_db.py
```

### `chroma_pipeline`

Purpose:
Reads the final canonical DB and loads retrieval documents into the local Chroma store under `data/chroma/`.

Run:

```bash
venv/bin/python db_creation/chroma_db_migration.py
```

### `final_db_viz`

Purpose:
Reads the final canonical DB and generates QA charts under `db_creation/analysis/final_db_viz/`.

Run:

```bash
venv/bin/python db_creation/final_db_viz.py
```

## Running Stages Separately

Each stage can be run independently as long as its inputs already exist.

Examples:

- If `steam_metadata.db` already exists, you can run only `initial_noncanon_db.py`.
- If `steam_initial_noncanon.db` already exists, you can run only `canon_export.py`.
- If the canonical CSVs already exist, you can run only `final_db.py`.
- If `steam_final_canon.db` already exists, you can run only `chroma_db_migration.py`.
- If `steam_final_canon.db` already exists, you can run only `final_db_viz.py`.

That separation is intentional so you can:

- resume long jobs
- inspect intermediate artifacts
- tune canonical mapping before building the final DB
- rerun visualization without touching the upstream pipeline
