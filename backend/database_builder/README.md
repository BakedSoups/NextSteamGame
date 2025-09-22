# Steam Recommender Database Builder - Modular Pipeline

This directory contains the **completely refactored modular database builder** for the Steam Recommender system. The pipeline has been redesigned with a stage-based architecture featuring comprehensive checkpointing, error recovery, and monitoring capabilities.

## New Modular Architecture

The database builder now follows a modular pipeline architecture with three main stages:

```
Data Collection → Review Analysis → Database Creation
```

### Stage 1: Data Collection (`pipeline/data_collection_stage.py`)
- **Purpose**: Collect raw game data from SteamSpy and Steam Store APIs
- **Duration**: ~2 hours
- **Cost**: FREE (only API rate limits)
- **Outputs**: `steamspy_all_games.db`, `steam_api.db`

### Stage 2: Review Analysis (`pipeline/review_analysis_stage.py`)
- **Purpose**: Analyze Steam reviews with AI and scrape professional reviews
- **Duration**: ~1-2 days (due to OpenAI rate limits)
- **Cost**: $100-300 (OpenAI API usage)
- **Outputs**: Analysis JSON files, hierarchical classification

### Stage 3: Database Creation (`pipeline/database_creation_stage.py`)
- **Purpose**: Create final recommendation database with TF-IDF vectors
- **Duration**: ~30 minutes
- **Cost**: FREE (local processing)
- **Outputs**: `steam_recommendations.db`, `hierarchical_vectorizer.pkl`

## Quick Start (New Modular System)

### Primary Interface
```bash
# Run complete pipeline (NEW)
python database_builder.py

# Run specific stage only (NEW)
python database_builder.py --stage data_collection
python database_builder.py --stage review_analysis
python database_builder.py --stage database_creation

# Check pipeline status (NEW)
python database_builder.py --status

# Reset pipeline (NEW)
python database_builder.py --reset

# Validate configuration (NEW)
python database_builder.py --validate
```

### Legacy Interface (Still Available)
```bash
# Old orchestrator (still works)
python pipeline_orchestrator.py --stage 1
python pipeline_orchestrator.py --stage 2
python pipeline_orchestrator.py --stage 3
```

## File Structure

### New Modular Pipeline (PRIMARY)
```
pipeline/
├── __init__.py                    # Package exports
├── base_stage.py                  # Base stage interface with checkpointing
├── data_collection_stage.py       # Stage 1: SteamSpy + Steam API
├── review_analysis_stage.py       # Stage 2: AI review analysis
├── database_creation_stage.py     # Stage 3: Final database creation
└── orchestrator.py               # Enhanced orchestrator with monitoring
```

### Core Modules (Shared)
- `steamspy_collector.py` - SteamSpy data collection
- `steam_api_enricher.py` - Steam Store API enrichment
- `database_manager.py` - Database schema and migration

### Tag Builder Modules (Legacy Integration)
- `tag_builder/steam_reviews_extractor.py` - Steam review analysis with OpenAI
- `tag_builder/ign_scrape.py` - IGN professional review scraping
- `tag_builder/extract_verdicts.py` - Hierarchical game classification
- `tag_builder/json_converter.py` - JSON to SQLite conversion

### Legacy Components
- `pipeline_orchestrator.py` - Original orchestrator (deprecated but functional)

## Key Improvements in Modular System

### Advanced Checkpointing & Recovery
- **Per-stage checkpoints**: Resume from any interrupted stage
- **Progress tracking**: Detailed progress indicators with item counts
- **Smart recovery**: Automatically detect and skip completed work
- **Granular control**: Reset individual stages without affecting others

### Enhanced Monitoring & Reporting
- **Real-time status**: Live pipeline status with completion percentages
- **Cost estimation**: Accurate OpenAI API cost projections
- **Dependency validation**: Automatic checking of stage prerequisites
- **Comprehensive logging**: Structured logs with execution summaries

### Improved Developer Experience
- **Modular design**: Each stage is independently testable and maintainable
- **Type safety**: Full type hints throughout the codebase
- **Error isolation**: Stage failures don't corrupt other stages
- **Configuration management**: Centralized, environment-aware settings

### Performance & Reliability
- **Batch processing**: Configurable batch sizes for memory efficiency
- **Retry mechanisms**: Intelligent retry with exponential backoff
- **Rate limit handling**: Automatic API rate limit compliance
- **Resource optimization**: Better memory and disk space management

## Dependencies

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

## Database Schema

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

## Key Features

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

## Performance Optimizations

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

## Monitoring & Debugging

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

## Common Issues

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

## Expected Timeline

| Stage | Duration | Bottleneck | Output |
|-------|----------|------------|---------|
| Stage 1 | 1-2 hours | Steam API rate limits | ~20k games with metadata |
| Stage 2 | 1-2 days | OpenAI API + web scraping | ~350 analyzed games |
| Stage 3 | 30 minutes | Vector computation | Production database |

## Pipeline Outputs

After successful completion:

1. **steam_recommendations.db** - Main production database
2. **hierarchical_vectorizer.pkl** - TF-IDF model for runtime
3. **checkpoint_steam_analysis.json** - Intermediate analysis results
4. **ign_all_games.json** - Professional review data
5. **pipeline.log** - Complete execution log

## Migration from Go

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