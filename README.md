# Steam Recommender

Find your new favorite game through game similarity. This algorithm attempts to reward video games that can't afford advertising.

**Live Demo**: https://nextsteamgame.com/

## Why This Exists

Ideally this is a one-shot app that gives you exactly what you were looking for first try! If it doesn't, then we have done something wrong.

## How This Works

Steam Recommender creates tags from 3 sources: Steam reviews, professional reviews, and video analysis. It applies intelligent weights to each tag and adds "unique" tags that separate games from others in their genre. All data is stored in an optimized SQLite database for lightning-fast searches.

### The Algorithm

**Hierarchical Genre Tree + Vector Similarity:**
1. **80% descriptive tags** - Core gameplay elements (combat, exploration, story)
2. **20% unique-in-genre tags** - What makes this game special within its category

**Three-tier niche carving:**
```
main_genre → sub_genre → sub_sub_genre
Broad Category → Specific Style → Unique Defining Element

Example: Action → Methodical Combat → Interconnected World (Dark Souls)
Example: Strategy → Turn-Based → Deck Building (Slay the Spire)
Example: Action → Platformer → Stamina-Based Combat (Hollow Knight)
```

**Similarity rewards by niche specificity:**
- Same sub_sub_genre: 0.4 bonus (shares unique defining trait)
- Same sub_genre: 0.25 bonus (similar gameplay style)
- Same main_genre: 0.15 bonus (broad category match)

## Architecture

### Clean Separation of Concerns
```
├── frontend/                    # Web interface
│   ├── static/                 # CSS, images, JS
│   └── templates/              # HTML templates
├── backend/                    # Core engine
│   ├── api/                   # Flask routes & endpoints
│   ├── core/                  # Game search & similarity engine
│   ├── config/                # Dynamic configuration
│   └── database_builder/      # Data pipeline
├── data/                      # Databases & models
└── logs/                      # Application logs
```

### Tech Stack
- **Python** - Unified language for entire pipeline
- **Flask** - Web framework for recommendation API
- **SQLite** - Hierarchical game database with vector storage
- **OpenAI GPT-3.5** - AI-powered tag generation from reviews
- **scikit-learn** - TF-IDF vectorization for similarity matching
- **Beautiful Soup & Selenium** - Web scraping for professional reviews

## Getting Started

### Prerequisites

1. **Python 3.8+** with pip
2. **OpenAI API Account** - Required for review analysis
3. **Chrome/Chromium Browser** - Required for IGN scraping (optional)
4. **3+ days of runtime** - Due to API rate limiting
5. **$50-100 budget** - Estimated OpenAI API costs

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/Steam_Reccomender.git
cd Steam_Reccomender

# Install Python dependencies
pip install -r requirements.txt

# Set your OpenAI API key
export OPENAI_API_KEY="your-openai-api-key-here"

# Optional: For automated deployment
export FLASK_SECRET_KEY="your-secure-random-key"
```

### Building the Database

The database building process is the core of this project. It takes 3+ days due to API rate limiting but produces a comprehensive game recommendation database.

#### Stage 1: Data Collection (1-2 hours)

Collects basic game information from public APIs:

```bash
# Run just the data collection stage
python -m backend.database_builder.pipeline_orchestrator --stage 1
```

**What happens:**
- Fetches 20,000 games from SteamSpy API (~1 hour)
- Enriches with Steam Store API data (pricing, images, descriptions)
- Creates initial SQLite databases: `steamspy_all_games.db` and `steam_api.db`

**Cost: FREE** - No OpenAI API calls in this stage

#### Stage 2: Review Analysis (1-2 days)

The most time-consuming and expensive stage - analyzes game reviews using AI:

```bash
# Run just the review analysis stage
python -m backend.database_builder.pipeline_orchestrator --stage 2
```

**What happens:**
- Downloads 100 Steam reviews per game (~350 games = 35,000 reviews)
- Filters out toxic/spam reviews using sentiment analysis
- Sends clean reviews to OpenAI GPT-3.5 for tag generation
- Scrapes IGN professional reviews (optional)
- Generates hierarchical game classifications

**Estimated Cost: $50-100**
- OpenAI GPT-3.5-turbo: ~$0.0015 per 1K tokens
- Average review analysis: ~500 tokens per game
- 350 games × 500 tokens × $0.0015 = ~$26 base cost
- Additional costs for retries, longer reviews, and classification

**Time: 1-2 days**
- OpenAI rate limits: 3 requests per minute (free tier)
- Steam API rate limits: 1 request per second
- IGN scraping delays: 2-5 seconds between requests

#### Stage 3: Database Creation (30 minutes)

Optimizes the analyzed data into the final recommendation database:

```bash
# Run just the database creation stage
python -m backend.database_builder.pipeline_orchestrator --stage 3
```

**What happens:**
- Converts JSON analysis results to optimized SQLite schema
- Creates TF-IDF vectors from game tags (1000-dimensional)
- Stores vectors as binary BLOBs for fast similarity calculations
- Creates performance indexes for sub-second queries
- Generates final `steam_recommendations.db`

**Cost: FREE** - No API calls, pure data processing

#### Complete Pipeline

To run all stages automatically:

```bash
# Run the complete pipeline (3+ days)
python -m backend.database_builder.pipeline_orchestrator

