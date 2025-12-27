# DB Creation - Organized Vector Analysis

Clean, organized system for Steam game vector analysis.

## 📁 Structure

```
db_creation/
├── core/
│   └── steam_review_analyzer.py    # Core review extraction
├── analyzers/
│   ├── vector_analyzer.py          # Main analysis engine
│   └── output_formatter.py         # Pretty printing
├── config/
│   └── review_config.json          # All configuration
├── tests/
│   └── test_persona.py             # Test Persona 3 Reload
└── README.md
```

## 🚀 Usage

### Stage 1: Test Analysis
```bash
cd db_creation/tests
python test_persona.py 15    # Analyze with 15 reviews
python test_persona.py       # Default 10 reviews
```

### Stage 2: Convert to Databases
```bash
cd db_creation
python stage2_db_converter.py           # Convert Persona 3 to SQLite + ChromaDB
python stage2_db_converter.py 730       # Convert CS2
```

### Query Databases
```bash
cd db_creation
python query_database.py info 1687950                    # Get game info
python query_database.py similar 1687950 music           # Find similar music
python query_database.py search gameplay "turn-based"    # Search gameplay
python query_database.py list                            # List all games
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