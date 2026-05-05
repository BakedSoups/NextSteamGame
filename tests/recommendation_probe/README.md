# Recommendation Probe

Small local probe scripts for reproducing recommendation behavior without the frontend.

This uses the same core runtime path as the app:

1. load a game from Postgres
2. run Postgres prescreen + Chroma retrieval
3. rerank candidates with the backend recommender

## Setup

Export the same Postgres DSN the app uses:

```bash
export STEAM_REC_POSTGRES_DSN=postgresql://steam_rec:steam_rec@127.0.0.1:5433/steam_rec
```

Run from the repo root:

```bash
python3 tests/recommendation_probe/probe_recommendations.py --game "PlateUp!"
```

## Useful examples

Probe a game by exact appid:

```bash
python3 tests/recommendation_probe/probe_recommendations.py --appid 1599600
```

Boost a tag in a specific recommendation lane:

```bash
python3 tests/recommendation_probe/probe_recommendations.py \
  --game "PlateUp!" \
  --boost structure_loop:"roguelike progression"=100
```

Try multiple boosts:

```bash
python3 tests/recommendation_probe/probe_recommendations.py \
  --game "Persona 5 Royal" \
  --boost identity:"Phantom Thieves"=100 \
  --boost music:"jazz fusion"=70
```

Override retrieval breadth:

```bash
python3 tests/recommendation_probe/probe_recommendations.py \
  --game "Hades" \
  --prescreen-limit 450 \
  --chroma-limit 300 \
  --merged-limit 300
```

## Boost format

Use:

```text
context:tag=value
```

Examples:

- `structure_loop:roguelike progression=100`
- `mechanics:automation mechanics=90`
- `identity:Phantom Thieves=100`
- `music:jazz fusion=60`

Allowed contexts:

- `mechanics`
- `narrative`
- `vibe`
- `structure_loop`
- `identity`
- `setting`
- `music`

## What it prints

- selected game summary
- active boost map
- retrieval timings
- candidate count
- top recommendation results with:
  - score
  - signature tag
  - matched tags
  - context breakdown

This is for debugging recommendation behavior, not for automated assertions.
