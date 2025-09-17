import json
import os
from collections import defaultdict, Counter
from difflib import SequenceMatcher
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class GameSearchEngine:
    def __init__(self, data_file='steam_games_with_hierarchical_tags.json'):
        self.data_file = data_file
        self.games_data = {}
        self.genre_index = defaultdict(list)
        self.tag_vectorizer = None
        self.tag_vectors = None
        self.game_ids = []
        
        self.load_data()
        self.build_indices()
        self.build_tag_vectors()
    
    def load_data(self):
        """Load the game database"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                self.games_data = json.load(f)
            print(f"Loaded {len(self.games_data)} games from database")
        except FileNotFoundError:
            print(f"Error: {self.data_file} not found!")
            print("Please run the tag builder first to create the database.")
            exit(1)
    
    def build_indices(self):
        """Build hierarchical genre indices for fast lookup"""
        for appid, game in self.games_data.items():
            main_genre = game.get('main_genre', 'unknown')
            sub_genre = game.get('sub_genre', 'unknown')
            sub_sub_genre = game.get('sub_sub_genre', 'unknown')
            
            # Create hierarchical keys
            self.genre_index[f"main:{main_genre}"].append(appid)
            self.genre_index[f"sub:{main_genre}:{sub_genre}"].append(appid)
            self.genre_index[f"subsub:{main_genre}:{sub_genre}:{sub_sub_genre}"].append(appid)
    
    def build_tag_vectors(self):
        """Build TF-IDF vectors for unique and subjective tags only (no art/music)"""
        print("Building tag similarity vectors...")
        
        game_tag_texts = []
        self.game_ids = []
        
        for appid, game in self.games_data.items():
            # Only include gameplay-related tags (no art style or music)
            all_tags = []
            all_tags.extend(game.get('unique_tags', []))
            all_tags.extend(game.get('subjective_tags', []))
            all_tags.append(game.get('theme', ''))  # Theme is gameplay-relevant
            
            # Create text representation
            tag_text = ' '.join(filter(None, all_tags))
            game_tag_texts.append(tag_text)
            self.game_ids.append(appid)
        
        # Build TF-IDF vectors
        self.tag_vectorizer = TfidfVectorizer(
            lowercase=True,
            token_pattern=r'[a-zA-Z-]+',
            ngram_range=(1, 2),
            max_features=1000
        )
        
        self.tag_vectors = self.tag_vectorizer.fit_transform(game_tag_texts)
        print(f"Built vectors for {len(self.game_ids)} games")
    
    def find_game_by_name(self, query):
        """Find games matching a name query with improved precision"""
        query_lower = query.lower().strip()
        matches = []
        
        for appid, game in self.games_data.items():
            game_name = game.get('name', '').lower()
            
            # Score different types of matches
            score = 0
            match_type = ""
            
            # Exact match (highest priority)
            if query_lower == game_name:
                score = 1.0
                match_type = "exact"
            
            # Starts with query (high priority)  
            elif game_name.startswith(query_lower):
                score = 0.9
                match_type = "starts_with"
            
            # Contains query as whole word (medium-high priority)
            elif f" {query_lower} " in f" {game_name} " or game_name.startswith(query_lower + " "):
                score = 0.8
                match_type = "whole_word"
            
            # Contains query substring (medium priority)
            elif query_lower in game_name:
                score = 0.7
                match_type = "contains"
            
            # Fuzzy similarity for typos (lower priority)
            else:
                similarity = SequenceMatcher(None, query_lower, game_name).ratio()
                if similarity > 0.7:  # Much higher threshold for fuzzy matches
                    score = similarity * 0.6  # Reduce fuzzy match scores
                    match_type = "fuzzy"
            
            # Only include if we have a reasonable match
            if score > 0.6:
                matches.append({
                    'appid': appid,
                    'name': game['name'],
                    'similarity': score,
                    'match_type': match_type,
                    'main_genre': game.get('main_genre', 'unknown'),
                    'sub_genre': game.get('sub_genre', 'unknown'),
                    'sub_sub_genre': game.get('sub_sub_genre', 'unknown')
                })
        
        # Sort by score, then by match type priority
        match_type_priority = {"exact": 5, "starts_with": 4, "whole_word": 3, "contains": 2, "fuzzy": 1}
        matches.sort(key=lambda x: (x['similarity'], match_type_priority.get(x['match_type'], 0)), reverse=True)
        
        return matches[:10]
    
    def get_game_tags(self, appid):
        """Get available tags for user selection (excluding art/music)"""
        game = self.games_data.get(appid)
        if not game:
            return {}
        
        available_tags = {
            'unique_tags': game.get('unique_tags', []),
            'subjective_tags': game.get('subjective_tags', []),
            'theme': [game.get('theme', '')]
        }
        
        # Filter out empty tags
        return {k: [tag for tag in v if tag and tag != 'unknown'] 
                for k, v in available_tags.items() if v and any(tag and tag != 'unknown' for tag in v)}
    
    def find_similar_games(self, target_appid, preferred_tags=None, tag_weights=None):
        """Find similar games using hierarchical search with tag preferences"""
        target_game = self.games_data.get(target_appid)
        if not target_game:
            return []
        
        # Get hierarchy info
        main_genre = target_game.get('main_genre', 'unknown')
        sub_genre = target_game.get('sub_genre', 'unknown')
        sub_sub_genre = target_game.get('sub_sub_genre', 'unknown')
        
        print(f"\\nSearching for games similar to: {target_game['name']}")
        print(f"Hierarchy: {main_genre} → {sub_genre} → {sub_sub_genre}")
        
        # Try hierarchical search (most specific to least specific)
        candidates = []
        search_level = ""
        
        # Level 1: Sub-sub genre
        subsub_key = f"subsub:{main_genre}:{sub_genre}:{sub_sub_genre}"
        if subsub_key in self.genre_index and len(self.genre_index[subsub_key]) > 1:
            candidates = [appid for appid in self.genre_index[subsub_key] if appid != target_appid]
            search_level = f"sub-sub genre ({sub_sub_genre})"
        
        # Level 2: Sub genre (if not enough candidates)
        if len(candidates) < 5:
            sub_key = f"sub:{main_genre}:{sub_genre}"
            if sub_key in self.genre_index:
                candidates = [appid for appid in self.genre_index[sub_key] if appid != target_appid]
                search_level = f"sub genre ({sub_genre})"
        
        # Level 3: Main genre (if still not enough)
        if len(candidates) < 5:
            main_key = f"main:{main_genre}"
            if main_key in self.genre_index:
                candidates = [appid for appid in self.genre_index[main_key] if appid != target_appid]
                search_level = f"main genre ({main_genre})"
        
        if not candidates:
            print("No similar games found!")
            return []
        
        print(f"Found {len(candidates)} candidates in {search_level}")
        
        # Calculate similarity scores using tag vectors
        target_idx = self.game_ids.index(target_appid) if target_appid in self.game_ids else None
        if target_idx is None:
            return self._fallback_similarity(candidates, target_game)
        
        similarities = []
        target_vector = self.tag_vectors[target_idx]
        
        for candidate_appid in candidates:
            if candidate_appid in self.game_ids:
                candidate_idx = self.game_ids.index(candidate_appid)
                candidate_vector = self.tag_vectors[candidate_idx]
                
                # Calculate base similarity
                sim_score = cosine_similarity(target_vector, candidate_vector)[0][0]
                
                # Apply tag preferences if specified
                if preferred_tags and tag_weights:
                    bonus = self._calculate_tag_bonus(candidate_appid, preferred_tags, tag_weights)
                    sim_score = sim_score * 0.7 + bonus * 0.3  # 70% similarity, 30% preference
                
                similarities.append({
                    'appid': candidate_appid,
                    'similarity': sim_score,
                    'game': self.games_data[candidate_appid]
                })
        
        # Sort by similarity
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        return similarities[:10]
    
    def _calculate_tag_bonus(self, candidate_appid, preferred_tags, tag_weights):
        """Calculate bonus score based on user's tag preferences"""
        candidate_game = self.games_data.get(candidate_appid)
        if not candidate_game:
            return 0
        
        candidate_tags = []
        candidate_tags.extend(candidate_game.get('unique_tags', []))
        candidate_tags.extend(candidate_game.get('subjective_tags', []))
        candidate_tags.append(candidate_game.get('theme', ''))
        
        bonus = 0
        total_weight = sum(tag_weights.values())
        
        for tag in preferred_tags:
            if tag in candidate_tags:
                bonus += tag_weights.get(tag, 1) / total_weight
        
        return bonus
    
    def _fallback_similarity(self, candidates, target_game):
        """Fallback similarity calculation when vectors aren't available"""
        target_tags = set()
        target_tags.update(target_game.get('unique_tags', []))
        target_tags.update(target_game.get('subjective_tags', []))
        target_tags.add(target_game.get('theme', ''))
        
        similarities = []
        for candidate_appid in candidates:
            candidate_game = self.games_data.get(candidate_appid)
            if not candidate_game:
                continue
            
            candidate_tags = set()
            candidate_tags.update(candidate_game.get('unique_tags', []))
            candidate_tags.update(candidate_game.get('subjective_tags', []))
            candidate_tags.add(candidate_game.get('theme', ''))
            
            # Simple Jaccard similarity
            intersection = len(target_tags & candidate_tags)
            union = len(target_tags | candidate_tags)
            similarity = intersection / union if union > 0 else 0
            
            similarities.append({
                'appid': candidate_appid,
                'similarity': similarity,
                'game': candidate_game
            })
        
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        return similarities[:10]
    
    def filter_by_aesthetics(self, game_list, target_art_style=None, target_music_style=None):
        """Filter game list by matching art style and/or music style"""
        if not target_art_style and not target_music_style:
            return game_list
        
        filtered = []
        for game_result in game_list:
            game = game_result['game']
            matches = True
            
            if target_art_style and game.get('art_style') != target_art_style:
                matches = False
            
            if target_music_style and game.get('music_style') != target_music_style:
                matches = False
            
            if matches:
                filtered.append(game_result)
        
        return filtered


