"""
Vector Analysis Module for Steam Games
Provides comprehensive analysis including gameplay, music, and vibes vectors
"""

import os
import json
from typing import Dict, List, Optional
from pathlib import Path

# Import core components
import sys
sys.path.append(str(Path(__file__).parent.parent / 'core'))

from steam_review_analyzer import SteamReviewAnalyzer
from openai import OpenAI


class VectorAnalyzer:
    """Comprehensive game vector analysis"""

    def __init__(self, config_path: Optional[str] = None):
        # Set default config path
        if config_path is None:
            config_path = str(Path(__file__).parent.parent / 'config' / 'review_config.json')

        self.config_path = config_path
        self.config = self._load_config()
        self.analyzer = SteamReviewAnalyzer(config_path)

    def _load_config(self) -> Dict:
        """Load configuration from JSON file"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {}

    def analyze_game_vectors(self, appid: int, num_reviews: int = 10) -> Dict:
        """
        Get all vectors for a game: consensus, gameplay, music, and vibes

        Args:
            appid: Steam app ID
            num_reviews: Number of reviews to analyze

        Returns:
            Dictionary with all analysis results
        """

        # Check for OpenAI API key
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError("OPENAI_API_KEY environment variable not set")

        # Get reviews
        fetch_count = min(num_reviews * 20, 100)
        reviews_text = self.analyzer.pull_insightful_reviews(
            appid, max_reviews=num_reviews, fetch_count=fetch_count
        )

        if not reviews_text:
            return {
                "appid": appid,
                "error": "No reviews found"
            }

        # Initialize result
        result = {
            "appid": appid,
            "num_reviews_analyzed": num_reviews
        }

        # Get OpenAI client
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        prompts = self.config.get("consensus_prompts", {})
        api_settings = self.config.get("api_settings", {})

        try:
            # 1. CONSENSUS
            consensus = self._get_consensus(client, prompts, api_settings, reviews_text, num_reviews)
            result["consensus"] = consensus

            # 2. GAMEPLAY VECTOR
            gameplay_vector = self._get_gameplay_vector(client, prompts, api_settings, reviews_text)
            result["gameplay_vector"] = gameplay_vector

            # 3. MUSIC VECTOR (Hierarchical)
            music_vector = self._get_hierarchical_music_vector(client, prompts, api_settings, reviews_text)
            result["music_vector"] = music_vector

            # 4. VIBES VECTOR
            vibes_vector = self._get_vibes_vector(client, prompts, api_settings, reviews_text)
            result["vibes_vector"] = vibes_vector

            return result

        except Exception as e:
            result["error"] = str(e)
            return result

    def _get_consensus(self, client, prompts, api_settings, reviews_text, num_reviews) -> str:
        """Get consensus summary"""
        consensus_prompt = prompts.get("main_consensus", "").format(
            num_reviews=num_reviews,
            reviews_text=reviews_text
        )

        response = client.chat.completions.create(
            model=api_settings.get("model", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": prompts.get("system_role_consensus", "")},
                {"role": "user", "content": consensus_prompt}
            ],
            temperature=api_settings.get("temperature", 0.3),
            max_tokens=api_settings.get("max_tokens_consensus", 150)
        )

        return response.choices[0].message.content.strip()

    def _get_gameplay_vector(self, client, prompts, api_settings, reviews_text) -> Dict:
        """Get gameplay mechanics vector"""
        gameplay_prompt = prompts.get("gameplay_vector", "").format(reviews_text=reviews_text)

        response = client.chat.completions.create(
            model=api_settings.get("model", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": prompts.get("system_role_gameplay", "")},
                {"role": "user", "content": gameplay_prompt}
            ],
            temperature=0.3,
            max_tokens=200
        )

        analysis = response.choices[0].message.content.strip()
        return self._parse_vector(analysis, "MAIN_GAMEPLAY:", "SUB_MECHANICS:", "gameplay_elements")

    def _get_vibes_vector(self, client, prompts, api_settings, reviews_text) -> Dict:
        """Get vibes/atmosphere vector"""
        vibes_prompt = prompts.get("vibes_vector", "").format(reviews_text=reviews_text)

        response = client.chat.completions.create(
            model=api_settings.get("model", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": prompts.get("system_role_vibes", "")},
                {"role": "user", "content": vibes_prompt}
            ],
            temperature=0.3,
            max_tokens=200
        )

        analysis = response.choices[0].message.content.strip()
        return self._parse_vector(analysis, "MAIN_VIBES:", "SUB_MOODS:", "vibes_atmosphere")

    def _get_hierarchical_music_vector(self, client, prompts, api_settings, reviews_text) -> Dict:
        """Get hierarchical music genre vector"""
        music_prompt = prompts.get("music_vector", "").format(reviews_text=reviews_text)

        response = client.chat.completions.create(
            model=api_settings.get("model", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": prompts.get("system_role_music", "")},
                {"role": "user", "content": music_prompt}
            ],
            temperature=0.3,
            max_tokens=250
        )

        analysis = response.choices[0].message.content.strip()
        return self._parse_hierarchical_music_vector(analysis)

    def _parse_vector(self, response: str, main_prefix: str, sub_prefix: str, category: str = None) -> Dict:
        """Parse standard vector response with optional synonym normalization"""
        result = {
            "main": {},
            "sub": {},
            "description": "No information available"
        }

        lines = response.strip().split('\n')
        for line in lines:
            line = line.strip()

            if line.startswith(main_prefix):
                items_str = line.replace(main_prefix, "").strip()
                if items_str:
                    for item_pair in items_str.split():
                        if ':' in item_pair:
                            item, percentage = item_pair.split(':')
                            try:
                                # Normalize if category is provided
                                if category:
                                    item = self._normalize_synonyms(item, category)
                                else:
                                    item = item.lower()
                                result["main"][item] = int(percentage)
                            except ValueError:
                                pass

            elif line.startswith(sub_prefix):
                sub_str = line.replace(sub_prefix, "").strip()
                if sub_str:
                    for sub_pair in sub_str.split():
                        if ':' in sub_pair:
                            sub_item, percentage = sub_pair.split(':')
                            try:
                                # Normalize if category is provided
                                if category:
                                    sub_item = self._normalize_synonyms(sub_item, category)
                                else:
                                    sub_item = sub_item.lower()
                                result["sub"][sub_item] = int(percentage)
                            except ValueError:
                                pass

            elif line.startswith("DESCRIPTION:"):
                result["description"] = line.replace("DESCRIPTION:", "").strip()

        return result

    def _normalize_synonyms(self, term: str, category: str) -> str:
        """Normalize synonyms to canonical forms based on config mapping"""
        synonym_mapping = self.config.get("synonym_mapping", {}).get(category, {})

        term_lower = term.lower().replace("-", "_").replace(" ", "_")

        # Check if this term should be mapped to a canonical form
        for canonical, synonyms in synonym_mapping.items():
            if term_lower in [s.replace("-", "_").replace(" ", "_") for s in synonyms]:
                return canonical

        return term_lower

    def _parse_hierarchical_music_vector(self, response: str) -> Dict:
        """Parse hierarchical music vector with sub-genres for each main genre"""
        result = {
            "main_genres": {},
            "genre_subgenres": {},
            "description": "No music information available"
        }

        lines = response.strip().split('\n')

        for line in lines:
            line = line.strip()

            # Parse main genres
            if line.startswith("MAIN_GENRES:"):
                genres_str = line.replace("MAIN_GENRES:", "").strip()
                if genres_str:
                    for genre_pair in genres_str.split():
                        if ':' in genre_pair:
                            genre, percentage = genre_pair.split(':')
                            try:
                                # Normalize the genre name
                                normalized_genre = self._normalize_synonyms(genre, "music_genres")
                                result["main_genres"][normalized_genre] = int(percentage)
                            except ValueError:
                                pass

            # Parse sub-genres for each main genre
            elif "_SUBGENRES:" in line:
                genre_name = line.split("_SUBGENRES:")[0].lower()
                normalized_genre = self._normalize_synonyms(genre_name, "music_genres")
                subgenres_str = line.split("_SUBGENRES:")[1].strip()

                if normalized_genre and subgenres_str:
                    result["genre_subgenres"][normalized_genre] = {}
                    for sub_pair in subgenres_str.split():
                        if ':' in sub_pair:
                            sub_genre, percentage = sub_pair.split(':')
                            try:
                                # Normalize the sub-genre name
                                normalized_subgenre = self._normalize_synonyms(sub_genre, "music_genres")
                                result["genre_subgenres"][normalized_genre][normalized_subgenre] = int(percentage)
                            except ValueError:
                                pass

            # Parse description
            elif line.startswith("DESCRIPTION:"):
                result["description"] = line.replace("DESCRIPTION:", "").strip()

        return result