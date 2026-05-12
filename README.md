# NextSteamGame

`NextSteamGame` is a Steam recommendation project built around the idea that games
should be matched by what they are, not only by player-overlap signals.

The project has three main layers:

- a metadata pipeline that builds and enriches `steam_metadata.db`
- a review/semantics pipeline that builds `steam_initial_noncanon.db` and `steam_final_canon.db`
- a live app stack that serves recommendations through FastAPI + a React frontend backed by Postgres

## App Stack

Current runtime shape:
<img width="1445" height="1365" alt="image" src="https://github.com/user-attachments/assets/a95801fe-6c18-4c29-9026-80a6f930a60e" />


- backend: `FastAPI`
- frontend: `Next.js` / React
- runtime game store: `Postgres`
- retrieval target: local `Chroma`
- upstream build artifacts: `SQLite`

The app flow is:

1. search for a Steam game
2. open it as the reference profile
3. inspect and adjust its focus vectors, identity tags, genres, and appeal axes
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
<img width="466" height="352" alt="cool parelell workers" src="https://github.com/user-attachments/assets/4060817d-e289-4441-997f-e6eca332dd35" />

The database build flow is intentionally stage-based.

### 1. Metadata Stage

Entrypoint:

- [db_creation/metadata_db.py](db_creation/metadata_db.py)

This stage:

- refreshes Steam Store metadata for appids already present in `steam_metadata.db`
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
- uses `filter=all` first, then falls back to `recent` if Steam pagination stalls too early
- builds a raw semantic profile from the review corpus
- writes `steam_initial_noncanon.db`

Current non-canonical schema direction:

- focus vectors
  - `mechanics`
  - `narrative`
  - `vibe`
  - `structure_loop`
- genre spine
  - `primary`
  - `sub`
  - `sub_sub`
- identity metadata
  - `signature_tag`
  - `niche_anchors`
  - `identity_tags`
  - `music_primary`
  - `music_secondary`
  - `micro_tags`

The review sampler currently keeps separate lanes for:

- `descriptive`
- `artistic`
- `music`
- `systems_depth`

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
- [db_creation/postgres_db.py](db_creation/postgres_db.py)

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
- compatibility UI still exposes `uniqueness` and `music`, but the long-term semantic model is moving toward:
  - four focus vectors
  - separate identity metadata for hook/music specificity
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
- `STEAM_REC_POSTGRES_DSN`

`app.py` loads `.env` from the repo root before checking `STEAM_REC_POSTGRES_DSN`.
The semantics pipeline still reads `OPENAI_API_KEY` from the process environment.

Current rough semantics-stage scale/cost:

- about `80,000` scraped Steam games
- about `$5` total using `gpt-4o-mini`

Backend:

```bash
python app.py
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

## Docker

The Docker stack runs:

- `postgres`
- the FastAPI backend
- the Next frontend

It expects your existing local data directory to already exist, especially:

- `data/steam_metadata.db`
- `data/steam_final_canon.db`
- `data/chroma/`

Bring the app stack up:

```bash
docker compose up --build
```

Default Docker URLs:

- backend: `http://localhost:8000`
- frontend: `http://localhost:3000`

Default Docker Postgres DSN inside the stack:

```text
postgresql://steam_rec:steam_rec@postgres:5432/steam_rec
```

Default host-side Postgres DSN for running `python db_creation/postgres_db.py` against the Docker database:

```text
postgresql://steam_rec:steam_rec@127.0.0.1:5433/steam_rec
```

Notes:

- `docker compose up` does not rerun the Postgres loader
- the loader is a manual one-shot so normal app startup stays fast
- the API container reads Chroma from the mounted `data/chroma`

Manual Postgres reload from the current SQLite outputs:

```bash
python db_creation/postgres_db.py
```

Or fully inside the Docker network:

```bash
docker compose --profile loader run --rm postgres_loader
```

## Droplet Deployment

For a DigitalOcean droplet with `nextsteamgame.com`, the intended flow is:

1. clone the repo onto the droplet
2. run the server setup script once
3. use `docker compose up -d --build`
4. later, use the redeploy script for `git pull` + `compose down/up`

One-time droplet setup:

```bash
sudo DOMAIN=nextsteamgame.com bash scripts/server_deploy/setup_droplet.sh
```

What it does:

- installs Docker Engine + Docker Compose plugin
- installs Nginx and Certbot
- configures Nginx to proxy:
  - `/` -> frontend on `127.0.0.1:3000`
  - `/api/` -> backend on `127.0.0.1:8000`
- writes `NEXT_PUBLIC_API_BASE_URL=https://nextsteamgame.com` into `.env` if missing
- optionally issues the TLS certificate if `EMAIL` is provided

Start the app stack:

```bash
docker compose up -d --build
```

Note:

- this only starts the containers
- on a fresh VPS it does not load Postgres from SQLite
- on a fresh VPS it does not build Chroma
- on a fresh VPS it does not precompute candidate caches
- for first boot, use `init_server.sh` instead of stopping here

Later redeploys:

```bash
bash scripts/server_deploy/redeploy.sh
```

That script does:

- `git pull --ff-only`
- `docker compose down`
- `docker compose up -d --build`

## Rsync Deployment Flow

If you want to deploy by pushing the repo directly to the server instead of pulling on-server:

Local machine:

```bash
bash scripts/server_deploy/rsync_push.sh
```

Defaults come from `scripts/server_deploy/.env`:

