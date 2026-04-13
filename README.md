# Steam Metadata Schema

```mermaid
erDiagram
    GAMES {
        INTEGER appid PK
        TEXT name
        TEXT type
        INTEGER required_age
        INTEGER is_free
        TEXT controller_support
        TEXT short_description
        TEXT detailed_description
        TEXT about_the_game
        TEXT supported_languages
        TEXT header_image
        TEXT capsule_image
        TEXT website
        TEXT developers_json
        TEXT publishers_json
        TEXT price_currency
        INTEGER price_initial
        INTEGER price_final
        INTEGER price_discount_percent
        TEXT release_date_text
        INTEGER release_date_is_coming_soon
        TEXT release_date_parsed
        INTEGER metacritic_score
        INTEGER recommendations_total
        TEXT steamspy_score_rank
        TEXT steamspy_owners
        INTEGER steamspy_owner_estimate
        INTEGER steamspy_average_forever
        INTEGER steamspy_median_forever
        INTEGER steamspy_ccu
        INTEGER positive
        INTEGER negative
        INTEGER estimated_review_count
        INTEGER has_steamspy_data
        INTEGER has_store_data
        TEXT source_last_updated
        TEXT created_at
        TEXT updated_at
    }

    GAME_GENRES {
        INTEGER appid FK
        INTEGER genre_id
        TEXT genre_name
    }

    GAME_CATEGORIES {
        INTEGER appid FK
        INTEGER category_id
        TEXT category_name
    }

    GAME_TAGS {
        INTEGER appid FK
        TEXT tag_name
        INTEGER tag_rank
        REAL tag_weight
        TEXT source
    }

    GAME_PLATFORMS {
        INTEGER appid PK_FK
        INTEGER windows
        INTEGER mac
        INTEGER linux
    }

    GAME_LANGUAGES {
        INTEGER appid FK
        TEXT language
        INTEGER interface_supported
        INTEGER audio_supported
        INTEGER subtitles_supported
    }

    GAME_DEVELOPERS {
        INTEGER appid FK
        TEXT developer_name
    }

    GAME_PUBLISHERS {
        INTEGER appid FK
        TEXT publisher_name
    }

    GAME_PACKAGES {
        INTEGER appid FK
        INTEGER package_id
        INTEGER is_default
    }

    GAME_PRICING {
        INTEGER appid FK
        TEXT region_code
        TEXT currency
        INTEGER initial
        INTEGER final
        INTEGER discount_percent
        TEXT initial_formatted
        TEXT final_formatted
        INTEGER is_free
        TEXT fetched_at
    }

    GAME_SCREENSHOTS {
        INTEGER appid FK
        INTEGER screenshot_id
        TEXT path_thumbnail
        TEXT path_full
    }

    GAME_MOVIES {
        INTEGER appid FK
        INTEGER movie_id
        TEXT name
        TEXT thumbnail
        TEXT webm_480
        TEXT mp4_480
    }

    RAW_STEAMSPY_GAMES {
        INTEGER appid PK
        INTEGER source_page
        TEXT fetched_at
        TEXT payload_json
    }

    RAW_STEAM_APP_DETAILS {
        INTEGER appid
        TEXT region_code
        TEXT fetched_at
        INTEGER success
        TEXT payload_json
    }

    RAW_STEAM_APP_LIST {
        INTEGER appid
        TEXT payload_json
    }

    INGESTION_STATE {
        INTEGER appid PK
        TEXT steamspy_fetched_at
        TEXT store_fetched_at
        TEXT last_attempt_at
        TEXT store_fetch_status
        TEXT last_error
    }

    SYNC_RUNS {
        INTEGER id PK
        TEXT started_at
        TEXT finished_at
        TEXT status
        INTEGER steamspy_pages_seen
        INTEGER appids_discovered
        INTEGER store_attempted
        INTEGER store_succeeded
        INTEGER error_count
        TEXT notes
    }

    SYNC_ERRORS {
        INTEGER id PK
        INTEGER sync_run_id FK
        INTEGER appid
        TEXT source
        TEXT context
        TEXT error_message
        TEXT created_at
    }

    GAMES ||--o{ GAME_GENRES : has
    GAMES ||--o{ GAME_CATEGORIES : has
    GAMES ||--o{ GAME_TAGS : has
    GAMES ||--|| GAME_PLATFORMS : has
    GAMES ||--o{ GAME_LANGUAGES : has
    GAMES ||--o{ GAME_DEVELOPERS : has
    GAMES ||--o{ GAME_PUBLISHERS : has
    GAMES ||--o{ GAME_PACKAGES : has
    GAMES ||--o{ GAME_PRICING : has
    GAMES ||--o{ GAME_SCREENSHOTS : has
    GAMES ||--o{ GAME_MOVIES : has
    GAMES ||--|| INGESTION_STATE : tracks

    GAMES ||..|| RAW_STEAMSPY_GAMES : sourced_from
    GAMES ||..o{ RAW_STEAM_APP_DETAILS : enriched_from

    SYNC_RUNS ||--o{ SYNC_ERRORS : logs
```

## Planned Frontend

The frontend plan is HTMX-first and intentionally light on boilerplate.

Target flow:

1. search for a game from the final canonical DB
2. open that game as the starting profile
3. show the game's canonical vectors and genre tree
4. let the user adjust what they want more or less of
5. rerun scoring and update results without a full page reload

For the first UI pass:

- ignore `micro_tags`
- use only `genre_tree.primary`, `genre_tree.sub`, and `genre_tree.traits`
- apply a 10% penalty each step back in the genre hierarchy
  - `traits` = full weight
  - `sub` = 0.9
  - `primary` = 0.8

### HTMX Stack

Planned stack:

- `HTMX` for request/response-driven UI updates
- `Jinja` or small server-rendered partial templates for result fragments
- `idiomorph` for cleaner DOM morphing on fragment refresh
- `_hyperscript` for tiny local interactions without adding a large JS framework
- optional HTMX extensions later if needed for long-running jobs or advanced swaps

This keeps the UI server-rendered, fast to iterate on, and avoids a large SPA codebase.

### Planned Screen Flow

Search screen:

- search input
- live result list
- click a game to set the base profile

Profile screen:

- show selected game's canonical vectors
- show selected game's genre tree
- allow add/remove adjustments
- allow increasing certain vector tags

Results screen:

- ranked recommended games
- score breakdown
- vector overlap
- genre-tree overlap

### Backend Shape

Planned endpoints:

- `GET /`
  - shell page
- `GET /search`
  - returns search results partial
- `GET /game/{appid}`
  - returns selected game profile partial
- `POST /score`
  - returns reranked recommendations partial

### Prototype Before UI

Before implementing the frontend, the recommendation logic is being prototyped in `test.py`.

That script:

- loads `data/steam_final_canon.db`
- starts from `Counter-Strike`
- ignores `micro_tags`
- applies the current genre hierarchy penalty model
- prints ranked matches so the scoring logic can be tuned before wiring HTMX templates
