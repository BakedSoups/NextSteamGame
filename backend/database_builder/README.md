# Steam Recommender Database Builder

This directory contains the Python-based data pipeline for building the Steam game recommendation database. The pipeline has been converted from Go to Python for better maintainability and integration.

## 🏗️ Pipeline Overview

The complete data pipeline consists of 3 stages that take ~3 days due to API rate limits:

```
Stage 1: Data Collection (1-2 hours)
├── SteamSpy API → steamspy_all_games.db
└── Steam Store API → steam_api.db

Stage 2: Review Analysis (1-2 days)
├── Steam Reviews → OpenAI Analysis → Tags
├── IGN Reviews → Web Scraping → Professional scores
└── Hierarchical Classification → JSON

Stage 3: Database Creation (30 mins)
├── JSON → SQLite schema
├── TF-IDF Vectorization
└── steam_recommendations.db + hierarchical_vectorizer.pkl
```

## 🚀 Quick Start

### Run Complete Pipeline
```bash
python pipeline_orchestrator.py
```

### Run Specific Stage
```bash
python pipeline_orchestrator.py --stage 1  # Data collection only
python pipeline_orchestrator.py --stage 2  # Review analysis only
python pipeline_orchestrator.py --stage 3  # Database creation only
```

### Skip Warning Prompt
```bash
python pipeline_orchestrator.py --skip-warning
```

## 📁 File Structure

### Core Pipeline Modules
- `pipeline_orchestrator.py` - Main orchestration script
- `steamspy_collector.py` - Collects 20k games from SteamSpy API
- `steam_api_enricher.py` - Enriches with Steam Store data (pricing, images, etc.)
- `database_manager.py` - Database schema creation and migration

### Tag Builder Modules (Python)
- `tag_builder/steam_reviews_extractor.py` - Steam review analysis with OpenAI
- `tag_builder/ign_scrape.py` - IGN professional review scraping
- `tag_builder/extract_verdicts.py` - Hierarchical game classification
- `tag_builder/json_converter.py` - Final database creation with vectors

### Legacy Modules (Go - Deprecated)
- `*.go` files - Original Go implementation (no longer used)

## 🔧 Dependencies

### Required Python Packages
```bash
pip install requests sqlite3 numpy scikit-learn openai beautifulsoup4 selenium vaderSentiment
```

### Required Environment Variables
```bash
export OPENAI_API_KEY="your-openai-api-key"
```

### Optional Dependencies
- Chrome/Chromium browser (for IGN scraping)
- ChromeDriver (for Selenium)

## 🗄️ Database Schema

### Stage 1 Databases

**steamspy_all_games.db:**
```sql
all_games (appid, name, developer, publisher, positive, negative, owners)
```

**steam_api.db:**
```sql
main_game (game_id, game_name, steam_appid)
steam_spy (steam_appid, positive_reviews, negative_reviews, owners)
steam_api (steam_appid, description, header_image, pricing, etc.)
genres (steam_appid, genre)
ign_scores (steam_appid, ign_score, review_text)
```

### Stage 3 Database

**steam_recommendations.db:**
```sql
games (steam_appid, name, main_genre, sub_genre, sub_sub_genre, art_style, theme)
steam_tags (steam_appid, tag, tag_order)
unique_tags (steam_appid, tag, tag_order)
subjective_tags (steam_appid, tag, tag_order)
tag_ratios (steam_appid, tag, ratio)
game_vectors (steam_appid, vector_data BLOB, vector_dimension)
```

## 🎯 Key Features

### Multi-Source Data Collection
- **SteamSpy**: Game catalog with ownership/review data
- **Steam Store API**: Official descriptions, pricing, screenshots
- **Steam Reviews**: User sentiment analysis (100 reviews per game)
- **IGN Reviews**: Professional review scores and content

### AI-Powered Tag Generation
- **OpenAI GPT-3.5**: Analyzes Steam reviews to generate tags
- **Hierarchical Classification**: 3-tier genre taxonomy (main → sub → sub_sub)
- **Percentage Ratios**: Gameplay element breakdown (combat:40%, exploration:30%)
- **Quality Tags**: Subjective assessments (polished, buggy, addictive)

### Vector Similarity Engine
- **TF-IDF Vectorization**: 1000-dimensional vectors from tag combinations
- **Binary Storage**: Numpy arrays stored as SQLite BLOBs
- **Fast Retrieval**: Pre-computed vectors for O(1) similarity lookups

### Rate Limiting & Error Recovery
- **Intelligent Backoff**: Respects API Retry-After headers
- **Checkpoint System**: Resume from interruptions
- **Quality Filtering**: Sentiment analysis, spam detection
- **Graceful Degradation**: Fallback mechanisms for missing data

## ⚡ Performance Optimizations

### Database Optimizations
- Strategic indexing on hierarchy (main_genre, sub_genre, sub_sub_genre)
- Batch inserts with transactions
- Compound indexes for fast genre tree traversal

### API Optimizations
- Concurrent requests with rate limiting
- Request pooling and retry logic
- Progress checkpoints for long-running processes

### Memory Optimizations
- Streaming JSON processing
- Sparse matrix conversion only during storage
- Batch processing to limit memory usage

## 🔍 Monitoring & Debugging

### Logging
All modules log to both console and `pipeline.log`:
```bash
tail -f pipeline.log  # Monitor progress
```

### Database Statistics
```bash
python database_manager.py  # Print database summary
```

### Debug Endpoints (after completion)
```bash
python app.py
# Visit: http://localhost:5000/debug/stats
```

## 🚨 Common Issues

### OpenAI API Limits
- **Quota Exceeded**: Pipeline will skip games and continue
- **Rate Limits**: Automatic exponential backoff (max 3 retries)
- **Cost Control**: ~$50-100 for full 350-game analysis

### Steam API Rate Limits
- **429 Errors**: Respects Retry-After headers
- **HTML Responses**: Detects error pages and retries
- **Network Issues**: Exponential backoff with max retries

### Memory Issues
- **Large Datasets**: Use batch processing (default: 1000 games)
- **Vector Storage**: Optimize max_features if memory constrained

## 📊 Expected Timeline

| Stage | Duration | Bottleneck | Output |
|-------|----------|------------|---------|
| Stage 1 | 1-2 hours | Steam API rate limits | ~20k games with metadata |
| Stage 2 | 1-2 days | OpenAI API + web scraping | ~350 analyzed games |
| Stage 3 | 30 minutes | Vector computation | Production database |

## 🎉 Pipeline Outputs

After successful completion:

1. **steam_recommendations.db** - Main production database
2. **hierarchical_vectorizer.pkl** - TF-IDF model for runtime
3. **checkpoint_steam_analysis.json** - Intermediate analysis results
4. **ign_all_games.json** - Professional review data
5. **pipeline.log** - Complete execution log

## 🔄 Migration from Go

The Python pipeline replaces the original Go implementation:

| Go Module | Python Equivalent | Status |
|-----------|-------------------|---------|
| `init_steamSpy.go` | `steamspy_collector.py` | ✅ Complete |
| `dag_steamapi.go` | `steam_api_enricher.py` | ✅ Complete |
| `db.go` | `database_manager.py` | ✅ Complete |
| `ign_migration.go` | `database_manager.py` | ✅ Complete |
| `orchestrator.go` | `pipeline_orchestrator.py` | ✅ Complete |

Benefits of Python conversion:
- **Unified Language**: Single language for entire pipeline
- **Better Error Handling**: More robust exception management
- **Easier Maintenance**: Integrated with existing Python ML stack
- **Enhanced Logging**: Comprehensive monitoring and debugging