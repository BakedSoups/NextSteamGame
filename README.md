# Steam Recommender

Find your new favorite game through game similarity. This algorithm attempts to reward video games that can't afford advertising.

**Live Demo**: https://nextsteamgame.com/

## 🎯 Why This Exists

Ideally this is a one-shot app that gives you exactly what you were looking for first try! If it doesn't, then we have done something wrong.

## 🧠 How This Works

Steam Recommender creates tags from 3 sources: Steam reviews, professional reviews, and video analysis. It applies intelligent weights to each tag and adds "unique" tags that separate games from others in their genre. All data is stored in an optimized SQLite database for lightning-fast searches.

### The Algorithm

**Hierarchical Genre Tree + Vector Similarity:**
1. **80% descriptive tags** - Core gameplay elements (combat, exploration, story)
2. **20% unique-in-genre tags** - What makes this game special within its category

**Three-tier genre classification:**
```
main_genre → sub_genre → sub_sub_genre
Example: action → rpg → open-world
```

**Similarity rewards by proximity:**
- Same sub_sub_genre: 0.4 bonus
- Same sub_genre: 0.25 bonus
- Same main_genre: 0.15 bonus

## 🏗️ Architecture

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

## 🚀 Setup & Usage

### Quick Start
```bash
# Install dependencies
pip install -r requirements.txt

# Set OpenAI API key
export OPENAI_API_KEY="your-api-key"

# Run complete data pipeline (3+ days)
python -m backend.database_builder.pipeline_orchestrator

# Start web application
python app.py
```

### Development Pipeline
```bash
# Run specific pipeline stages
python -m backend.database_builder.pipeline_orchestrator --stage 1  # Data collection
python -m backend.database_builder.pipeline_orchestrator --stage 2  # Review analysis
python -m backend.database_builder.pipeline_orchestrator --stage 3  # Database creation

# Skip warning for automation
python -m backend.database_builder.pipeline_orchestrator --skip-warning
```

### Configuration

All settings are centralized in `backend/config/settings.py`:
- Database paths
- API endpoints and rate limits
- ML/Vector parameters
- Web server configuration

## 📊 Current Stats

- **~350 games** in database
- **3-source analysis** per game (Steam reviews, IGN, YouTube)
- **1000-dimensional** TF-IDF vectors for similarity
- **Sub-second** recommendation responses

## 🔄 Data Pipeline

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

## 🎮 Preview

![Steam Recommender Interface](https://github.com/user-attachments/assets/3d99ff7f-d75b-48f4-a5c9-cf9a1c59a0fc)

![Game Recommendations](https://github.com/user-attachments/assets/5f2c0604-38f6-497f-ab21-1363ce99a627)

## 📋 Todo

- Context-aware review analysis (mention previous games)
- Convert Flask app to FastAPI (hitting performance limits)
- Implement ChromaDB for enhanced semantic similarity
- Humble Bundle affiliate integration

## 🚨 Limitations

The data pipeline takes 3+ days due to API rate limiting, so the database is typically 3 months old. This trade-off ensures we can analyze games thoroughly without overwhelming external APIs.

## ⚠️ Important Notice

If any reviewing companies want their data removed from this program, please let me know. This is a data science project for educational purposes.

I run minimal ads because I'm a broke college student trying to break even on server costs.

## 🛠️ Development

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