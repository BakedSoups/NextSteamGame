# NextSteamGame

`NextSteamGame` is a Steam recommendation project built around the idea that games
should be matched by what they are, not only by player-overlap signals.

Most recommendation systems rely heavily on player-overlap data:

> Players who liked X also liked Y.

That works well for popular games, but it often struggles with niche preferences and rarely explains *why* two games are similar.

For example:

- Someone may enjoy Persona 5 because of its jazz fusion soundtrack and modern Tokyo setting.
- Another player may enjoy Persona 5 because of its social simulation and dungeon crawling.

Most recommendation systems treat those users identically.

NextSteamGame attempts to separate those signals and lets users directly control what aspects of a game matter most.

The project has three main layers:

- a metadata pipeline that builds and enriches `steam_metadata.db`
- a review/semantics pipeline that builds `steam_initial_noncanon.db` and `steam_final_canon.db`
- a live app stack that serves recommendations through FastAPI + a React frontend backed by Postgres

## App Preview

Current runtime application:

<img width="1445" height="1365" alt="image" src="https://github.com/user-attachments/assets/a95801fe-6c18-4c29-9026-80a6f930a60e" />

## How Recommendations Work

I wanted a recommendation system that could answer:

> Why is this game being recommended?

Traditional recommenders often know that two games are related but cannot clearly explain the connection.

For example:

- Star Wars and Lord of the Rings may both be recommended because of a hero's journey.
- Two players may enjoy the same game for completely different reasons.
- A niche mechanic may be more important than the genre itself.

The goal of NextSteamGame is to build recommendations around a game's semantic identity rather than only player behavior.

The current database contains roughly:

- 80,000 Steam games
- up to 2,000 reviews per game
- semantic vectors
- identity tags
- canonicalized genre and tag relationships

### Stage 1: Metadata Collection

The first stage creates a local metadata database using Steam's APIs and SteamSpy.

This includes:

- appids
- genres
- tags
- descriptions
- release information
- storefront artwork

Output:

```text
steam_metadata.db
```

### Stage 2: Review Collection & Filtering

For each game, the pipeline collects up to:

```text
2,000 reviews
```

Reviews are processed through several filtering stages:

- regex spam removal
- review quality scoring
- word diversity scoring
- insightful phrase detection
- review ranking heuristics

The goal is to prioritize reviews that actually explain the game rather than memes or one-line comments.

Reviews are then classified with ModernBERT into categories such as:

- gameplay explanations
- artistic discussion
- soundtrack discussion
- systems depth
- general descriptive reviews

This gives the pipeline separate review pools focused on different aspects of a game.

### Stage 3: Semantic Tag & Vector Generation

The highest quality review candidates are then passed into an LLM extraction pipeline.

This stage generates:

#### Focus Vectors

- mechanics
- narrative
- vibe
- structure_loop

#### Identity Metadata

- signature tags
- niche anchors
- identity tags
- music tags
- micro-tags

The goal is to capture details often missing from traditional tags.

For example, many players describe PlateUp!'s late-game automation systems as the most important part of the experience despite the game primarily being categorized as a cooperative cooking game.

### Stage 4: Canonical Tag Mapping

Generated tags frequently describe the same concept using different wording.

For example:

```text
Fast Action
Quick Action
High-Speed Combat
```

All represent nearly identical ideas.

To solve this, I built a separate canonicalization pipeline using:

- heuristics
- fuzzy matching
- embedding similarity
- vector search

This groups semantically similar tags together while preserving niche distinctions.

Output:

```text
steam_final_canon.db
```

### Stage 5: Retrieval Optimization

Computing similarity between every game at runtime would be expensive.

Instead, NextSteamGame precomputes candidate relationships offline.

When a user searches:

1. candidate games are retrieved
2. user weighting is applied
3. recommendations are reranked

This keeps the live application extremely cheap while still allowing real-time customization.

## Pipeline

<img width="1688" height="1260" alt="pipeline" src="https://github.com/user-attachments/assets/fb48c02d-53c1-4afd-ae4a-d7f58fee58f1" />

- backend: `FastAPI`
- frontend: `Next.js` / React
- runtime game store: `Postgres`
- retrieval target: local `Chroma`
- upstream build artifacts: `SQLite`

The app flow is:

1. search for a Steam game
2. open it as the reference profile
3. inspect and adjust its focus vectors, identity tags, genres, and appeal axes
4. rerank recommendations from the game's semantic profile
