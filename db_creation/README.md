# DB Creation - Organized Vector Analysis

Clean, organized system for Steam game vector analysis.

## 📁 Structure

```
db_creation/
├── analysis/
│   ├── core/
│   │   └── steam_review_analyzer.py    # Review extraction + filtering
│   ├── analyzers/
│   │   ├── vector_analyzer.py          # AI analysis engine
│   │   └── output_formatter.py         # Pretty printing
│   └── tests/
│       └── test_persona.py             # Analysis-only test entrypoint
├── database/
│   ├── main.py                         # Main entrypoint for building both databases
│   ├── stage2_db_converter.py          # Persist analysis into SQLite + ChromaDB
│   └── query_database.py               # Query stored databases
└── README.md
```

## 🚀 Usage

### Stage 1: Test Analysis
```bash
cd db_creation
python -m db_creation.analysis.tests.test_persona 15    # Analyze with 15 reviews
python -m db_creation.analysis.tests.test_persona       # Default 10 reviews
```

### Stage 2: Convert to Databases
```bash
cd Steam_Reccomender
python -m db_creation.database.main                     # Build SQLite + ChromaDB for Persona 3
python -m db_creation.database.main 730                 # Build SQLite + ChromaDB for CS2
python -m db_creation.database.main 730 440 --num-reviews 15
```

Or run it directly from the database folder:
```bash
cd db_creation/database
python main.py 730
```

### Query Databases
```bash
cd Steam_Reccomender
python -m db_creation.database.query_database info 1687950                    # Get game info
python -m db_creation.database.query_database similar 1687950 music           # Find similar music
python -m db_creation.database.query_database search gameplay "turn-based"    # Search gameplay
python -m db_creation.database.query_database list                            # List all games
```

## 🎯 Output Format

### Full Analysis
- ✨ **Consensus** - What players agree on
- 🎯 **Gameplay Vector** - combat:40 exploration:30 social:20
- 🎵 **Music Vector (Hierarchical)** - Jazz:60 → acid_jazz:30 bebop:30
- ✨ **Vibes Vector** - stylish:30 dark:25 nostalgic:25

### Hierarchical Music Example
```
🎼 JAZZ: 60%
   └─ acid_jazz: 30%
   └─ bebop: 20%
   └─ smooth_jazz: 10%

🎼 ROCK: 30%
   └─ hard_rock: 15%
   └─ punk: 10%
   └─ alternative: 5%
```

## ⚙️ Configuration

Edit `config/review_config.json` to:
- Add keywords for insightful review detection
- Modify AI prompts for consensus/vectors
- Adjust quality thresholds
- Configure API settings

## 📊 Features

### Stage 1: Vector Analysis
- **Hierarchical Music Genres** - Sub-genres within main genres
- **Percentage Validation** - Ensures totals add up correctly
- **Clean Imports** - Organized module structure
- **Error Handling** - Graceful failure with helpful messages

### Stage 2: Database Storage
- **SQLite Database** - Structured metadata and vector storage
- **ChromaDB Integration** - Vector similarity search
- **Hierarchical Storage** - Maintains music genre hierarchy
- **Query Interface** - Search and similarity functions

## 🗄️ Database Structure

### SQLite Tables
- `games` - Basic game metadata and consensus
- `gameplay_vectors` - Gameplay elements and percentages
- `music_vectors` - Hierarchical music genres with parent relationships
- `vibes_vectors` - Atmosphere and mood vectors

### ChromaDB Collections
- `gameplay_vectors` - Semantic search for gameplay
- `music_vectors` - Semantic search for music styles
- `vibes_vectors` - Semantic search for game atmosphere
