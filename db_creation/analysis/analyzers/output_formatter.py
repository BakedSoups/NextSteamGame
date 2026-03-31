"""
Output formatting utilities for vector analysis results
"""

from typing import Dict


class OutputFormatter:
    """Formats vector analysis output for display"""

    @staticmethod
    def print_full_analysis(analysis: Dict) -> None:
        """Pretty print complete game analysis"""

        print("\n" + "=" * 60)
        print(f"📊 GAME ANALYSIS - AppID {analysis.get('appid', 'Unknown')}")
        print("=" * 60)

        if "error" in analysis:
            print(f"❌ Error: {analysis['error']}")
            return

        print(f"Reviews analyzed: {analysis.get('num_reviews_analyzed', 'Unknown')}")

        # CONSENSUS
        OutputFormatter._print_consensus(analysis)

        # GAMEPLAY VECTOR
        OutputFormatter._print_gameplay_vector(analysis)

        # MUSIC VECTOR (Hierarchical)
        OutputFormatter._print_hierarchical_music_vector(analysis)

        # VIBES VECTOR
        OutputFormatter._print_vibes_vector(analysis)

        print("\n" + "=" * 60)

    @staticmethod
    def _print_consensus(analysis: Dict) -> None:
        """Print consensus section"""
        print("\n✨ CONSENSUS:")
        print("-" * 40)
        print(analysis.get("consensus", "No consensus available"))

    @staticmethod
    def _print_gameplay_vector(analysis: Dict) -> None:
        """Print gameplay vector section"""
        print("\n🎯 GAMEPLAY VECTOR:")
        print("-" * 40)

        gameplay = analysis.get("gameplay_vector", {})

        if gameplay.get("main"):
            print("Main Gameplay Elements:")
            for element, percentage in sorted(gameplay["main"].items(), key=lambda x: x[1], reverse=True):
                print(f"  • {element}: {percentage}%")

        if gameplay.get("sub"):
            print("\nSub-Mechanics:")
            for mechanic, percentage in sorted(gameplay["sub"].items(), key=lambda x: x[1], reverse=True):
                print(f"  • {mechanic}: {percentage}%")

        print(f"\nDescription: {gameplay.get('description', 'N/A')}")

    @staticmethod
    def _print_hierarchical_music_vector(analysis: Dict) -> None:
        """Print hierarchical music vector section"""
        print("\n🎵 MUSIC VECTOR (Hierarchical):")
        print("-" * 40)

        music = analysis.get("music_vector", {})
        main_genres = music.get("main_genres", {})
        genre_subgenres = music.get("genre_subgenres", {})

        if main_genres:
            # Sort by percentage
            sorted_genres = sorted(main_genres.items(), key=lambda x: x[1], reverse=True)

            for genre, percentage in sorted_genres:
                print(f"\n🎼 {genre.upper()}: {percentage}%")

                # Print sub-genres for this genre
                if genre in genre_subgenres and genre_subgenres[genre]:
                    sorted_subs = sorted(genre_subgenres[genre].items(),
                                       key=lambda x: x[1], reverse=True)
                    for sub_genre, sub_percent in sorted_subs:
                        print(f"   └─ {sub_genre}: {sub_percent}%")
        else:
            print("No music genre data available")

        print(f"\nDescription: {music.get('description', 'N/A')}")

        # Validation check
        if main_genres:
            total = sum(main_genres.values())
            if total != 100:
                print(f"⚠️  Warning: Main genres total {total}% (should be 100%)")

    @staticmethod
    def _print_vibes_vector(analysis: Dict) -> None:
        """Print vibes vector section"""
        print("\n✨ VIBES VECTOR:")
        print("-" * 40)

        vibes = analysis.get("vibes_vector", {})

        if vibes.get("main"):
            print("Main Vibes:")
            for vibe, percentage in sorted(vibes["main"].items(), key=lambda x: x[1], reverse=True):
                print(f"  • {vibe}: {percentage}%")

        if vibes.get("sub"):
            print("\nSub-Moods:")
            for mood, percentage in sorted(vibes["sub"].items(), key=lambda x: x[1], reverse=True):
                print(f"  • {mood}: {percentage}%")

        print(f"\nDescription: {vibes.get('description', 'N/A')}")

    @staticmethod
    def print_music_only(analysis: Dict) -> None:
        """Print only the hierarchical music analysis"""
        print("\n" + "=" * 60)
        print("🎵 HIERARCHICAL MUSIC ANALYSIS")
        print("=" * 60)

        music = analysis.get("music_vector", {})
        main_genres = music.get("main_genres", {})
        genre_subgenres = music.get("genre_subgenres", {})

        if main_genres:
            print("\n📊 MAIN GENRES (should total 100%):")
            print("-" * 40)

            # Sort by percentage
            sorted_genres = sorted(main_genres.items(), key=lambda x: x[1], reverse=True)

            for genre, percentage in sorted_genres:
                print(f"\n🎼 {genre.upper()}: {percentage}%")

                # Print sub-genres for this genre
                if genre in genre_subgenres and genre_subgenres[genre]:
                    sorted_subs = sorted(genre_subgenres[genre].items(),
                                       key=lambda x: x[1], reverse=True)
                    for sub_genre, sub_percent in sorted_subs:
                        print(f"   └─ {sub_genre}: {sub_percent}%")

            # Validation
            total = sum(main_genres.values())
            print(f"\n✅ Total percentage check: {total}%")

            # Check sub-genre totals
            for genre, percentage in main_genres.items():
                if genre in genre_subgenres:
                    sub_total = sum(genre_subgenres[genre].values())
                    if sub_total != percentage:
                        print(f"⚠️  {genre} sub-genres total {sub_total}% but should be {percentage}%")
        else:
            print("No genre data available")

        print(f"\n📝 Description:")
        print("-" * 40)
        print(music.get("description", "No description available"))

        print("\n" + "=" * 60)