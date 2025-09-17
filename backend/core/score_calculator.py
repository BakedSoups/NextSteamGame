"""
Modular Score Calculator for Game Similarity

This module provides a flexible scoring system that can be easily adjusted
and extended with new vector databases (images, audio, metadata, etc.)
"""
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
import numpy as np


@dataclass
class ScoreWeights:
    """Configuration for similarity score weights - must sum to 100"""
    gameplay_vector: float = 40.0      # TF-IDF gameplay similarity
    sub_sub_genre: float = 20.0        # Unique defining element match
    sub_genre: float = 10.0            # Specific style match
    main_genre: float = 5.0            # Broad category match
    user_preferences: float = 15.0     # User aesthetic/tag preferences
    visual_similarity: float = 0.0     # Future: Image vector similarity
    audio_similarity: float = 0.0      # Future: Music/sound similarity
    metadata_similarity: float = 0.0   # Future: Release date, price, etc.
    special_bonuses: float = 10.0      # Soulslike, popular combos, etc.

    def __post_init__(self):
        """Validate weights sum to 100"""
        total = (self.gameplay_vector + self.sub_sub_genre + self.sub_genre +
                self.main_genre + self.user_preferences + self.visual_similarity +
                self.audio_similarity + self.metadata_similarity + self.special_bonuses)

        if abs(total - 100.0) > 0.01:
            raise ValueError(f"Score weights must sum to 100%, got {total}%")

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for easy iteration"""
        return {
            'gameplay_vector': self.gameplay_vector,
            'sub_sub_genre': self.sub_sub_genre,
            'sub_genre': self.sub_genre,
            'main_genre': self.main_genre,
            'user_preferences': self.user_preferences,
            'visual_similarity': self.visual_similarity,
            'audio_similarity': self.audio_similarity,
            'metadata_similarity': self.metadata_similarity,
            'special_bonuses': self.special_bonuses
        }


@dataclass
class SimilarityScores:
    """Raw similarity scores from different components (0.0 to 1.0)"""
    gameplay_vector: float = 0.0       # Cosine similarity of gameplay vectors
    sub_sub_genre_match: bool = False  # Exact sub_sub_genre match
    sub_genre_match: bool = False      # Same sub_genre, different sub_sub_genre
    main_genre_match: bool = False     # Same main_genre only
    user_preferences: float = 0.0      # User preference bonus (0.0 to 1.0)
    visual_similarity: float = 0.0     # Future: Image similarity
    audio_similarity: float = 0.0      # Future: Audio similarity
    metadata_similarity: float = 0.0   # Future: Metadata similarity
    soulslike_bonus: bool = False      # Special soulslike detection
    popular_combo_bonus: float = 0.0   # Popular tag combinations


class ScoreCalculator:
    """
    Flexible similarity score calculator that can be easily reconfigured
    and extended with new similarity vectors
    """

    def __init__(self, weights: Optional[ScoreWeights] = None):
        self.weights = weights or ScoreWeights()
        self._score_components = {}  # For debugging/analysis

    def calculate_final_score(self, similarities: SimilarityScores) -> Tuple[float, Dict[str, float]]:
        """
        Calculate final similarity score and return breakdown

        Returns:
            Tuple of (final_score, component_breakdown)
        """
        self._score_components.clear()

        # Calculate each component score (0.0 to 1.0 range)
        components = {
            'gameplay_vector': self._score_gameplay_vector(similarities.gameplay_vector),
            'sub_sub_genre': self._score_sub_sub_genre(similarities.sub_sub_genre_match),
            'sub_genre': self._score_sub_genre(similarities.sub_genre_match),
            'main_genre': self._score_main_genre(similarities.main_genre_match),
            'user_preferences': self._score_user_preferences(similarities.user_preferences),
            'visual_similarity': self._score_visual_similarity(similarities.visual_similarity),
            'audio_similarity': self._score_audio_similarity(similarities.audio_similarity),
            'metadata_similarity': self._score_metadata_similarity(similarities.metadata_similarity),
            'special_bonuses': self._score_special_bonuses(similarities)
        }

        # Apply weights and calculate final score
        weighted_scores = {}
        final_score = 0.0

        for component, raw_score in components.items():
            weight = getattr(self.weights, component) / 100.0
            weighted_score = raw_score * weight
            weighted_scores[component] = {
                'raw_score': raw_score,
                'weight_percent': getattr(self.weights, component),
                'weighted_score': weighted_score,
                'contribution': weighted_score * 100  # As percentage of final
            }
            final_score += weighted_score

        # Store for debugging
        self._score_components = weighted_scores

        return min(final_score, 1.0), weighted_scores

    def _score_gameplay_vector(self, vector_similarity: float) -> float:
        """Score the TF-IDF gameplay vector similarity (0.0 to 1.0)"""
        return max(0.0, min(1.0, vector_similarity))

    def _score_sub_sub_genre(self, is_match: bool) -> float:
        """Score sub_sub_genre match - unique defining element"""
        return 1.0 if is_match else 0.0

    def _score_sub_genre(self, is_match: bool) -> float:
        """Score sub_genre match - specific gameplay style"""
        return 1.0 if is_match else 0.0

    def _score_main_genre(self, is_match: bool) -> float:
        """Score main_genre match - broad category"""
        return 1.0 if is_match else 0.0

    def _score_user_preferences(self, preference_score: float) -> float:
        """Score user preferences (already 0.0 to 1.0)"""
        return max(0.0, min(1.0, preference_score))

    def _score_visual_similarity(self, visual_score: float) -> float:
        """Future: Score visual similarity from image vectors"""
        if self.weights.visual_similarity == 0.0:
            return 0.0
        return max(0.0, min(1.0, visual_score))

    def _score_audio_similarity(self, audio_score: float) -> float:
        """Future: Score audio similarity from music/sound analysis"""
        if self.weights.audio_similarity == 0.0:
            return 0.0
        return max(0.0, min(1.0, audio_score))

    def _score_metadata_similarity(self, metadata_score: float) -> float:
        """Future: Score metadata similarity (release date, price, etc.)"""
        if self.weights.metadata_similarity == 0.0:
            return 0.0
        return max(0.0, min(1.0, metadata_score))

    def _score_special_bonuses(self, similarities: SimilarityScores) -> float:
        """Calculate special bonuses (soulslike, popular combos, etc.)"""
        bonus_score = 0.0

        # Soulslike bonus (very specific niche)
        if similarities.soulslike_bonus:
            bonus_score += 0.7  # High bonus for this special case

        # Popular tag combination bonus
        bonus_score += similarities.popular_combo_bonus

        return min(1.0, bonus_score)

    def get_score_breakdown(self) -> Dict[str, Dict[str, float]]:
        """Get detailed breakdown of last calculated score"""
        return self._score_components.copy()

    def update_weights(self, **kwargs) -> None:
        """Update specific weights dynamically"""
        for key, value in kwargs.items():
            if hasattr(self.weights, key):
                setattr(self.weights, key, value)

        # Validate new weights
        try:
            self.weights.__post_init__()
        except ValueError as e:
            raise ValueError(f"Invalid weight update: {e}")

    def get_current_weights(self) -> Dict[str, float]:
        """Get current weight configuration"""
        return self.weights.to_dict()


# Predefined weight configurations for different use cases
class WeightPresets:
    """Common weight configurations for different recommendation strategies"""

    @staticmethod
    def gameplay_focused() -> ScoreWeights:
        """Heavy emphasis on gameplay mechanics"""
        return ScoreWeights(
            gameplay_vector=60.0,
            sub_sub_genre=15.0,
            sub_genre=10.0,
            main_genre=5.0,
            user_preferences=10.0
        )

    @staticmethod
    def niche_focused() -> ScoreWeights:
        """Heavy emphasis on niche/genre matching"""
        return ScoreWeights(
            gameplay_vector=30.0,
            sub_sub_genre=35.0,
            sub_genre=15.0,
            main_genre=5.0,
            user_preferences=15.0
        )

    @staticmethod
    def balanced() -> ScoreWeights:
        """Default balanced approach"""
        return ScoreWeights()  # Uses defaults

    @staticmethod
    def visual_heavy() -> ScoreWeights:
        """Future: For when visual similarity is implemented"""
        return ScoreWeights(
            gameplay_vector=25.0,
            sub_sub_genre=15.0,
            sub_genre=10.0,
            main_genre=5.0,
            user_preferences=10.0,
            visual_similarity=35.0
        )

    @staticmethod
    def multimedia_future() -> ScoreWeights:
        """Future: Full multimedia similarity"""
        return ScoreWeights(
            gameplay_vector=30.0,
            sub_sub_genre=20.0,
            sub_genre=5.0,
            main_genre=5.0,
            user_preferences=10.0,
            visual_similarity=20.0,
            audio_similarity=10.0
        )


# Example usage and testing
if __name__ == "__main__":
    # Example: Calculate similarity between two games from 20k database
    calculator = ScoreCalculator()

    # Mock similarity data - realistic for 20k game database
    similarities = SimilarityScores(
        gameplay_vector=0.75,           # 75% gameplay vector similarity (TF-IDF)
        sub_sub_genre_match=True,       # Same unique defining element (rare in 20k)
        sub_genre_match=True,           # Same specific style (uncommon in 20k)
        main_genre_match=True,          # Same broad category (common in 20k)
        user_preferences=0.6,           # 60% user preference match
        soulslike_bonus=True,           # Special soulslike bonus (very rare)
        popular_combo_bonus=0.2         # Some popular tag combo
    )

    # Calculate final score
    final_score, breakdown = calculator.calculate_final_score(similarities)

    print(f"Final Similarity Score (20k database): {final_score:.3f}")
    print("\nScore Breakdown:")
    for component, details in breakdown.items():
        weight = details['weight_percent']
        contribution = details['contribution']
        raw = details['raw_score']
        print(f"  {component:20} | Weight: {weight:5.1f}% | Raw: {raw:.3f} | Contribution: {contribution:5.1f}%")

    # Test scaling for 20k games - sub_sub_genre becomes more valuable
    print("\n" + "="*60)
    print("Weight Configurations for 20k Game Database:")
    print("(sub_sub_genre matches are rarer and more valuable at scale)")

    presets = [
        ("Balanced (20k scale)", WeightPresets.balanced()),
        ("Gameplay Heavy", WeightPresets.gameplay_focused()),
        ("Niche Focused (rare matches)", WeightPresets.niche_focused())
    ]

    for name, weights in presets:
        calc = ScoreCalculator(weights)
        score, _ = calc.calculate_final_score(similarities)
        print(f"{name:25}: {score:.3f}")