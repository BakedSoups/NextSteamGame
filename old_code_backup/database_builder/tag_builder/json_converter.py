import json
import sqlite3
import os
from datetime import datetime
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

class HierarchicalDatabaseConverter:
    def __init__(self, json_file_path, db_file_path):
        self.json_file_path = json_file_path
        self.db_file_path = db_file_path
        self.games_data = {}
        
    def load_json_data(self):
        """Load the hierarchical JSON data"""
        print(f"Loading JSON data from {self.json_file_path}...")
        
        with open(self.json_file_path, 'r', encoding='utf-8') as f:
            self.games_data = json.load(f)
        
        print(f"✅ Loaded {len(self.games_data)} games")
        return True
    
    def create_database_schema(self):
        """Create the SQLite database schema"""
        print(f"Creating database schema in {self.db_file_path}...")
        
        # Remove existing database if it exists
        if os.path.exists(self.db_file_path):
            os.remove(self.db_file_path)
            print(f"🗑️ Removed existing database")
        
        conn = sqlite3.connect(self.db_file_path)
        cursor = conn.cursor()
        
        # Main games table with hierarchical structure
        cursor.execute("""
        CREATE TABLE games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            steam_appid INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL,
            steam_description TEXT,
            
            -- Hierarchical genre classification
            main_genre TEXT NOT NULL,
            sub_genre TEXT NOT NULL,
            sub_sub_genre TEXT NOT NULL,
            
            -- Aesthetic classifications
            art_style TEXT,
            theme TEXT,
            music_style TEXT,
            
            -- Processing metadata
            processing_date TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Search optimization
            search_text TEXT, -- For full-text search
            
            -- Indexes will be created separately
            FOREIGN KEY (steam_appid) REFERENCES steam_tags(steam_appid)
        );
        """)
        
        # Steam tags table (original Steam tags)
        cursor.execute("""
        CREATE TABLE steam_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            steam_appid INTEGER NOT NULL,
            tag TEXT NOT NULL,
            tag_order INTEGER, -- Order in the original tags list
            FOREIGN KEY (steam_appid) REFERENCES games(steam_appid)
        );
        """)
        
        # Unique gameplay tags
        cursor.execute("""
        CREATE TABLE unique_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            steam_appid INTEGER NOT NULL,
            tag TEXT NOT NULL,
            tag_order INTEGER,
            FOREIGN KEY (steam_appid) REFERENCES games(steam_appid)
        );
        """)
        
        # Subjective quality tags
        cursor.execute("""
        CREATE TABLE subjective_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            steam_appid INTEGER NOT NULL,
            tag TEXT NOT NULL,
            tag_order INTEGER,
            FOREIGN KEY (steam_appid) REFERENCES games(steam_appid)
        );
        """)
        
        # Tag ratios (gameplay element percentages)
        cursor.execute("""
        CREATE TABLE tag_ratios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            steam_appid INTEGER NOT NULL,
            tag TEXT NOT NULL,
            ratio INTEGER NOT NULL, -- Percentage 0-100
            FOREIGN KEY (steam_appid) REFERENCES games(steam_appid)
        );
        """)
        
        # Reviews data (condensed from original reviews)
        cursor.execute("""
        CREATE TABLE game_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            steam_appid INTEGER NOT NULL,
            review_type TEXT NOT NULL, -- 'general', 'art_style', 'theme', 'music', 'quality'
            review_text TEXT,
            voted_up BOOLEAN,
            playtime_hours REAL,
            review_date TEXT,
            keyword_score INTEGER, -- How many relevant keywords found
            FOREIGN KEY (steam_appid) REFERENCES games(steam_appid)
        );
        """)
        
        # Vector embeddings for similarity search
        cursor.execute("""
        CREATE TABLE game_vectors (
            steam_appid INTEGER PRIMARY KEY,
            vector_data BLOB, -- Serialized numpy array
            vector_dimension INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (steam_appid) REFERENCES games(steam_appid)
        );
        """)
        
        # Create indexes for fast querying
        print("Creating indexes...")
        
        # Hierarchy indexes
        cursor.execute("CREATE INDEX idx_games_main_genre ON games(main_genre);")
        cursor.execute("CREATE INDEX idx_games_sub_genre ON games(sub_genre);")
        cursor.execute("CREATE INDEX idx_games_sub_sub_genre ON games(sub_sub_genre);")
        cursor.execute("CREATE INDEX idx_games_hierarchy ON games(main_genre, sub_genre, sub_sub_genre);")
        
        # Aesthetic indexes
        cursor.execute("CREATE INDEX idx_games_art_style ON games(art_style);")
        cursor.execute("CREATE INDEX idx_games_theme ON games(theme);")
        cursor.execute("CREATE INDEX idx_games_music_style ON games(music_style);")
        
        # Tag indexes
        cursor.execute("CREATE INDEX idx_steam_tags_appid ON steam_tags(steam_appid);")
        cursor.execute("CREATE INDEX idx_steam_tags_tag ON steam_tags(tag);")
        cursor.execute("CREATE INDEX idx_unique_tags_appid ON unique_tags(steam_appid);")
        cursor.execute("CREATE INDEX idx_unique_tags_tag ON unique_tags(tag);")
        cursor.execute("CREATE INDEX idx_subjective_tags_appid ON subjective_tags(steam_appid);")
        cursor.execute("CREATE INDEX idx_subjective_tags_tag ON subjective_tags(tag);")
        cursor.execute("CREATE INDEX idx_tag_ratios_appid ON tag_ratios(steam_appid);")
        
        # Review indexes
        cursor.execute("CREATE INDEX idx_reviews_appid ON game_reviews(steam_appid);")
        cursor.execute("CREATE INDEX idx_reviews_type ON game_reviews(review_type);")
        
        # Search index
        cursor.execute("CREATE INDEX idx_games_search ON games(search_text);")
        cursor.execute("CREATE INDEX idx_games_name ON games(name);")
        
        # Full-text search (if SQLite supports it)
        try:
            cursor.execute("CREATE VIRTUAL TABLE games_fts USING fts5(name, search_text, content='games', content_rowid='id');")
            print("✅ Created FTS5 virtual table for full-text search")
        except sqlite3.OperationalError:
            print("⚠️ FTS5 not available, using regular indexes")
        
        conn.commit()
        conn.close()
        print("✅ Database schema created successfully")
    
    def insert_game_data(self):
        """Insert all game data into the database"""
        print("Inserting game data...")
        
        conn = sqlite3.connect(self.db_file_path)
        cursor = conn.cursor()
        
        batch_size = 1000
        game_count = 0
        
        # Prepare batch inserts
        games_batch = []
        steam_tags_batch = []
        unique_tags_batch = []
        subjective_tags_batch = []
        tag_ratios_batch = []
        reviews_batch = []
        
        for appid, game_data in self.games_data.items():
            steam_appid = int(appid)
            
            # Prepare search text for full-text search
            search_components = [
                game_data.get('name', ''),
                game_data.get('main_genre', ''),
                game_data.get('sub_genre', ''),
                game_data.get('sub_sub_genre', ''),
                ' '.join(game_data.get('unique_tags', [])),
                ' '.join(game_data.get('subjective_tags', []))
            ]
            search_text = ' '.join(filter(None, search_components)).lower()
            
            # Main game record
            games_batch.append((
                steam_appid,
                game_data.get('name', ''),
                game_data.get('steam_description', ''),
                game_data.get('main_genre', 'unknown'),
                game_data.get('sub_genre', 'unknown'),
                game_data.get('sub_sub_genre', 'unknown'),
                game_data.get('art_style', 'unknown'),
                game_data.get('theme', 'unknown'),
                game_data.get('music_style', 'unknown'),
                game_data.get('processing_date', ''),
                game_data.get('status', ''),
                search_text
            ))
            
            # Steam tags
            for i, tag in enumerate(game_data.get('steam_tags', [])):
                steam_tags_batch.append((steam_appid, tag, i))
            
            # Unique tags
            for i, tag in enumerate(game_data.get('unique_tags', [])):
                unique_tags_batch.append((steam_appid, tag, i))
            
            # Subjective tags
            for i, tag in enumerate(game_data.get('subjective_tags', [])):
                subjective_tags_batch.append((steam_appid, tag, i))
            
            # Tag ratios
            for tag, ratio in game_data.get('tag_ratios', {}).items():
                tag_ratios_batch.append((steam_appid, tag, int(ratio)))
            
            # Reviews (condensed)
            for review_type in ['general', 'art_style', 'theme', 'music', 'quality']:
                reviews_key = f"{review_type}_reviews" if review_type != 'general' else 'reviews'
                if reviews_key in game_data:
                    for review in game_data[reviews_key][:3]:  # Limit to top 3 reviews per type
                        reviews_batch.append((
                            steam_appid,
                            review_type,
                            review.get('review', ''),
                            review.get('voted_up', True),
                            review.get('playtime_hours', 0),
                            review.get('date', ''),
                            review.get('keyword_score', 0)
                        ))
            
            game_count += 1
            
            # Batch insert when we hit the batch size
            if game_count % batch_size == 0:
                self._execute_batch_inserts(cursor, games_batch, steam_tags_batch, 
                                          unique_tags_batch, subjective_tags_batch, 
                                          tag_ratios_batch, reviews_batch)
                
                # Clear batches
                games_batch = []
                steam_tags_batch = []
                unique_tags_batch = []
                subjective_tags_batch = []
                tag_ratios_batch = []
                reviews_batch = []
                
                print(f"   Processed {game_count}/{len(self.games_data)} games...")
        
        # Insert remaining data
        if games_batch:
            self._execute_batch_inserts(cursor, games_batch, steam_tags_batch, 
                                      unique_tags_batch, subjective_tags_batch, 
                                      tag_ratios_batch, reviews_batch)
        
        conn.commit()
        conn.close()
        print(f"✅ Inserted {game_count} games successfully")
    
    def _execute_batch_inserts(self, cursor, games_batch, steam_tags_batch, 
                              unique_tags_batch, subjective_tags_batch, 
                              tag_ratios_batch, reviews_batch):
        """Execute batch inserts for all tables"""
        
        # Insert games
        cursor.executemany("""
        INSERT OR REPLACE INTO games 
        (steam_appid, name, steam_description, main_genre, sub_genre, sub_sub_genre,
         art_style, theme, music_style, processing_date, status, search_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, games_batch)
        
        # Insert steam tags
        if steam_tags_batch:
            cursor.executemany("""
            INSERT INTO steam_tags (steam_appid, tag, tag_order)
            VALUES (?, ?, ?)
            """, steam_tags_batch)
        
        # Insert unique tags
        if unique_tags_batch:
            cursor.executemany("""
            INSERT INTO unique_tags (steam_appid, tag, tag_order)
            VALUES (?, ?, ?)
            """, unique_tags_batch)
        
        if subjective_tags_batch:
            cursor.executemany("""
            INSERT INTO subjective_tags (steam_appid, tag, tag_order)
            VALUES (?, ?, ?)
            """, subjective_tags_batch)
        
        if tag_ratios_batch:
            cursor.executemany("""
            INSERT INTO tag_ratios (steam_appid, tag, ratio)
            VALUES (?, ?, ?)
            """, tag_ratios_batch)
        
        if reviews_batch:
            cursor.executemany("""
            INSERT INTO game_reviews 
            (steam_appid, review_type, review_text, voted_up, playtime_hours, review_date, keyword_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, reviews_batch)
    
    def build_and_store_vectors(self):
        """Build TF-IDF vectors and store them in the database"""
        print("Building and storing similarity vectors...")
        
        game_tag_texts = []
        game_appids = []
        
        for appid, game in self.games_data.items():
            all_tags = []
            all_tags.extend(game.get('unique_tags', []))
            all_tags.extend(game.get('subjective_tags', []))
            all_tags.append(game.get('theme', ''))
            
            tag_text = ' '.join(filter(None, all_tags))
            game_tag_texts.append(tag_text)
            game_appids.append(int(appid))
        
        # Build TF-IDF vectors
        vectorizer = TfidfVectorizer(
            lowercase=True,
            token_pattern=r'[a-zA-Z-]+',
            ngram_range=(1, 2),
            max_features=1000
        )
        
        vectors = vectorizer.fit_transform(game_tag_texts)
        
        # Store vectors in database
        conn = sqlite3.connect(self.db_file_path)
        cursor = conn.cursor()
        
        vector_batch = []
        for i, appid in enumerate(game_appids):
            vector_dense = vectors[i].toarray()[0]
            vector_blob = vector_dense.tobytes()
            
            vector_batch.append((
                appid,
                vector_blob,
                len(vector_dense)
            ))
        
        cursor.executemany("""
        INSERT INTO game_vectors (steam_appid, vector_data, vector_dimension)
        VALUES (?, ?, ?)
        """, vector_batch)
        
        conn.commit()
        conn.close()
        
        # Save vectorizer for later use
        import pickle
        with open('hierarchical_vectorizer.pkl', 'wb') as f:
            pickle.dump(vectorizer, f)
        
        print(f"✅ Stored {len(vector_batch)} vectors in database")
        print("💾 Saved vectorizer to hierarchical_vectorizer.pkl")
    
    def create_summary_views(self):
        """Create useful views for quick queries"""
        print("Creating summary views...")
        
        conn = sqlite3.connect(self.db_file_path)
        cursor = conn.cursor()
        
        # Hierarchy summary view
        cursor.execute("""
        CREATE VIEW hierarchy_summary AS
        SELECT 
            main_genre,
            sub_genre,
            sub_sub_genre,
            COUNT(*) as game_count,
            GROUP_CONCAT(name, ', ') as sample_games
        FROM games
        GROUP BY main_genre, sub_genre, sub_sub_genre
        ORDER BY game_count DESC;
        """)
        
        # Popular tags view
        cursor.execute("""
        CREATE VIEW popular_unique_tags AS
        SELECT 
            tag,
            COUNT(*) as usage_count,
            GROUP_CONCAT(DISTINCT g.name, ', ') as sample_games
        FROM unique_tags ut
        JOIN games g ON ut.steam_appid = g.steam_appid
        GROUP BY tag
        ORDER BY usage_count DESC;
        """)
        
        # Aesthetic combinations view
        cursor.execute("""
        CREATE VIEW aesthetic_combinations AS
        SELECT 
            art_style,
            theme,
            music_style,
            COUNT(*) as game_count,
            GROUP_CONCAT(name, ', ') as sample_games
        FROM games
        WHERE art_style != 'unknown' AND theme != 'unknown' AND music_style != 'unknown'
        GROUP BY art_style, theme, music_style
        ORDER BY game_count DESC;
        """)
        
        conn.commit()
        conn.close()
        print("✅ Created summary views")
    
    def print_database_stats(self):
        """Print statistics about the created database"""
        print("\n" + "="*50)
        print("DATABASE STATISTICS")
        print("="*50)
        
        conn = sqlite3.connect(self.db_file_path)
        cursor = conn.cursor()
        
        # Basic counts
        cursor.execute("SELECT COUNT(*) FROM games")
        game_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM steam_tags")
        steam_tags_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM unique_tags")
        unique_tags_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM subjective_tags")
        subjective_tags_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM game_vectors")
        vectors_count = cursor.fetchone()[0]
        
        
        # Top hierarchies
        print(f"\n🎮 TOP HIERARCHIES:")
        cursor.execute("""
        SELECT main_genre, sub_genre, sub_sub_genre, COUNT(*) as count
        FROM games 
        GROUP BY main_genre, sub_genre, sub_sub_genre
        ORDER BY count DESC
        LIMIT 10
        """)
        
        for row in cursor.fetchall():
            print(f"   {row[3]:3d} games: {row[0]} → {row[1]} → {row[2]}")
        
        # Database size
        cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        db_size = cursor.fetchone()[0]
        
        conn.close()
        print("="*50)

def convert_json_to_sqlite(json_file="steam_games_with_hierarchical_tags.json", 
                          db_file="steam_recommendations.db"):
    """Main conversion function"""
    print("🚀 Starting JSON to SQLite conversion...")
    print(f"Input: {json_file}")
    print(f"Output: {db_file}")
    
    converter = HierarchicalDatabaseConverter(json_file, db_file)
    
    try:
        # Step 1: Load JSON data
        converter.load_json_data()
        
        # Step 2: Create database schema
        converter.create_database_schema()
        
        # Step 3: Insert game data
        converter.insert_game_data()
        
        # Step 4: Build and store vectors
        converter.build_and_store_vectors()
        
        # Step 5: Create summary views
        converter.create_summary_views()
        
        # Step 6: Print statistics
        converter.print_database_stats()
    
    except Exception as e:
        print(f"❌ Error during conversion: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Run the conversion
    convert_json_to_sqlite()
    
    # Optional: Test the database
    print("\n🧪 Testing database queries...")
    
    conn = sqlite3.connect("steam_recommendations.db")
    cursor = conn.cursor()
    
    # Test basic query
    cursor.execute("SELECT name, main_genre, sub_genre FROM games LIMIT 5")
    print("\nSample games:")
    for row in cursor.fetchall():
        print(f"  {row[0]} ({row[1]} → {row[2]})")
    
    # Test hierarchy search
    cursor.execute("""
    SELECT COUNT(*) FROM games 
    WHERE main_genre = 'jrpg' AND sub_genre = 'turn-based'
    """)
    jrpg_count = cursor.fetchone()[0]
    print(f"\nTurn-based JRPGs: {jrpg_count}")
    
    conn.close()
    print("Database test completed!")