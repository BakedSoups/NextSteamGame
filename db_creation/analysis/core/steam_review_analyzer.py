"""
Simple Steam Review Analyzer Library
Focused on extracting and analyzing insightful reviews by appid
"""

import requests
import json
import re
import os
from typing import List, Dict, Optional
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


class SteamReviewAnalyzer:
    """Extract and analyze insightful Steam reviews for a game"""

    def __init__(self, config_path: str = "review_config.json"):
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        self.reviews_api_url = "https://store.steampowered.com/appreviews/{appid}"

        # Load configuration from JSON
        self.config = self._load_config(config_path)

        # Extract keyword sets from config
        keywords = self.config.get("insightful_review_keywords", {})
        self.gameplay_keywords = set(
            keywords.get("gameplay", []) +
            keywords.get("genre_indicators", []) +
            keywords.get("quality_indicators", [])
        )

        # Toxicity phrases from config
        self.toxicity_phrases = set(self.config.get("toxicity_filters", []))

        # Quality thresholds from config
        self.thresholds = self.config.get("review_quality_thresholds", {})

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load config from {config_path}: {e}")

        # Return default config if file doesn't exist
        return {
            "insightful_review_keywords": {
                "gameplay": ["mechanics", "controls", "gameplay", "combat"],
                "genre_indicators": ["fps", "rpg", "platformer"],
                "quality_indicators": ["polish", "balanced", "fair"]
            },
            "toxicity_filters": ["toxic", "grief", "trolls"],
            "review_quality_thresholds": {
                "min_review_length": 200,
                "min_playtime_hours": 1,
                "min_unique_chars": 10,
                "max_char_repetition": 30,
                "min_keyword_count": 3,
                "sentiment_toxicity_threshold": -0.5
            }
        }

    def pull_insightful_reviews(self, appid: int, max_reviews: int = 3, fetch_count: int = None) -> str:
        """
        Pull the most insightful reviews for a game and return as a string

        Args:
            appid: Steam app ID of the game
            max_reviews: Maximum number of insightful reviews to return (default: 3)
            fetch_count: Number of reviews to fetch from Steam (default: 100, max: 100 per request)

        Returns:
            String containing the most insightful reviews concatenated
        """
        # Determine how many reviews to fetch
        if fetch_count is None:
            fetch_count = min(max_reviews * 20, 100)  # Fetch more to ensure we get enough quality reviews
        else:
            fetch_count = min(fetch_count, 100)  # Steam API limit per request

        reviews = self._fetch_steam_reviews(appid, count=fetch_count)
        if not reviews:
            return ""

        filtered = self._filter_insightful_reviews(reviews)
        top_reviews = filtered[:max_reviews]

        # Combine review texts into a single string
        review_texts = [r["review"] for r in top_reviews]
        return " [NEXT REVIEW] ".join(review_texts)

    def get_review_insights(self, appid: int) -> Dict:
        """
        Get structured insights from reviews

        Args:
            appid: Steam app ID of the game

        Returns:
            Dictionary with review insights including sentiment and key themes
        """
        reviews = self._fetch_steam_reviews(appid)
        if not reviews:
            return {
                "appid": appid,
                "total_reviews": 0,
                "insightful_reviews": [],
                "average_sentiment": 0,
                "key_themes": []
            }

        filtered = self._filter_insightful_reviews(reviews)

        # Calculate average sentiment
        sentiments = [self._get_sentiment_score(r["review"]) for r in filtered[:10]]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0

        # Extract key themes
        all_text = " ".join([r["review"] for r in filtered[:10]])
        key_themes = self._extract_key_themes(all_text)

        return {
            "appid": appid,
            "total_reviews": len(reviews),
            "insightful_reviews": [
                {
                    "text": r["review"][:500],  # First 500 chars
                    "playtime_hours": r["playtime_hours"],
                    "voted_up": r["voted_up"]
                }
                for r in filtered[:3]
            ],
            "average_sentiment": round(avg_sentiment, 3),
            "key_themes": key_themes
        }

    def _fetch_steam_reviews(self, appid: int, count: int = 100) -> List[Dict]:
        """Fetch reviews from Steam API"""
        url = self.reviews_api_url.format(appid=appid)
        params = {
            "json": 1,
            "num_per_page": count,
            "filter": "recent",
            "language": "english"
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if "reviews" not in data:
                return []

            reviews = []
            for review in data["reviews"]:
                reviews.append({
                    "review": review["review"],
                    "voted_up": review["voted_up"],
                    "playtime_hours": round(review["author"]["playtime_forever"] / 60, 1),
                    "timestamp": review["timestamp_created"]
                })

            # Sort by playtime (most experienced players first)
            reviews.sort(key=lambda r: r["playtime_hours"], reverse=True)
            return reviews

        except Exception as e:
            print(f"Error fetching reviews for appid {appid}: {e}")
            return []

    def _filter_insightful_reviews(self, reviews: List[Dict]) -> List[Dict]:
        """Filter reviews to find the most insightful ones"""
        filtered = []

        for review in reviews:
            text = review["review"]

            # Basic quality checks using config thresholds
            if len(text) < self.thresholds.get("min_review_length", 200):  # Too short
                continue
            if review["playtime_hours"] < self.thresholds.get("min_playtime_hours", 1):  # Not enough experience
                continue
            if not self._is_comprehensible(text):  # Spam/gibberish
                continue

            # Check for gameplay keywords
            keyword_count = self._count_keywords(text)
            if keyword_count < self.thresholds.get("min_keyword_count", 3):  # Not enough substance
                continue

            # Filter out toxic complaints
            sentiment = self._get_sentiment_score(text)
            toxicity_threshold = self.thresholds.get("sentiment_toxicity_threshold", -0.5)
            if sentiment < toxicity_threshold and self._contains_toxicity(text):
                continue

            # Add keyword count for ranking
            review["keyword_count"] = keyword_count
            review["sentiment"] = sentiment
            filtered.append(review)

        # Sort by quality indicators
        filtered.sort(
            key=lambda r: (r["keyword_count"], r["playtime_hours"], r["voted_up"]),
            reverse=True
        )

        return filtered

    def _is_comprehensible(self, text: str) -> bool:
        """Check if text is comprehensible (not spam)"""
        # Check for minimum unique characters
        unique_chars = set(c.lower() for c in text if c.isalpha())
        min_chars = self.thresholds.get("min_unique_chars", 10)
        if len(unique_chars) < min_chars:
            return False

        # Check for excessive repetition
        max_repetition = self.thresholds.get("max_char_repetition", 30)
        if re.search(rf'(.)\1{{{max_repetition},}}', text):
            return False

        return True

    def _count_keywords(self, text: str) -> int:
        """Count gameplay-related keywords in text"""
        lower_text = text.lower()
        return sum(1 for keyword in self.gameplay_keywords if keyword in lower_text)

    def _get_sentiment_score(self, text: str) -> float:
        """Get sentiment score for text"""
        scores = self.sentiment_analyzer.polarity_scores(text)
        return scores['compound']

    def _contains_toxicity(self, text: str) -> bool:
        """Check if text contains toxic phrases"""
        lower_text = text.lower()
        return any(phrase in lower_text for phrase in self.toxicity_phrases)

    def _extract_key_themes(self, text: str) -> List[str]:
        """Extract key themes from text based on keyword frequency"""
        lower_text = text.lower()
        theme_counts = {}

        for keyword in self.gameplay_keywords:
            count = lower_text.count(keyword)
            if count > 0:
                theme_counts[keyword] = count

        # Return top 5 themes
        sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
        return [theme for theme, _ in sorted_themes[:5]]


# Simple usage functions
def pull_insightful_reviews(appid: int) -> str:
    """
    Simple function to pull insightful reviews for a game

    Args:
        appid: Steam app ID

    Returns:
        String of concatenated insightful reviews
    """
    analyzer = SteamReviewAnalyzer()
    return analyzer.pull_insightful_reviews(appid)


def analyze_game_reviews(appid: int) -> Dict:
    """
    Analyze game reviews and return insights

    Args:
        appid: Steam app ID

    Returns:
        Dictionary with review analysis
    """
    analyzer = SteamReviewAnalyzer()
    return analyzer.get_review_insights(appid)


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) > 1:
        try:
            appid = int(sys.argv[1])
            print(f"\nAnalyzing reviews for appid: {appid}")
            print("=" * 50)

            # Get insightful reviews as string
            reviews_text = pull_insightful_reviews(appid)
            if reviews_text:
                print("\nInsightful Reviews (concatenated):")
                print("-" * 30)
                print(reviews_text[:1000] + "..." if len(reviews_text) > 1000 else reviews_text)

            # Get structured insights
            insights = analyze_game_reviews(appid)
            print(f"\n\nReview Insights:")
            print("-" * 30)
            print(f"Total reviews fetched: {insights['total_reviews']}")
            print(f"Average sentiment: {insights['average_sentiment']}")
            print(f"Key themes: {', '.join(insights['key_themes'])}")
            print(f"Most insightful reviews: {len(insights['insightful_reviews'])}")

        except ValueError:
            print("Please provide a valid Steam app ID as argument")
    else:
        print("Usage: python steam_review_analyzer.py <appid>")
        print("Example: python steam_review_analyzer.py 730  # CS:GO")