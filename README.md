# NextSteamGame

`NextSteamGame` is a Steam recommendation project built around the idea that games
should be matched by what they are, not only by player-overlap signals.

The project has three main layers:

- a metadata pipeline that builds and enriches `steam_metadata.db`
- a semantics/canonicalization pipeline that builds `steam_final_canon.db`
- a live app stack that serves recommendations through FastAPI + a React frontend

## App Stack

Current runtime shape:

- backend: `FastAPI`
- frontend: `Next.js` / React
- metadata store: `SQLite`
- retrieval target: `Chroma`

The app flow is:

1. search for a Steam game
2. open it as the reference profile
3. inspect and adjust its vectors, tags, genres, and appeal axes
4. rerank recommendations from the game’s actual semantic profile

## Main Databases

By default the databases live in `data/`:

- `steam_metadata.db`
- `steam_initial_noncanon.db`
- `steam_final_canon.db`
- `chroma/`

Path handling is centralized in:

- [db_creation/paths.py](db_creation/paths.py)

## Pipeline Overview

The database build flow is intentionally stage-based.

### 1. Metadata Stage

Entrypoint:

- [db_creation/metadata_db.py](db_creation/metadata_db.py)

This stage:

- syncs SteamSpy + Steam Store metadata
- writes `steam_metadata.db`
- backfills extra storefront art assets like:
  - `logo_image`
  - `library_hero_image`
  - `library_capsule_image`

Internal modules:

- [db_creation/metadata_pipeline/pipeline.py](db_creation/metadata_pipeline/pipeline.py)
- [db_creation/metadata_pipeline/assets.py](db_creation/metadata_pipeline/assets.py)

Run:

```bash
cd db_creation
python3 metadata_db.py
```

### 2. Non-Canonical Semantics Stage

Entrypoint:

- [db_creation/initial_noncanon_db.py](db_creation/initial_noncanon_db.py)

This stage:

- reads `steam_metadata.db`
- fetches and samples Steam reviews
- calls the semantics model
- writes `steam_initial_noncanon.db`

### 3. Canon Export Stage

Entrypoint:

- [db_creation/canon_export.py](db_creation/canon_export.py)

This stage:

- reads the non-canonical DB
- exports canonical tag group CSVs into `db_creation/analysis/`

### 4. Final Canonical DB Stage

Entrypoint:

- [db_creation/final_db.py](db_creation/final_db.py)

This stage:

- reads the non-canonical DB
- reads canonical mapping CSVs
- builds `steam_final_canon.db`

### 5. Chroma Migration Stage

Entrypoint:

- [db_creation/chroma_db_migration.py](db_creation/chroma_db_migration.py)

This stage:

- reads `steam_final_canon.db`
- writes retrieval-ready records into local `Chroma`

### 6. Visualization / QA Stage

Entrypoint:

- [db_creation/final_db_viz.py](db_creation/final_db_viz.py)

This stage:

- reads `steam_final_canon.db`
- generates QA charts and summary artifacts

## Entry Point Pattern

Top-level stage scripts in `db_creation/` are intentionally lightweight orchestration entrypoints.

The pattern is:

- constants/config at the top
- a `run_...()` function for the stage
- a `print_run_configuration()`
- a `print_run_summary(...)`
- a small `main()` that reads like the workflow

Examples:

- [db_creation/metadata_db.py](db_creation/metadata_db.py)
- [db_creation/initial_noncanon_db.py](db_creation/initial_noncanon_db.py)
- [db_creation/canon_export.py](db_creation/canon_export.py)
- [db_creation/final_db.py](db_creation/final_db.py)
- [db_creation/chroma_db_migration.py](db_creation/chroma_db_migration.py)

## Metadata Art Fields

The metadata layer currently uses these storefront image fields in `games`:

- `header_image`
- `capsule_image`
- `capsule_imagev5`
- `background_image`
- `background_image_raw`
- `logo_image`
- `library_hero_image`
- `library_capsule_image`

`icon_image` was intentionally removed from the active pipeline because it was not being populated reliably and is not used by the app.

## Frontend / Recommendation Surface

The live UI is built around:

- a search-first landing page
- a profile-building second screen
- a results screen with ongoing tuning

The recommendation controls currently include:

- match weighting
  - `vector`
  - `genre`
  - `appeal`
  - `music`
- context weighting
  - `mechanics`
  - `narrative`
  - `vibe`
  - `structure_loop`
  - `uniqueness`
  - `music`
- appeal axes
  - `challenge`
  - `complexity`
  - `pace`
  - `narrative_focus`
  - `social_energy`
  - `creativity`
- per-context tag weighting
- genre tree toggles

## Running the App

## Environment

The semantics pipeline reads the OpenAI key from the process environment:

- `OPENAI_API_KEY`

The code currently uses `os.getenv(...)` directly and does not rely on a built-in
`.env` loader, so export the variable in your shell or provide it through your
runtime environment.

Current rough semantics-stage scale/cost:

- about `80,000` scraped Steam games
- about `$5` total using `gpt-4o-mini`

Backend:

```bash
python3 app.py
```

Frontend dev server:

```bash
cd frontend
npm run dev
```

Frontend production:

```bash
cd frontend
npm run build
npm start
```

Default local URLs:

- backend: `http://127.0.0.1:8000`
- frontend: `http://localhost:3000`