def display_game_info(game_data, show_full=False):
    """Display game information in a readable format"""
    name = game_data.get('name', 'Unknown Game')
    hierarchy = f"{game_data.get('main_genre', '?')} → {game_data.get('sub_genre', '?')} → {game_data.get('sub_sub_genre', '?')}"
    
    print(f"\\n📱 {name}")
    print(f"   🎮 {hierarchy}")
    
    if show_full:
        art_style = game_data.get('art_style', 'unknown')
        theme = game_data.get('theme', 'unknown')  
        music_style = game_data.get('music_style', 'unknown')
        
        print(f"   🎨 Art: {art_style} | 🌍 Theme: {theme} | 🎵 Music: {music_style}")
        
        unique_tags = game_data.get('unique_tags', [])
        subjective_tags = game_data.get('subjective_tags', [])
        
        if unique_tags:
            print(f"   ⭐ Unique: {', '.join(unique_tags[:3])}")
        if subjective_tags:
            print(f"   💭 Quality: {', '.join(subjective_tags[:3])}")


def main():
    print("🎮 Game Similarity Search Engine")
    print("=" * 50)
    
    # Initialize search engine
    search_engine = GameSearchEngine()
    
    while True:
        print("\\n" + "=" * 50)
        query = input("🔍 Search for games like: ").strip()
        
        if query.lower() in ['quit', 'exit', 'q']:
            print("Thanks for using the game search engine!")
            break
        
        if not query:
            continue
        
        # Find matching games
        matches = search_engine.find_game_by_name(query)
        
        if not matches:
            print("❌ No games found matching your search.")
            continue
        
        # Display matches
        print(f"\\n🎯 Found {len(matches)} matching games:")
        for i, match in enumerate(matches, 1):
            confidence = "🟢" if match['similarity'] > 0.8 else "🟡" if match['similarity'] > 0.6 else "🟠"
            print(f"{i}. {confidence} {match['name']} ({match['main_genre']})")
        
        # Let user select a game
        try:
            choice = int(input("\\n📝 Select a game (number): ")) - 1
            if choice < 0 or choice >= len(matches):
                print("❌ Invalid selection.")
                continue
        except ValueError:
            print("❌ Please enter a number.")
            continue
        
        selected_game = matches[choice]
        target_appid = selected_game['appid']
        
        print(f"\\n✅ Selected: {selected_game['name']}")
        
        # Show available tags for preference weighting
        available_tags = search_engine.get_game_tags(target_appid)
        
        if available_tags:
            print("\\n🏷️  Available tags to prioritize:")
            all_tags = []
            
            for category, tags in available_tags.items():
                category_name = category.replace('_', ' ').title()
                print(f"\\n   {category_name}:")
                for tag in tags:
                    all_tags.append(tag)
                    print(f"     • {tag}")
            
            # Let user select preferred tags
            print("\\n🎯 Enter tag numbers you want to prioritize (comma-separated, or press Enter to skip):")
            for i, tag in enumerate(all_tags, 1):
                print(f"{i}. {tag}")
            
            tag_input = input("\\n📝 Your choices: ").strip()
            
            preferred_tags = []
            tag_weights = {}
            
            if tag_input:
                try:
                    tag_indices = [int(x.strip()) - 1 for x in tag_input.split(',')]
                    for idx in tag_indices:
                        if 0 <= idx < len(all_tags):
                            tag = all_tags[idx]
                            preferred_tags.append(tag)
                            tag_weights[tag] = 1.0  # Equal weight for now
                    
                    print(f"\\n✅ Prioritizing: {', '.join(preferred_tags)}")
                except ValueError:
                    print("❌ Invalid input, proceeding without tag preferences.")
        else:
            preferred_tags = None
            tag_weights = None
        
        # Find similar games
        similar_games = search_engine.find_similar_games(
            target_appid, preferred_tags, tag_weights
        )
        
        if not similar_games:
            print("❌ No similar games found.")
            continue
        
        # Display results
        print(f"\\n🎮 Top {len(similar_games)} similar games:")
        for i, result in enumerate(similar_games, 1):
            similarity_bar = "🟢" if result['similarity'] > 0.7 else "🟡" if result['similarity'] > 0.4 else "🟠"
            print(f"{i}. {similarity_bar} {result['game']['name']} ({result['similarity']:.2f})")
            display_game_info(result['game'])
        
        # Offer aesthetic filtering
        target_game = search_engine.games_data[target_appid]
        target_art = target_game.get('art_style', 'unknown')
        target_music = target_game.get('music_style', 'unknown')
        
        if target_art != 'unknown' or target_music != 'unknown':
            print(f"\\n🎨 Filter by matching aesthetics?")
            if target_art != 'unknown':
                print(f"   Art Style: {target_art}")
            if target_music != 'unknown':
                print(f"   Music Style: {target_music}")
            
            filter_choice = input("\\n📝 Filter by aesthetics? (y/n): ").strip().lower()
            
            if filter_choice == 'y':
                filtered_games = search_engine.filter_by_aesthetics(
                    similar_games, target_art, target_music
                )
                
                if filtered_games:
                    print(f"\\n🎨 Games with matching aesthetics ({len(filtered_games)} found):")
                    for i, result in enumerate(filtered_games, 1):
                        similarity_bar = "🟢" if result['similarity'] > 0.7 else "🟡" if result['similarity'] > 0.4 else "🟠"
                        print(f"{i}. {similarity_bar} {result['game']['name']} ({result['similarity']:.2f})")
                        display_game_info(result['game'], show_full=True)
                else:
                    print("❌ No games found with matching aesthetics.")


if __name__ == "__main__":
    main()