- remote host: `REMOTE_HOST`
- remote dir: `REMOTE_DIR`
- ssh key: `SSH_KEY`

Then SSH to the server:

```bash
bash scripts/server_deploy/ssh_remote.sh
cd /root/steamrec2
```

## VPS Deployment

Use this order on a brand new VPS.

### 1. Configure deployment env locally

Edit `scripts/server_deploy/.env` and make sure these are correct:

- `REMOTE_HOST=root@YOUR_SERVER_IP`
- `REMOTE_DIR=/root/steamrec2`
- `SSH_KEY=$HOME/.ssh/id_ed25519`
- `DOMAIN=your-domain.com`
- `EMAIL=you@example.com`

### 2. Push the repo to the VPS

From your local machine:

```bash
bash scripts/server_deploy/rsync_push.sh
```

### 3. Run first-time server init

This is the correct first-boot command. It handles:

- OS/bootstrap setup
- Docker + Nginx + Certbot
- Postgres load from SQLite
- Chroma build
- candidate precompute
- API/frontend startup

```bash
bash scripts/server_deploy/run_remote.sh "cd /root/steamrec2 && sudo DOMAIN=nextsteamgame.com bash scripts/server_deploy/init_server.sh"
```

### 4. Smoke test the live site

From the server or your local machine:

```bash
curl -I https://nextsteamgame.com
curl "https://nextsteamgame.com/api/search?q=hades"
```

If you want to check the containers on the server:

```bash
bash scripts/server_deploy/run_remote.sh "cd /root/steamrec2 && docker compose ps"
```

### 5. Later deploys

Use the smallest script that matches the change.

Frontend-only deploy:

```bash
bash scripts/server_deploy/run_remote.sh "cd /root/steamrec2 && docker compose up --build -d frontend"
```

Code-only app deploy, without data refresh:

```bash
bash scripts/server_deploy/run_remote.sh "cd /root/steamrec2 && docker compose up --build -d api frontend"
```

Frontend-only deploy:

```bash
docker compose up --build -d frontend
```

Code-only app deploy, without data refresh:

```bash
docker compose up --build -d api frontend
```

Full cutover, when canonical data or retrieval data changed:

```bash
bash scripts/server_deploy/run_remote.sh "cd /root/steamrec2 && sudo DOMAIN=nextsteamgame.com bash scripts/server_deploy/cutover_server.sh"
```

First-time server initialization, including server bootstrap, Postgres load, Chroma build, and candidate precompute:

```bash
bash scripts/server_deploy/run_remote.sh "cd /root/steamrec2 && sudo DOMAIN=nextsteamgame.com bash scripts/server_deploy/init_server.sh"
```

If you only need to rebuild retrieval data on the VPS and want to let it run in the background:

```bash
bash scripts/server_deploy/run_remote.sh "cd /root/steamrec2 && bash scripts/server_deploy/rebuild_retrieval_async.sh"
```

Then check status later with:

```bash
bash scripts/server_deploy/run_remote.sh "cd /root/steamrec2 && bash scripts/server_deploy/rebuild_retrieval_status.sh"
```

Server-side stack involved in deploys:

- Docker Compose for `api`, `frontend`, and `postgres`
- Nginx as the public reverse proxy
- Certbot for HTTPS/TLS certificate management
- Postgres for canonical game data and cached candidate pools
- Chroma for semantic retrieval data
- SQLite `steam_final_canon.db` as the build artifact that feeds Postgres and Chroma

That cutover script:

- stops the old gunicorn path on port `5000`
- rewrites the Nginx proxy config
- brings the Docker stack down
- rebuilds and starts the Docker stack
- rebuilds `steam_final_canon.db` from `canon_groups_v6.csv` with `--skip-canon`
- reloads Postgres from the rebuilt final SQLite DB
- rebuilds Chroma from the rebuilt final SQLite DB
- regenerates `precomputed_candidates`
- reloads Nginx

Use full cutover only when data/build artifacts changed, such as:

- `canon_groups_v6.csv`
- `steam_final_canon.db`
- Postgres-loaded canonical game data
- Chroma collection contents
- precomputed candidate cache

For UI-only changes, do not run full cutover. Just rebuild `frontend`.

This is the safer version of “kill the old ports and serve from Docker” because it only targets:

- the old gunicorn app on `5000`
- the app’s Docker stack
- the app’s Nginx config

## Useful One-Off Runs

Run the non-canonical pipeline:

```bash
python db_creation/initial_noncanon_db.py
```

Run a single-game non-canonical test without writing the full DB:

```bash
python db_creation/noncanon_pipeline/test_single_game.py 1599600
```

Run the Postgres load wrapper:

```bash
python db_creation/postgres_db.py
```

Run the visual pipeline wrapper:

```bash
python db_creation/visual_pipeline.py
```

## Current Direction

The repo is in the middle of a semantic-data redesign.

The main direction is:

- keep only four true focus vectors:
  - `mechanics`
  - `narrative`
  - `vibe`
  - `structure_loop`
- keep genre as a single committed spine
- move music and hook/uniqueness information into identity metadata instead of full vectors
- improve hyper-niche capture through:
  - better review sampling
  - `niche_anchors`
  - `identity_tags`
  - deeper systems-focused review extraction

The working design notes for that are in:

- [db_creation/UPDATE_REVIEW_PIPELINE.md](db_creation/UPDATE_REVIEW_PIPELINE.md)
- [frontend/UPDATE_UI_FOR_VECTOR_DB.md](frontend/UPDATE_UI_FOR_VECTOR_DB.md)