# Skip the warning prompt for automation
python -m backend.database_builder.pipeline_orchestrator --skip-warning
```

#### Cost Breakdown

| Component | Estimated Cost | Notes |
|-----------|----------------|-------|
| SteamSpy API | FREE | Public API, 1 second rate limit |
| Steam Store API | FREE | Public API, respects rate limits |
| OpenAI GPT-3.5 | $50-100 | 350 games × ~500 tokens per analysis |
| IGN Scraping | FREE | Web scraping with delays |
| **Total Estimated Cost** | **$50-100** | Mainly OpenAI API usage |

#### Reducing Costs

1. **Start small**: Modify `DATA_COLLECTION['max_games']` in `backend/config/settings.py`
2. **Use existing data**: Skip Stage 2 if you have analysis JSON files
3. **OpenAI alternatives**: Modify the review analyzer to use local models
4. **Caching**: The pipeline saves checkpoints to resume from interruptions

### Running the Application

Once you have the database built (or download pre-built databases):

```bash
# Start the Flask web application
python app.py
```

Visit `http://localhost:5000` to use the recommender.

### Using Pre-built Databases

If you don't want to spend the time/money building the database:

1. Download pre-built databases (if available)
2. Place them in the `data/` directory:
   - `steam_recommendations.db` (required)
   - `hierarchical_vectorizer.pkl` (required)
   - `steam_api.db` (optional, for images/pricing)

## Configuration

All settings are centralized in `backend/config/settings.py`:

```python
# Customize data collection
DATA_COLLECTION = {
    'max_games': 20000,        # Reduce for testing
    'reviews_per_game': 100,   # Reduce to lower OpenAI costs
    'batch_size': 1000,
    'checkpoint_interval': 100
}

# Adjust rate limits
RATE_LIMITS = {
    'openai_max_retries': 3,
    'steam_api_delay': 0.5,    # Increase if rate limited
}
```

## Current Stats

- **~350 games** in database
- **3-source analysis** per game (Steam reviews, IGN, YouTube)
- **1000-dimensional** TF-IDF vectors for similarity
- **Sub-second** recommendation responses

## Data Pipeline Details

**Stage 1: Data Collection (1-2 hours)**
- SteamSpy API → 20k game catalog
- Steam Store API → metadata, pricing, images

**Stage 2: Review Analysis (1-2 days)**
- Steam Reviews + OpenAI → intelligent tag generation
- IGN Scraping → professional review scores
- Hierarchical classification → genre taxonomy

**Stage 3: Database Creation (30 mins)**
- JSON → optimized SQLite schema
- TF-IDF vectorization → binary BLOB storage
- Performance indexing → sub-second queries

## Limitations

The data pipeline takes 3+ days due to API rate limiting, so the database is typically 3 months old. This trade-off ensures we can analyze games thoroughly without overwhelming external APIs.

**API Rate Limits:**
- OpenAI: 3 requests/minute (free tier), 60 requests/minute (paid)
- Steam Store: ~1 request/second (unofficial limit)
- SteamSpy: 1 request/second (official limit)

## Todo

- Context-aware review analysis (mention previous games)
- Convert Flask app to FastAPI (hitting performance limits)
- Implement ChromaDB for enhanced semantic similarity
- Humble Bundle affiliate integration

## Important Notice

If any reviewing companies want their data removed from this program, please let me know. This is a data science project for educational purposes.

I run minimal ads because I'm a broke college student trying to break even on server costs.

## Development

### Project Structure
- **Modular Architecture** - Clean separation between frontend, API, core logic, and data pipeline
- **Dynamic Configuration** - Centralized settings with environment variable support
- **Type Hints** - Full type annotations for better code quality
- **Error Handling** - Comprehensive exception management with graceful fallbacks

### Key Features
- **Hierarchical Genre Matching** - Multi-tier similarity scoring
- **Vector Similarity Engine** - TF-IDF cosine similarity with tag-based fallback
- **Intelligent Rate Limiting** - Respects API limits with exponential backoff
- **Checkpoint System** - Resume long-running processes from interruptions

### API Endpoints
- `GET /` - Main interface
- `POST /search` - Game search and preference selection
- `POST /recommend` - Generate recommendations
- `GET /api/search` - Search suggestions (JSON)
- `GET /debug/stats` - Database statistics
- `GET /health` - System health check

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes with proper type hints and documentation
4. Test with a small dataset first (`max_games = 50`)
5. Submit a pull request

### Testing

```bash
# Test with a small dataset (reduces costs)
# Edit backend/config/settings.py:
DATA_COLLECTION['max_games'] = 50

# Run quick pipeline test
python -m backend.database_builder.pipeline_orchestrator --stage 1
```