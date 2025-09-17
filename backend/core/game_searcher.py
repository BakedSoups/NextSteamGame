"""
Game search and similarity engine
"""
import sqlite3
import os
import numpy as np
import pickle
from typing import List, Dict, Any, Optional
from sklearn.metrics.pairwise import cosine_similarity

from backend.config import DATABASE_CONFIG, ML_CONFIG


class SQLiteGameSearcher:
    """Main game search and recommendation engine"""

    def __init__(self, recommendations_db=None, steam_api_db=None):
        self.recommendations_db = recommendations_db or str(DATABASE_CONFIG['recommendations_db'])
        self.steam_api_db = steam_api_db or str(DATABASE_CONFIG['steam_api_db'])
        self.vectorizer = None
        self.load_vectorizer()

    def load_vectorizer(self):
        """Load the TF-IDF vectorizer"""
        vectorizer_path = str(DATABASE_CONFIG['vectorizer_path'])
        try:
            with open(vectorizer_path, 'rb') as f:
                self.vectorizer = pickle.load(f)
            print("✅ Loaded TF-IDF vectorizer")
        except FileNotFoundError:
            print("Vectorizer not found. Run the converter first!")
            self.vectorizer = None

    def find_game_by_name(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Find games by name using SQLite full-text search"""
        if not os.path.exists(self.recommendations_db):
            print(f"Database not found: {self.recommendations_db}")
            return []

        conn = sqlite3.connect(self.recommendations_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            query_lower = query.lower().strip()

            # Try exact match first
            cursor.execute("""
            SELECT steam_appid, name, main_genre, sub_genre, sub_sub_genre
            FROM games
            WHERE LOWER(name) = ?
            LIMIT 1
            """, (query_lower,))

            exact_match = cursor.fetchone()
            if exact_match:
                result = self._enhance_game_with_steam_data([dict(exact_match)])[0]
                result['similarity'] = 1.0
                result['match_type'] = 'exact'
                return [result]

            # Fuzzy search with ranking
            search_query = """
            SELECT steam_appid, name, main_genre, sub_genre, sub_sub_genre,
                   CASE
                       WHEN LOWER(name) LIKE LOWER(? || '%') THEN 0.9
                       WHEN LOWER(name) LIKE LOWER('%' || ? || '%') THEN 0.7
                       ELSE 0.5
                   END as similarity_score
            FROM games
            WHERE LOWER(name) LIKE LOWER('%' || ? || '%')
            ORDER BY similarity_score DESC, name
            LIMIT ?
            """

            cursor.execute(search_query, [query_lower] * 3 + [limit])
            matches = cursor.fetchall()

            if matches:
                enhanced_matches = self._enhance_game_with_steam_data([dict(m) for m in matches])
                for i, match in enumerate(enhanced_matches):
                    match['similarity'] = matches[i]['similarity_score']
                    match['match_type'] = 'fuzzy'
                return enhanced_matches

            return []

        except Exception as e:
            print(f"Error searching games: {e}")
            return []
        finally:
            conn.close()

    def _enhance_game_with_steam_data(self, games: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enhance game data with Steam API database info"""
        if not os.path.exists(self.steam_api_db):
            # Return games with default values if Steam DB not available
            for game in games:
                game.update({
                    'header_image': '/static/logo.png',
                    'pricing': 'Unknown',
                    'steam_url': f"https://store.steampowered.com/app/{game['steam_appid']}/"
                })
            return games

        conn = sqlite3.connect(self.steam_api_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            for game in games:
                cursor.execute("""
                SELECT a.header_image, a.pricing, a.steam_url,
                       s.positive_reviews, s.negative_reviews
                FROM steam_api a
                LEFT JOIN steam_spy s ON a.steam_appid = s.steam_appid
                WHERE a.steam_appid = ?
                """, (game['steam_appid'],))

                steam_data = cursor.fetchone()
                if steam_data:
                    game.update({
                        'header_image': steam_data['header_image'] or '/static/logo.png',
                        'pricing': steam_data['pricing'] or 'Unknown',
                        'steam_url': steam_data['steam_url'] or f"https://store.steampowered.com/app/{game['steam_appid']}/",
                        'positive_reviews': steam_data['positive_reviews'] or 0,
                        'negative_reviews': steam_data['negative_reviews'] or 0
                    })
                else:
                    # Default values if not found in Steam database
                    game.update({
                        'header_image': '/static/logo.png',
                        'pricing': 'Unknown',
                        'steam_url': f"https://store.steampowered.com/app/{game['steam_appid']}/",
                        'positive_reviews': 0,
                        'negative_reviews': 0
                    })

            return games

        except Exception as e:
            print(f"Error enhancing with Steam data: {e}")
            return games
        finally:
            conn.close()

    def get_game_details(self, steam_appid: int) -> Optional[Dict[str, Any]]:
        """Get full game details including all tags and classifications"""
        conn = sqlite3.connect(self.recommendations_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Get main game info
            cursor.execute("""
            SELECT * FROM games WHERE steam_appid = ?
            """, (steam_appid,))

            game = cursor.fetchone()
            if not game:
                return None

            game_dict = dict(game)

            # Get all tags
            cursor.execute("""
            SELECT tag FROM steam_tags WHERE steam_appid = ? ORDER BY tag_order
            """, (steam_appid,))
            game_dict['steam_tags'] = [row[0] for row in cursor.fetchall()]

            cursor.execute("""
            SELECT tag FROM unique_tags WHERE steam_appid = ? ORDER BY tag_order
            """, (steam_appid,))
            game_dict['unique_tags'] = [row[0] for row in cursor.fetchall()]

            cursor.execute("""
            SELECT tag FROM subjective_tags WHERE steam_appid = ? ORDER BY tag_order
            """, (steam_appid,))
            game_dict['subjective_tags'] = [row[0] for row in cursor.fetchall()]

            cursor.execute("""
            SELECT tag, ratio FROM tag_ratios WHERE steam_appid = ?
            """, (steam_appid,))
            game_dict['tag_ratios'] = {row[0]: row[1] for row in cursor.fetchall()}

            # Enhance with Steam API data
            enhanced = self._enhance_game_with_steam_data([game_dict])[0]
            return enhanced

        except Exception as e:
            print(f"Error getting game details: {e}")
            return None
        finally:
            conn.close()

    def get_available_preferences(self, steam_appid: int) -> Dict[str, Any]:
        """Get available preference options for a game"""
        game = self.get_game_details(steam_appid)
        if not game:
            return {}

        return {
            'hierarchy': {
                'main_genre': game.get('main_genre', ''),
                'sub_genre': game.get('sub_genre', ''),
                'sub_sub_genre': game.get('sub_sub_genre', '')
            },
            'aesthetics': {
                'art_style': game.get('art_style', ''),
                'theme': game.get('theme', ''),
                'music_style': game.get('music_style', '')
            },
            'unique_tags': game.get('unique_tags', []),
            'subjective_tags': game.get('subjective_tags', []),
            'steam_tags': game.get('steam_tags', []),
            'tag_ratios': game.get('tag_ratios', {})
        }