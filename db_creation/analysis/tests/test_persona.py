#!/usr/bin/env python3
"""
Test script for Persona 3 Reload (AppID 1687950)
Clean test using the organized db_creation modules
"""

import sys
import json

from ..analyzers.vector_analyzer import VectorAnalyzer
from ..analyzers.output_formatter import OutputFormatter


def test_persona_analysis(num_reviews: int = 10) -> None:
    """Test full vector analysis for Persona 3 Reload"""

    appid = 1687950  # Persona 3 Reload

    print(f"🎮 Testing vector analysis for AppID {appid}")
    print(f"📊 Analyzing {num_reviews} reviews")

    try:
        # Initialize analyzer
        analyzer = VectorAnalyzer()

        # Get full analysis
        results = analyzer.analyze_game_vectors(appid, num_reviews)

        if "error" in results:
            print(f"❌ Error: {results['error']}")
            return

        # Print formatted output
        OutputFormatter.print_full_analysis(results)

        # Save results
        output_file = f"persona_analysis_{num_reviews}_reviews.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\n💾 Results saved to: {output_file}")

    except Exception as e:
        print(f"❌ Error during analysis: {e}")


def main():
    """Main function with command line argument support"""

    num_reviews = 10  # default

    if len(sys.argv) > 1:
        try:
            num_reviews = int(sys.argv[1])
            if num_reviews < 1:
                print("❌ Number of reviews must be at least 1")
                sys.exit(1)
            if num_reviews > 50:
                print("⚠️ Warning: Analyzing more than 50 reviews may be slow and costly")
        except ValueError:
            print("❌ Invalid number. Usage: python test_persona.py [number_of_reviews]")
            print("Example: python test_persona.py 15")
            sys.exit(1)

    test_persona_analysis(num_reviews)


if __name__ == "__main__":
    main()
