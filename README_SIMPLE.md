# Simplified Steam Database Builder

A clean, focused library for building Steam game databases with insightful reviews.

## 🎯 Core Concept

Everything revolves around Steam `appid`:
```python
reviews = pull_insightful_reviews(appid)  # That's it!
```

## 📦 Installation

```bash
pip install -r requirements_simple.txt
export OPENAI_API_KEY="your-api-key"
```

## 🚀 Quick Start

### 1. Get Insightful Reviews for Any Game

```python
from steam_review_analyzer import pull_insightful_reviews

# Get reviews for Counter-Strike 2
reviews = pull_insightful_reviews(730)
print(reviews)  # Returns concatenated string of best reviews
```

### 2. Build Complete Database

```bash
# Build SQLite database with 100 games
python database_builder.py build 100

# Export to ChromaDB for vector search
python database_builder.py chromadb --load

# Or do everything at once
python database_builder.py all 100
```

### 3. Find Similar Games

```python
from chromadb_integration import SteamChromaDB

db = SteamChromaDB()
similar = db.find_similar_games(730, n_results=5)  # Find games like CS2
```

## 📁 File Structure

```
steam_review_analyzer.py   # Core library - gets insightful reviews
simple_db_builder.py       # Builds SQLite database
chromadb_integration.py    # Vector search with ChromaDB
database_builder.py        # Main entry point
```

## 🔧 How It Works

1. **Review Filtering** (automatic):
   - Fetches Steam reviews for appid
   - Filters spam (min 200 chars, 1hr playtime)
   - Sentiment analysis (VADER)
   - Removes toxic complaints
   - Ranks by gameplay keywords
   - Returns top 3 most insightful

2. **Database Building**:
   - SQLite first (metadata + reviews)
   - Export to ChromaDB (vector embeddings)
   - Enables similarity search

## 🎮 Examples

### Get reviews for any game:
```bash
python steam_review_analyzer.py 271590  # GTA V
```

### Build database for top 500 games:
```bash
python database_builder.py all 500
```

### Find games similar to Elden Ring:
```python
from chromadb_integration import find_games_like
similar = find_games_like(1245620)  # Elden Ring's appid
```

## 🗑️ Old Code

The complex pipeline code has been moved to `old_code_backup/` and is no longer needed.

## 💡 Key Features

✅ **Simple API** - Just `pull_insightful_reviews(appid)`
✅ **Smart Filtering** - Sentiment analysis, spam detection
✅ **SQLite First** - Traditional database, then vectors
✅ **ChromaDB Integration** - Modern vector search
✅ **No Abstractions** - Direct, focused functions

## 📝 License

Educational project for Steam game recommendations.