"""
Similarity calculation engine for game recommendations
"""
import sqlite3
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from sklearn.metrics.pairwise import cosine_similarity

from backend.config import ML_CONFIG
from .score_calculator import ScoreCalculator, SimilarityScores, WeightPresets


class SimilarityEngine:
    """Handles similarity calculations between games"""

    def __init__(self, db_path: str, score_calculator: Optional[ScoreCalculator] = None):
        self.db_path = db_path
        self.score_calculator = score_calculator or ScoreCalculator(WeightPresets.balanced())

    def find_similar_games(self, target_appid: int, user_preferences: Optional[Dict] = None,
                          limit: int = 10) -> List[Dict[str, Any]]:
        """Find similar games using hierarchical search + vector similarity"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Get target game info
            cursor.execute("""
            SELECT name, main_genre, sub_genre, sub_sub_genre, art_style, theme, music_style
            FROM games WHERE steam_appid = ?
            """, (target_appid,))

            target_game = cursor.fetchone()
            if not target_game:
                return []

            target_dict = dict(target_game)
            main_genre = target_dict['main_genre']
            sub_genre = target_dict['sub_genre']
            sub_sub_genre = target_dict['sub_sub_genre']

            print(f"Finding games similar to: {target_dict['name']}")
            print(f"Hierarchy: {main_genre} → {sub_genre} → {sub_sub_genre}")

            # Check if soulslike
            is_soulslike = self._is_soulslike_game_sql(target_appid, cursor)
            if is_soulslike:
                print("🗡️ Detected soulslike game - prioritizing soulslike mechanics")

            # Get candidates using SQL hierarchy search
            candidates = self._get_hierarchy_candidates(
                target_appid, main_genre, sub_genre, sub_sub_genre, is_soulslike, cursor
            )

            if not candidates:
                return []

            # Calculate similarities using vectors or tags
            similarities = self._calculate_similarities(target_appid, candidates, user_preferences, cursor)

            # Enhance with game details
            enhanced_games = []
            for sim in similarities[:limit]:
                game_details = self._get_enhanced_game_details(sim['steam_appid'], cursor)
                if game_details:
                    enhanced_games.append({
                        'appid': str(sim['steam_appid']),
                        'game': game_details,
                        'similarity': sim['similarity'],
                        'base_similarity': sim.get('base_similarity', sim['similarity']),
                        'hierarchy_bonus': sim.get('hierarchy_bonus', 0),
                        'preference_bonus': sim.get('preference_bonus', 0),
                        'match_type': sim['match_type']
                    })

            return enhanced_games

        except Exception as e:
            print(f"Error finding similar games: {e}")
            return []
        finally:
            conn.close()

    def _is_soulslike_game_sql(self, steam_appid: int, cursor) -> bool:
        """Check if game is soulslike using SQL queries"""
        # Check name
        cursor.execute("SELECT name FROM games WHERE steam_appid = ?", (steam_appid,))
        name = cursor.fetchone()
        if name and any(indicator in name[0].lower() for indicator in ['souls', 'elden ring', 'bloodborne']):
            return True

        # Check tags
        cursor.execute("""
        SELECT COUNT(*) FROM unique_tags
        WHERE steam_appid = ? AND (
            LOWER(tag) LIKE '%souls%' OR
            LOWER(tag) LIKE '%soulslike%' OR
            LOWER(tag) LIKE '%stamina%' OR
            LOWER(tag) LIKE '%challenging-but-fair%'
        )
        """, (steam_appid,))

        if cursor.fetchone()[0] > 0:
            return True

        # Check sub-sub genre
        cursor.execute("""
        SELECT sub_sub_genre FROM games
        WHERE steam_appid = ? AND LOWER(sub_sub_genre) LIKE '%souls%'
        """, (steam_appid,))

        return cursor.fetchone() is not None

    def _get_hierarchy_candidates(self, target_appid: int, main_genre: str, sub_genre: str,
                                sub_sub_genre: str, is_soulslike: bool, cursor) -> List[Tuple[int, str, float]]:
        """Get candidate games using hierarchical genre search"""
        candidates = []
        candidates_limit = ML_CONFIG['similarity_candidates_limit']

        # Soulslike matches (if applicable)
        if is_soulslike:
            cursor.execute("""
            SELECT DISTINCT g.steam_appid, 'soulslike' as match_type, 0.5 as hierarchy_bonus
            FROM games g
            LEFT JOIN unique_tags ut ON g.steam_appid = ut.steam_appid
            WHERE g.steam_appid != ? AND (
                LOWER(g.name) LIKE '%souls%' OR
                LOWER(g.sub_sub_genre) LIKE '%souls%' OR
                LOWER(ut.tag) LIKE '%souls%' OR
                LOWER(ut.tag) LIKE '%soulslike%'
            )
            LIMIT 20
            """, (target_appid,))

            candidates.extend([(row[0], row[1], row[2]) for row in cursor.fetchall()])

        # Exact hierarchy matches
        cursor.execute("""
        SELECT steam_appid, 'exact' as match_type, 0.4 as hierarchy_bonus
        FROM games
        WHERE steam_appid != ? AND main_genre = ? AND sub_genre = ? AND sub_sub_genre = ?
        LIMIT 15
        """, (target_appid, main_genre, sub_genre, sub_sub_genre))

        candidates.extend([(row[0], row[1], row[2]) for row in cursor.fetchall()
                          if row[0] not in [c[0] for c in candidates]])

        # Sub-genre matches
        cursor.execute("""
        SELECT steam_appid, 'sub' as match_type, 0.25 as hierarchy_bonus
        FROM games
        WHERE steam_appid != ? AND main_genre = ? AND sub_genre = ? AND sub_sub_genre != ?
        LIMIT 15
        """, (target_appid, main_genre, sub_genre, sub_sub_genre))

        candidates.extend([(row[0], row[1], row[2]) for row in cursor.fetchall()
                          if row[0] not in [c[0] for c in candidates]])

        # Main genre matches
        cursor.execute("""
        SELECT steam_appid, 'main' as match_type, 0.15 as hierarchy_bonus
        FROM games
        WHERE steam_appid != ? AND main_genre = ? AND sub_genre != ?
        LIMIT 10
        """, (target_appid, main_genre, sub_genre))

        candidates.extend([(row[0], row[1], row[2]) for row in cursor.fetchall()
                          if row[0] not in [c[0] for c in candidates]])

        print(f"Found {len(candidates)} candidates")
        return candidates[:candidates_limit]

    def _calculate_similarities(self, target_appid: int, candidates: List[Tuple],
                              user_preferences: Optional[Dict], cursor) -> List[Dict[str, Any]]:
        """Calculate similarities using vectors or tags as fallback"""
        try:
            # Try vector similarity first
            return self._calculate_vector_similarities(target_appid, candidates, user_preferences, cursor)
        except Exception as e:
            print(f"Vector similarity failed: {e}, falling back to tag similarity")
            return self._calculate_tag_similarities(target_appid, candidates, user_preferences, cursor)

    def _calculate_vector_similarities(self, target_appid: int, candidates: List[Tuple],
                                     user_preferences: Optional[Dict], cursor) -> List[Dict[str, Any]]:
        """Calculate similarities using stored vectors"""
        # Get target vector
        cursor.execute("SELECT vector_data FROM game_vectors WHERE steam_appid = ?", (target_appid,))
        target_row = cursor.fetchone()
        if not target_row:
            raise ValueError("No vector data found for target game")

        target_vector = np.frombuffer(target_row[0], dtype=np.float64).reshape(1, -1)

        similarities = []
        for candidate_appid, match_type, hierarchy_bonus in candidates:
            cursor.execute("SELECT vector_data FROM game_vectors WHERE steam_appid = ?", (candidate_appid,))
            candidate_row = cursor.fetchone()

            if candidate_row:
                candidate_vector = np.frombuffer(candidate_row[0], dtype=np.float64).reshape(1, -1)
                base_sim = cosine_similarity(target_vector, candidate_vector)[0][0]

                # Apply user preference bonus
                preference_bonus = self._calculate_preference_bonus(candidate_appid, user_preferences, cursor)

                final_score = min(1.0, base_sim + hierarchy_bonus + preference_bonus)

                similarities.append({
                    'steam_appid': candidate_appid,
                    'similarity': final_score,
                    'base_similarity': base_sim,
                    'hierarchy_bonus': hierarchy_bonus,
                    'preference_bonus': preference_bonus,
                    'match_type': match_type
                })

        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        return similarities

    def _calculate_tag_similarities(self, target_appid: int, candidates: List[Tuple],
                                  user_preferences: Optional[Dict], cursor) -> List[Dict[str, Any]]:
        """Fallback tag-based similarity calculation using Jaccard similarity"""
        # Get target game tags
        cursor.execute("""
        SELECT tag FROM unique_tags WHERE steam_appid = ?
        UNION
        SELECT tag FROM subjective_tags WHERE steam_appid = ?
        """, (target_appid, target_appid))

        target_tags = set(row[0] for row in cursor.fetchall())

        similarities = []
        for candidate_appid, match_type, hierarchy_bonus in candidates:
            # Get candidate tags
            cursor.execute("""
            SELECT tag FROM unique_tags WHERE steam_appid = ?
            UNION
            SELECT tag FROM subjective_tags WHERE steam_appid = ?
            """, (candidate_appid, candidate_appid))

            candidate_tags = set(row[0] for row in cursor.fetchall())

            # Jaccard similarity
            if len(target_tags) > 0 and len(candidate_tags) > 0:
                intersection = len(target_tags & candidate_tags)
                union = len(target_tags | candidate_tags)
                base_sim = intersection / union if union > 0 else 0
            else:
                base_sim = 0

            # Apply preference bonus
            preference_bonus = self._calculate_preference_bonus(candidate_appid, user_preferences, cursor)

            final_score = min(1.0, base_sim + hierarchy_bonus + preference_bonus)

            similarities.append({
                'steam_appid': candidate_appid,
                'similarity': final_score,
                'base_similarity': base_sim,
                'hierarchy_bonus': hierarchy_bonus,
                'preference_bonus': preference_bonus,
                'match_type': match_type
            })

        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        return similarities

    def _calculate_preference_bonus(self, candidate_appid: int, user_preferences: Optional[Dict], cursor) -> float:
        """Calculate preference bonus based on user selections"""
        if not user_preferences:
            return 0

        bonus = 0

        # Aesthetic preferences
        aesthetics = user_preferences.get('aesthetics', {})
        if aesthetics:
            cursor.execute("""
            SELECT art_style, theme, music_style FROM games WHERE steam_appid = ?
            """, (candidate_appid,))

            game_aesthetics = cursor.fetchone()
            if game_aesthetics:
                for pref_type, pref_value in aesthetics.items():
                    if pref_value and game_aesthetics[pref_type] == pref_value:
                        bonus += 0.1

        # Tag preferences
        preferred_tags = user_preferences.get('preferred_tags', [])
        if preferred_tags:
            placeholders = ','.join(['?' for _ in preferred_tags])
            cursor.execute(f"""
            SELECT COUNT(*) FROM (
                SELECT tag FROM unique_tags WHERE steam_appid = ? AND tag IN ({placeholders})
                UNION
                SELECT tag FROM subjective_tags WHERE steam_appid = ? AND tag IN ({placeholders})
            )
            """, [candidate_appid] + preferred_tags + [candidate_appid] + preferred_tags)

            matching_count = cursor.fetchone()[0]
            if matching_count > 0:
                bonus += (matching_count / len(preferred_tags)) * 0.15

        # Steam tag preferences with popular combos
        preferred_steam_tags = user_preferences.get('preferred_steam_tags', [])
        if preferred_steam_tags:
            placeholders = ','.join(['?' for _ in preferred_steam_tags])
            cursor.execute(f"""
            SELECT COUNT(*) FROM steam_tags
            WHERE steam_appid = ? AND tag IN ({placeholders})
            """, [candidate_appid] + preferred_steam_tags)

            matching_steam_tags = cursor.fetchone()[0]
            if matching_steam_tags > 0:
                steam_tag_bonus = (matching_steam_tags / len(preferred_steam_tags)) * 0.25
                bonus += steam_tag_bonus

                # Popular tag combinations bonus
                popular_combos = {
                    ('roguelike', 'procedural generation'): 0.1,
                    ('souls-like', 'difficult'): 0.1,
                    ('metroidvania', 'exploration'): 0.1,
                    ('platformer', 'pixel graphics'): 0.05,
                    ('puzzle', 'relaxing'): 0.05
                }

                selected_tags_lower = [tag.lower() for tag in preferred_steam_tags]
                for combo, combo_bonus in popular_combos.items():
                    if all(tag in selected_tags_lower for tag in combo):
                        # Check if candidate has this combo too
                        cursor.execute(f"""
                        SELECT COUNT(*) FROM steam_tags
                        WHERE steam_appid = ? AND LOWER(tag) IN ({','.join(['?' for _ in combo])})
                        """, [candidate_appid] + list(combo))

                        if cursor.fetchone()[0] == len(combo):
                            bonus += combo_bonus

        return bonus

    def _get_enhanced_game_details(self, steam_appid: int, cursor) -> Optional[Dict[str, Any]]:
        """Get enhanced game details for results"""
        cursor.execute("SELECT * FROM games WHERE steam_appid = ?", (steam_appid,))
        game = cursor.fetchone()

        if not game:
            return None

        return dict(game)