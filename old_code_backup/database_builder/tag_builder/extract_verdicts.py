import requests
import sqlite3
import json
import os
import time
import re
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from openai import OpenAI

analyzer = SentimentIntensityAnalyzer()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

TAG_CONTEXT = {
    'ratio_tags': set(),
    'unique_tags': set(),
    'subjective_tags': set(),
    'main_genres': set(),
    'sub_genres': set(),
    'sub_sub_genres': set(),
    'art_styles': set(),
    'themes': set(),
    'music_styles': set()
}

GAMEPLAY_KEYWORDS = {
    "vibes", "soundtrack", "music", "overall", "the good", "pros", "cons",
    "mechanics", "controls", "gameplay", "combat", "movement", "pacing",
    "shooting", "platforming", "turn based", "real time", "puzzle", "exploration",
    "stealth", "driving", "flying", "building", "crafting", "level", "missions", 
    "quests", "campaign", "objectives", "checkpoints", "difficulty", "progression", 
    "grind", "boss", "miniboss", "enemy ai", "chill", "multiplayer", "co-op", 
    "singleplayer", "team", "ranked", "competitive", "pvp", "pve", "sandbox", 
    "open world", "inventory", "skills", "abilities", "tree", "upgrade", "loadout", 
    "gear", "weapons", "armor", "stats", "classes", "perks", "mods", "economy",
    "fps", "rpg", "roguelike", "deck builder", "platformer", "shooter", "metroidvania",
    "strategy", "simulation", "management", "builder", "survival", "horror"
}

ART_STYLE_KEYWORDS = {
    "pixel", "pixelated", "pixel art", "8-bit", "16-bit", "retro", "sprite",
    "anime", "cel-shaded", "cel shaded", "cartoon", "cartoony", "toon",
    "realistic", "photorealistic", "hyper-realistic", "lifelike",
    "stylized", "stylised", "art style", "artstyle", "aesthetic",
    "minimalist", "abstract", "geometric", "low-poly", "polygonal",
    "hand-drawn", "hand drawn", "painted", "watercolor", "oil painting",
    "comic book", "comic", "manga", "sketch", "sketchy", "pencil",
    "3d", "2d", "2.5d", "isometric", "top-down", "side-scrolling",
    "noir", "black and white", "monochrome", "sepia", "vintage",
    "neon", "cyberpunk", "steampunk", "gothic", "dark", "bright",
    "colorful", "colourful", "vibrant", "muted", "pastel",
    "flat", "material design", "voxel", "blocky", "minecraft",
    "unity", "unreal", "source engine", "cel animation", "rotoscope"
}

THEME_KEYWORDS = {
    # Time Periods
    "medieval", "modern", "futuristic", "prehistoric", "ancient", "renaissance",
    "victorian", "industrial", "contemporary", "near-future", "far-future",
    
    # Settings
    "sci-fi", "fantasy", "cyberpunk", "steampunk", "dieselpunk", "post-apocalyptic",
    "dystopian", "utopian", "western", "noir", "horror", "supernatural",
    "zombie", "vampire", "werewolf", "alien", "space", "underwater",
    
    # Locations
    "city", "urban", "rural", "wilderness", "forest", "desert", "arctic",
    "tropical", "mountain", "cave", "dungeon", "castle", "mansion", "laboratory",
    "school", "hospital", "prison", "military", "spaceship", "space station",
    
    # Cultural
    "japanese", "chinese", "european", "american", "african", "mythology",
    "greek", "norse", "egyptian", "celtic", "hindu", "folklore",
    
    # Concepts
    "time-travel", "parallel-worlds", "magic", "technology", "nature",
    "war", "peace", "survival", "exploration", "mystery", "romance",
    "friendship", "family", "betrayal", "revenge", "redemption", "coming-of-age"
}

MUSIC_KEYWORDS = {
    # Genres
    "orchestral", "electronic", "ambient", "jazz", "rock", "metal", "classical",
    "folk", "country", "blues", "reggae", "hip-hop", "rap", "techno", "house",
    "dubstep", "synthwave", "chiptune", "8-bit music", "lofi", "lo-fi",
    
    # Styles
    "epic", "dramatic", "emotional", "uplifting", "melancholic", "haunting",
    "atmospheric", "energetic", "calming", "intense", "peaceful", "aggressive",
    "mysterious", "suspenseful", "romantic", "nostalgic", "triumphant",
    
    # Instruments
    "piano", "violin", "guitar", "drums", "synthesizer", "orchestra",
    "choir", "vocals", "instrumental", "acapella", "acoustic", "electric",
    
    # Descriptions
    "soundtrack", "ost", "music", "audio", "sound design", "voice acting",
    "sound effects", "dynamic music", "adaptive music", "procedural music",
    "licensed music", "original score", "composer", "memorable themes"
}

SUBJECTIVE_QUALITY_KEYWORDS = {
    # Story & Writing (Positive)
    "great story", "amazing story", "good story", "well written", "compelling narrative", 
    "good writing", "interesting story", "engaging plot", "good characters", "character development",
    "emotional story", "touching story", "deep story", "meaningful story", "immersive story",
    
    # Story & Writing (Negative)  
    "bad story", "terrible story", "poor writing", "bad writing", "boring story",
    "confusing story", "cringe", "cringey", "bad dialogue", "cheesy dialogue", 
    "plot holes", "weak story", "generic story", "predictable story", "no story",
    
    # Technical Quality (Positive)
    "well optimized", "runs well", "smooth", "polished", "bug-free", "stable",
    "good performance", "optimized", "no bugs", "quality", "well made",
    
    # Technical Quality (Negative)
    "buggy", "bugs", "glitchy", "crashes", "broken", "unoptimized", "laggy",
    "performance issues", "technical issues", "messy", "unfinished", "rushed",
    "save corruption", "game breaking", "fps drops", "stuttering",
    
    # Gameplay Feel (Positive)
    "satisfying", "smooth gameplay", "responsive", "tight controls", "feels good",
    "addictive", "fun", "engaging", "enjoyable", "rewarding", "polished gameplay",
    
    # Gameplay Feel (Negative)
    "clunky", "janky", "awkward", "frustrating", "annoying", "tedious", "boring",
    "repetitive", "grindy", "unfair", "cheap", "unbalanced", "poorly designed",
    
    # Difficulty (Positive)
    "challenging", "fair difficulty", "well balanced", "good learning curve",
    "rewarding difficulty", "skill based", "strategic", "tactical",
    
    # Difficulty (Negative)
    "too easy", "too hard", "unfair difficulty", "artificial difficulty", "unbalanced",
    "cheap deaths", "rng heavy", "luck based", "trial and error", "poor balance",
    
    # Content & Value (Positive)
    "lots of content", "good value", "worth the price", "replay value", "replayable",
    "tons to do", "long game", "extensive", "complete", "full game",
    
    # Content & Value (Negative)
    "short", "not worth it", "overpriced", "lacking content", "empty", "shallow",
    "no replay value", "expensive", "incomplete", "cut content", "feels unfinished",
    
    # Innovation & Originality (Positive)
    "innovative", "original", "unique", "creative", "fresh", "new ideas",
    "different", "stands out", "clever", "inventive",
    
    # Innovation & Originality (Negative)
    "generic", "copy", "unoriginal", "been done before", "nothing new", "derivative",
    "cliche", "formulaic", "cookie cutter", "same old",
    
    # Emotional Response (Positive)
    "relaxing", "cozy", "comforting", "inspiring", "beautiful", "atmospheric",
    "immersive", "captivating", "charming", "delightful", "wholesome",
    
    # Emotional Response (Negative)
    "boring", "bland", "dull", "lifeless", "soulless", "uninspiring", "depressing",
    "dark", "disturbing", "uncomfortable", "annoying", "irritating"
}

TOXICITY_PHRASES = {
    "toxic", "grief", "flamed", "slur", "racism", "sexism", "trash community",
    "abandoned", "report system", "mute button", "valve doesn't care",
    "worst community", "matchmaking is broken", "smurfs", "trolls", "chain queuing"
}

def check_existing_reviews(db_path="steam_api.db", steam_appid=None):
    # Removed - we no longer skip games with existing reviews
    return False, []

def get_games_from_database(db_path="steam_api.db"):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT game_id, game_name, steam_appid FROM main_game")
        games = cursor.fetchall()
        
        conn.close()
        
        return [{"game_id": row[0], "game_name": row[1], "steam_appid": row[2]} for row in games]
    
    except Exception as e:
        print(f"error reading database: {e}")
        return []

def get_steam_tags_and_description(appid: int) -> tuple:
    """Get official Steam tags and game description"""
    try:
        url = f"https://store.steampowered.com/api/appdetails"
        params = {"appids": appid, "filters": "categories,genres,short_description,detailed_description"}
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if str(appid) not in data or not data[str(appid)]["success"]:
            return [], ""
        
        game_data = data[str(appid)]["data"]
        tags = []
        description = ""
        
        # Get genres
        if "genres" in game_data:
            for genre in game_data["genres"]:
                tags.append(genre["description"].lower())
        
        # Get categories (like multiplayer, co-op, etc.)
        if "categories" in game_data:
            for category in game_data["categories"]:
                cat_name = category["description"].lower()
                # Filter out less useful categories
                if cat_name not in ["steam achievements", "steam cloud", "steam trading cards", "full controller support"]:
                    tags.append(cat_name)
        
        # Get description (prefer short, fallback to detailed)
        if "short_description" in game_data and game_data["short_description"]:
            description = game_data["short_description"]
        elif "detailed_description" in game_data and game_data["detailed_description"]:
            # Clean HTML tags from detailed description and limit length
            import re
            description = re.sub(r'<[^>]+>', '', game_data["detailed_description"])
            if len(description) > 500:
                description = description[:500] + "..."
        
        return tags[:3], description  # Return top 3 most relevant tags and description
    
    except Exception as e:
        print(f"error fetching steam data for appid {appid}: {e}")
        return [], ""

def find_art_style_reviews(reviews: list) -> list:
    """Find reviews that mention art style or visual elements"""
    art_style_reviews = []
    
    for review in reviews:
        text = review['review'].lower()
        
        # Check for art style keywords
        art_mentions = 0
        mentioned_keywords = []
        
        for keyword in ART_STYLE_KEYWORDS:
            if keyword in text:
                art_mentions += text.count(keyword)
                mentioned_keywords.append(keyword)
        
        if art_mentions > 0:
            review['art_style_score'] = art_mentions
            review['art_keywords'] = mentioned_keywords
            art_style_reviews.append(review)
    
    # Sort by art style relevance and review quality
    art_style_reviews.sort(key=lambda r: (r['art_style_score'], r['voted_up'], r['playtime_hours']), reverse=True)
    
    return art_style_reviews[:3]  # Return top 3 art style reviews

def find_theme_reviews(reviews: list) -> list:
    """Find reviews that mention themes, settings, or story elements"""
    theme_reviews = []
    
    for review in reviews:
        text = review['review'].lower()
        
        # Check for theme keywords
        theme_mentions = 0
        mentioned_keywords = []
        
        for keyword in THEME_KEYWORDS:
            if keyword in text:
                theme_mentions += text.count(keyword)
                mentioned_keywords.append(keyword)
        
        if theme_mentions > 0:
            review['theme_score'] = theme_mentions
            review['theme_keywords'] = mentioned_keywords
            theme_reviews.append(review)
    
    # Sort by theme relevance and review quality
    theme_reviews.sort(key=lambda r: (r['theme_score'], r['voted_up'], r['playtime_hours']), reverse=True)
    
    return theme_reviews[:3]  # Return top 3 theme reviews

def find_music_reviews(reviews: list) -> list:
    """Find reviews that mention music, soundtrack, or audio"""
    music_reviews = []
    
    for review in reviews:
        text = review['review'].lower()
        
        # Check for music keywords
        music_mentions = 0
        mentioned_keywords = []
        
        for keyword in MUSIC_KEYWORDS:
            if keyword in text:
                music_mentions += text.count(keyword)
                mentioned_keywords.append(keyword)
        
        if music_mentions > 0:
            review['music_score'] = music_mentions
            review['music_keywords'] = mentioned_keywords
            music_reviews.append(review)
    
    # Sort by music relevance and review quality
    music_reviews.sort(key=lambda r: (r['music_score'], r['voted_up'], r['playtime_hours']), reverse=True)
    
    return music_reviews[:3]  # Return top 3 music reviews

def find_subjective_quality_reviews(reviews: list) -> list:
    """Find reviews that mention subjective quality aspects (positive and negative)"""
    quality_reviews = []
    
    for review in reviews:
        text = review['review'].lower()
        
        # Check for subjective quality keywords
        quality_mentions = 0
        mentioned_keywords = []
        positive_mentions = 0
        negative_mentions = 0
        
        for keyword in SUBJECTIVE_QUALITY_KEYWORDS:
            if keyword in text:
                count = text.count(keyword)
                quality_mentions += count
                mentioned_keywords.append(keyword)
                
                # Categorize as positive or negative based on keyword
                if any(pos_word in keyword for pos_word in ["great", "good", "amazing", "well", "smooth", "polished", "satisfying", "fun", "challenging", "worth", "innovative", "beautiful", "relaxing"]):
                    positive_mentions += count
                else:
                    negative_mentions += count
        
        if quality_mentions > 0:
            review['quality_score'] = quality_mentions
            review['quality_keywords'] = mentioned_keywords
            review['positive_sentiment_score'] = positive_mentions
            review['negative_sentiment_score'] = negative_mentions
            review['overall_sentiment'] = 'positive' if positive_mentions > negative_mentions else 'negative' if negative_mentions > positive_mentions else 'mixed'
            quality_reviews.append(review)
    
    # Sort by quality relevance and overall usefulness
    quality_reviews.sort(key=lambda r: (r['quality_score'], r['voted_up'], r['playtime_hours']), reverse=True)
    
    return quality_reviews[:5]  # Return top 5 quality-focused reviews

def mentions_toxicity(text: str, phrases=TOXICITY_PHRASES) -> bool:
    lower = text.lower()
    return any(p in lower for p in phrases)

def gameplay_keyword_stats(text: str, keywords=GAMEPLAY_KEYWORDS) -> dict:
    lower_text = text.lower()
    keyword_hits = {kw: lower_text.count(kw) for kw in keywords if kw in lower_text}
    total_hits = sum(keyword_hits.values())
    return {"total": total_hits, "matched_keywords": keyword_hits}

def is_comprehensible(text: str) -> bool:
    unique_chars = set(c.lower() for c in text if c.isalpha())
    if len(unique_chars) < 10:
        return False
    if re.search(r'(.)\1{30,}', text):
        return False
    return True

def is_complaint(text: str) -> bool:
    sentiment = analyzer.polarity_scores(text)
    return sentiment['compound'] < -0.5

def normalize_tag(tag: str, existing_tags: set) -> str:
    """Normalize a tag to match existing ones or create a consistent new one"""
    normalized = tag.strip().lower()
    
    # Check for exact matches first
    if normalized in existing_tags:
        return normalized
    
    # Check for similar tags (handle common variations)
    for existing in existing_tags:
        # Handle hyphenated vs non-hyphenated
        if normalized.replace('-', '') == existing.replace('-', ''):
            return existing
        if normalized.replace(' ', '-') == existing:
            return existing
        if normalized.replace('-', ' ') == existing:
            return existing
        
        # Handle plural/singular
        if normalized.rstrip('s') == existing or normalized == existing.rstrip('s'):
            return existing
    
    return normalized

def generate_hierarchical_tags(game_name: str, steam_tags: list, steam_description: str, reviews_text: list, art_style_reviews: list = None, theme_reviews: list = None, music_reviews: list = None, quality_reviews: list = None, retry_count: int = 0):
    art_style_context = ""
    theme_context = ""
    music_context = ""
    quality_context = ""
    description_context = ""
    
    if steam_description:
        description_context = f"\n\nsteam official description: {steam_description}"
    
    if art_style_reviews:
        art_style_context = f"\n\nart style mentions from reviews: {' | '.join([r['review'][:150] + '...' for r in art_style_reviews[:2]])}"
    
    if theme_reviews:
        theme_context = f"\n\ntheme/setting mentions from reviews: {' | '.join([r['review'][:150] + '...' for r in theme_reviews[:2]])}"
    
    if music_reviews:
        music_context = f"\n\nmusic/soundtrack mentions from reviews: {' | '.join([r['review'][:150] + '...' for r in music_reviews[:2]])}"
    
    if quality_reviews:
        quality_context = f"\n\nquality aspects mentioned in reviews: {' | '.join([r['review'][:150] + '...' for r in quality_reviews[:2]])}"
    
    system_prompt = f"""you are a game categorization expert. based on steam's official tags, official description, user reviews, and specific mentions of art, theme, music, and quality aspects, create a comprehensive classification system.

steam's official tags for this game: {', '.join(steam_tags)}

your task:
1. identify the MAIN GENRE (the primary category this game belongs to)
2. identify the SUB GENRE (more specific classification within the main genre)  
3. identify the SUB-SUB GENRE (very specific mechanics/style within the sub genre)
4. identify the ART STYLE (visual/aesthetic style of the game)
5. identify the THEME (setting, time period, story theme, or world type)
6. identify the MUSIC STYLE (soundtrack genre, mood, or musical approach)
7. create 2-4 UNIQUE TAGS that distinguish this game within its sub-sub genre
8. create 2-4 SUBJECTIVE TAGS based on reviewer opinions (include both positive AND negative aspects if mentioned)
9. percentage breakdown of core gameplay elements (must total 100%)

use steam's official description as the primary source of truth for genre classification, then supplement with user review insights for subjective aspects.

IMPORTANT: For subjective tags, include BOTH positive and negative quality aspects that reviewers consistently mention. 
Examples: "great-story", "buggy-launch", "addictive-gameplay", "poor-optimization", "beautiful-visuals", "repetitive-content"

consistency rules - ALWAYS use existing tags when appropriate:
- main genres ({len(TAG_CONTEXT['main_genres'])} existing): {', '.join(sorted(list(TAG_CONTEXT['main_genres']))[:15])}{'...' if len(TAG_CONTEXT['main_genres']) > 15 else ''}
- sub genres ({len(TAG_CONTEXT['sub_genres'])} existing): {', '.join(sorted(list(TAG_CONTEXT['sub_genres']))[:15])}{'...' if len(TAG_CONTEXT['sub_genres']) > 15 else ''}
- sub-sub genres ({len(TAG_CONTEXT['sub_sub_genres'])} existing): {', '.join(sorted(list(TAG_CONTEXT['sub_sub_genres']))[:15])}{'...' if len(TAG_CONTEXT['sub_sub_genres']) > 15 else ''}
- art styles ({len(TAG_CONTEXT['art_styles'])} existing): {', '.join(sorted(list(TAG_CONTEXT['art_styles']))[:15])}{'...' if len(TAG_CONTEXT['art_styles']) > 15 else ''}
- themes ({len(TAG_CONTEXT['themes'])} existing): {', '.join(sorted(list(TAG_CONTEXT['themes']))[:15])}{'...' if len(TAG_CONTEXT['themes']) > 15 else ''}
- music styles ({len(TAG_CONTEXT['music_styles'])} existing): {', '.join(sorted(list(TAG_CONTEXT['music_styles']))[:15])}{'...' if len(TAG_CONTEXT['music_styles']) > 15 else ''}
- unique tags ({len(TAG_CONTEXT['unique_tags'])} existing): {', '.join(sorted(list(TAG_CONTEXT['unique_tags']))[:20])}{'...' if len(TAG_CONTEXT['unique_tags']) > 20 else ''}
- subjective tags ({len(TAG_CONTEXT['subjective_tags'])} existing): {', '.join(sorted(list(TAG_CONTEXT['subjective_tags']))[:20])}{'...' if len(TAG_CONTEXT['subjective_tags']) > 20 else ''}

examples of full classification WITH subjective quality tags:
- dark souls 3: soulslike -> action-rpg -> stamina-based-combat -> realistic -> medieval-fantasy -> orchestral -> [challenging-but-fair, great-atmosphere, steep-learning-curve, rewarding-mastery]
- cyberpunk 2077: rpg -> action-rpg -> open-world -> realistic -> cyberpunk-future -> synthwave -> [ambitious-scope, buggy-launch, great-story, performance-issues]
- stardew valley: simulation -> farming-sim -> life-sim -> pixel-art -> rural-countryside -> folk -> [relaxing-gameplay, addictive-progression, cozy-atmosphere, wholesome-content]
- persona 5: jrpg -> turn-based -> social-simulation -> anime -> modern-tokyo -> jazz -> [stylish-presentation, excellent-story, long-playtime, time-management]

canonical subjective tag forms (include both positive AND negative):
- positive: "great-story", "addictive-gameplay", "beautiful-visuals", "smooth-controls", "challenging-but-fair", "excellent-music", "atmospheric", "polished", "innovative", "relaxing"
- negative: "buggy-launch", "poor-optimization", "repetitive-content", "bad-writing", "unfair-difficulty", "short-length", "overpriced", "clunky-controls", "generic-gameplay"

canonical forms (always use these):
- art styles: "pixel-art", "anime", "realistic", "cartoon", "minimalist", "hand-drawn"
- themes: "medieval-fantasy", "sci-fi", "cyberpunk", "modern", "post-apocalyptic", "urban", "rural"
- music: "orchestral", "electronic", "ambient", "jazz", "rock", "chiptune", "atmospheric"
- genres: "soulslike", "jrpg", "fps", "turn-based", "real-time"

response format:
MAIN_GENRE: [primary genre]
SUB_GENRE: [sub genre within main]
SUB_SUB_GENRE: [specific mechanics/style]
ART_STYLE: [visual/aesthetic style]
THEME: [setting/world/story theme]
MUSIC_STYLE: [soundtrack genre/mood]
UNIQUE_TAGS: tag1, tag2, tag3, tag4
SUBJECTIVE_TAGS: tag1, tag2, tag3, tag4
RATIOS: element1:percentage% element2:percentage% element3:percentage%"""
    
    combined_text = " ".join(reviews_text)
    if len(combined_text) > 400:
        combined_text = combined_text[:400] + "..."
    
    user_prompt = f"""game: {game_name}
steam official tags: {', '.join(steam_tags)}
user reviews sample: {combined_text}{description_context}{art_style_context}{theme_context}{music_context}{quality_context}

create comprehensive classification and tags for this game. use the official description as primary context, then supplement with review insights for subjective quality aspects."""
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=200
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Parse response
        main_genre_match = re.search(r'MAIN_GENRE:\s*(.+?)(?:\n|$)', response_text)
        sub_genre_match = re.search(r'SUB_GENRE:\s*(.+?)(?:\n|$)', response_text)
        sub_sub_genre_match = re.search(r'SUB_SUB_GENRE:\s*(.+?)(?:\n|$)', response_text)
        art_style_match = re.search(r'ART_STYLE:\s*(.+?)(?:\n|$)', response_text)
        theme_match = re.search(r'THEME:\s*(.+?)(?:\n|$)', response_text)
        music_style_match = re.search(r'MUSIC_STYLE:\s*(.+?)(?:\n|$)', response_text)
        unique_match = re.search(r'UNIQUE_TAGS:\s*(.+?)(?:\n|$)', response_text)
        subjective_match = re.search(r'SUBJECTIVE_TAGS:\s*(.+?)(?:\n|$)', response_text)
        ratios_match = re.search(r'RATIOS:\s*(.+?)(?:\n|$)', response_text)
        
        # Extract and normalize tags
        main_genre = normalize_tag(main_genre_match.group(1), TAG_CONTEXT['main_genres']) if main_genre_match else "unknown"
        sub_genre = normalize_tag(sub_genre_match.group(1), TAG_CONTEXT['sub_genres']) if sub_genre_match else "unknown"
        sub_sub_genre = normalize_tag(sub_sub_genre_match.group(1), TAG_CONTEXT['sub_sub_genres']) if sub_sub_genre_match else "unknown"
        art_style = normalize_tag(art_style_match.group(1), TAG_CONTEXT['art_styles']) if art_style_match else "unknown"
        theme = normalize_tag(theme_match.group(1), TAG_CONTEXT['themes']) if theme_match else "unknown"
        music_style = normalize_tag(music_style_match.group(1), TAG_CONTEXT['music_styles']) if music_style_match else "unknown"
        
        unique_tags = []
        if unique_match:
            raw_tags = [tag.strip() for tag in unique_match.group(1).split(',')]
            for tag in raw_tags:
                if tag:
                    normalized = normalize_tag(tag, TAG_CONTEXT['unique_tags'])
                    unique_tags.append(normalized)
                    TAG_CONTEXT['unique_tags'].add(normalized)
        
        subjective_tags = []
        if subjective_match:
            raw_tags = [tag.strip() for tag in subjective_match.group(1).split(',')]
            for tag in raw_tags:
                if tag:
                    normalized = normalize_tag(tag, TAG_CONTEXT['subjective_tags'])
                    subjective_tags.append(normalized)
                    TAG_CONTEXT['subjective_tags'].add(normalized)
        
        tag_ratios = {}
        if ratios_match:
            ratios_text = ratios_match.group(1)
            ratio_parts = re.findall(r'([^:]+):(\d+)%', ratios_text)
            for tag, percentage in ratio_parts:
                normalized_tag = normalize_tag(tag, TAG_CONTEXT['ratio_tags'])
                tag_ratios[normalized_tag] = int(percentage)
                TAG_CONTEXT['ratio_tags'].add(normalized_tag)
        
        # Add to context
        TAG_CONTEXT['main_genres'].add(main_genre)
        TAG_CONTEXT['sub_genres'].add(sub_genre)
        TAG_CONTEXT['sub_sub_genres'].add(sub_sub_genre)
        TAG_CONTEXT['art_styles'].add(art_style)
        TAG_CONTEXT['themes'].add(theme)
        TAG_CONTEXT['music_styles'].add(music_style)
        
        # Normalize ratios to 100%
        total = sum(tag_ratios.values())
        if total != 100 and total > 0:
            for tag in tag_ratios:
                tag_ratios[tag] = round(tag_ratios[tag] * 100 / total)
            
            diff = 100 - sum(tag_ratios.values())
            if diff != 0 and tag_ratios:
                largest_tag = max(tag_ratios.keys(), key=lambda k: tag_ratios[k])
                tag_ratios[largest_tag] += diff
        
        if not tag_ratios:
            tag_ratios = {"general": 100}
        
        return {
            "main_genre": main_genre,
            "sub_genre": sub_genre,
            "sub_sub_genre": sub_sub_genre,
            "art_style": art_style,
            "theme": theme,
            "music_style": music_style,
            "unique_tags": unique_tags,
            "subjective_tags": subjective_tags,
            "tag_ratios": tag_ratios
        }
        
    except Exception as e:
        error_str = str(e)
        
        if "insufficient_quota" in error_str:
            print(f"api quota exceeded for {game_name}. skipping...")
            return {
                "main_genre": "skipped",
                "sub_genre": "api-limit",
                "sub_sub_genre": "quota-exceeded",
                "art_style": "unknown",
                "theme": "unknown",
                "music_style": "unknown",
                "unique_tags": ["api-limit-reached"],
                "subjective_tags": ["skipped"],
                "tag_ratios": {"skipped": 100}
            }
        
        elif "rate_limit_exceeded" in error_str:
            if retry_count < 3:
                wait_time = 5 + (retry_count * 2)
                print(f"rate limit hit for {game_name}. waiting {wait_time} seconds before retry {retry_count + 1}/3...")
                time.sleep(wait_time)
                return generate_hierarchical_tags(game_name, steam_tags, steam_description, reviews_text, art_style_reviews, theme_reviews, music_reviews, quality_reviews, retry_count + 1)
            else:
                print(f"rate limit persists for {game_name} after 3 retries.")
                return {
                    "main_genre": "rate-limited",
                    "sub_genre": "api-error",
                    "sub_sub_genre": "retry-failed",
                    "art_style": "unknown",
                    "theme": "unknown",
                    "music_style": "unknown",
                    "unique_tags": ["rate-limit-exceeded"],
                    "subjective_tags": ["rate-limited"],
                    "tag_ratios": {"rate-limited": 100}
                }
        
        else:
            print(f"error generating tags for {game_name}: {error_str}")
            return {
                "main_genre": "error",
                "sub_genre": "unknown-error",
                "sub_sub_genre": "processing-failed",
                "art_style": "unknown",
                "theme": "unknown",
                "music_style": "unknown",
                "unique_tags": ["unknown-error"],
                "subjective_tags": ["error"],
                "tag_ratios": {"error": 100}
            }

def gather_steam_reviews(appid: int, count: int = 100) -> list:
    url = f"https://store.steampowered.com/appreviews/{appid}"
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
                "author_id": review["author"]["steamid"],
                "review": review["review"],
                "voted_up": review["voted_up"],
                "playtime_hours": round(review["author"]["playtime_forever"] / 60, 1),
                "date": datetime.fromtimestamp(review["timestamp_created"]).isoformat()
            })
        return reviews
    
    except Exception as e:
        print(f"error fetching reviews for appid {appid}: {e}")
        return []

def save_tag_context(filename='tag_context.json'):
    context_to_save = {
        'ratio_tags': sorted(list(TAG_CONTEXT['ratio_tags'])),
        'unique_tags': sorted(list(TAG_CONTEXT['unique_tags'])),
        'subjective_tags': sorted(list(TAG_CONTEXT['subjective_tags'])),
        'main_genres': sorted(list(TAG_CONTEXT['main_genres'])),
        'sub_genres': sorted(list(TAG_CONTEXT['sub_genres'])),
        'sub_sub_genres': sorted(list(TAG_CONTEXT['sub_sub_genres'])),
        'art_styles': sorted(list(TAG_CONTEXT['art_styles'])),
        'themes': sorted(list(TAG_CONTEXT['themes'])),
        'music_styles': sorted(list(TAG_CONTEXT['music_styles']))
    }
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(context_to_save, f, ensure_ascii=False, indent=2)

def load_tag_context(filename='tag_context.json'):
    global TAG_CONTEXT
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            saved_context = json.load(f)
            TAG_CONTEXT['ratio_tags'] = set(saved_context.get('ratio_tags', []))
            TAG_CONTEXT['unique_tags'] = set(saved_context.get('unique_tags', []))
            TAG_CONTEXT['subjective_tags'] = set(saved_context.get('subjective_tags', []))
            TAG_CONTEXT['main_genres'] = set(saved_context.get('main_genres', []))
            TAG_CONTEXT['sub_genres'] = set(saved_context.get('sub_genres', []))
            TAG_CONTEXT['sub_sub_genres'] = set(saved_context.get('sub_sub_genres', []))
            TAG_CONTEXT['art_styles'] = set(saved_context.get('art_styles', []))
            TAG_CONTEXT['themes'] = set(saved_context.get('themes', []))
            TAG_CONTEXT['music_styles'] = set(saved_context.get('music_styles', []))
            
        print(f"loaded existing tag context:")
        print(f"  - main genres: {len(TAG_CONTEXT['main_genres'])}")
        print(f"  - sub genres: {len(TAG_CONTEXT['sub_genres'])}")
        print(f"  - sub-sub genres: {len(TAG_CONTEXT['sub_sub_genres'])}")
        print(f"  - art styles: {len(TAG_CONTEXT['art_styles'])}")
        print(f"  - themes: {len(TAG_CONTEXT['themes'])}")
        print(f"  - music styles: {len(TAG_CONTEXT['music_styles'])}")
        print(f"  - unique tags: {len(TAG_CONTEXT['unique_tags'])}")
        print(f"  - subjective tags: {len(TAG_CONTEXT['subjective_tags'])}")
        print(f"  - ratio tags: {len(TAG_CONTEXT['ratio_tags'])}")
            
    except FileNotFoundError:
        print("warning: tag_context.json not found!")
        print("starting with empty context - creating new tag consistency system.")

def save_checkpoint(results, filename='checkpoint_steam_analysis.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"checkpoint saved: {len(results)} games processed")

def load_checkpoint(filename='checkpoint_steam_analysis.json'):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def main():
    if not os.getenv('OPENAI_API_KEY'):
        print("error: openai_api_key environment variable not set")
        print("please set it using: export openai_api_key='your-api-key'")
        return
    
    load_tag_context()
    
    results = load_checkpoint()
    processed_appids = set(results.keys())
    
    games = get_games_from_database()
    if not games:
        print("no games found in database!")
        return
    
    print(f"found {len(games)} games in database")
    print(f"already processed: {len(processed_appids)} games")
    
    remaining_games = []
    
    for g in games:
        appid_str = str(g["steam_appid"])
        
        if appid_str in processed_appids:
            continue
            
        remaining_games.append(g)
    
    print(f"remaining to process: {len(remaining_games)} games")
    
    if not remaining_games:
        print("no games need steam review processing!")
        return
    
    for i, game in enumerate(remaining_games, 1):
        appid = game["steam_appid"]
        game_name = game["game_name"]
        
        print(f"\n=== processing {i}/{len(remaining_games)}: {game_name} (appid: {appid}) ===")
        
        # Get Steam's official tags and description
        print("fetching steam official data...")
        steam_tags, steam_description = get_steam_tags_and_description(appid)
        if steam_tags:
            print(f"steam tags: {', '.join(steam_tags)}")
        else:
            print("no steam tags found")
        
        if steam_description:
            print(f"description: {steam_description[:100]}{'...' if len(steam_description) > 100 else ''}")
        else:
            print("no description found")
        
        raw_reviews = gather_steam_reviews(appid, 200)
        if not raw_reviews:
            print(f"no reviews found for {game_name}")
            results[str(appid)] = {
                "game_id": game["game_id"],
                "name": game_name,
                "steam_appid": appid,
                "steam_tags": steam_tags,
                "steam_description": steam_description,
                "reviews": [],
                "art_style_reviews": [],
                "theme_reviews": [],
                "music_reviews": [],
                "quality_reviews": [],
                "main_genre": "unknown",
                "sub_genre": "unknown",
                "sub_sub_genre": "unknown",
                "art_style": "unknown",
                "theme": "unknown",
                "music_style": "unknown",
                "unique_tags": [],
                "subjective_tags": [],
                "tag_ratios": {},
                "processing_date": datetime.now().isoformat(),
                "status": "no_reviews"
            }
            continue
        
        raw_reviews.sort(key=lambda r: r["playtime_hours"], reverse=True)
        
        # Find art style reviews first
        art_style_reviews = find_art_style_reviews(raw_reviews)
        print(f"found {len(art_style_reviews)} reviews mentioning art style")
        
        if art_style_reviews:
            print(f"art style keywords found: {', '.join(art_style_reviews[0]['art_keywords'][:3])}")
        
        # Find theme reviews
        theme_reviews = find_theme_reviews(raw_reviews)
        print(f"found {len(theme_reviews)} reviews mentioning themes")
        
        if theme_reviews:
            print(f"theme keywords found: {', '.join(theme_reviews[0]['theme_keywords'][:3])}")
        
        # Find music reviews
        music_reviews = find_music_reviews(raw_reviews)
        print(f"found {len(music_reviews)} reviews mentioning music")
        
        if music_reviews:
            print(f"music keywords found: {', '.join(music_reviews[0]['music_keywords'][:3])}")
        
        # Find quality-focused reviews
        quality_reviews = find_subjective_quality_reviews(raw_reviews)
        print(f"found {len(quality_reviews)} reviews mentioning quality aspects")
        
        if quality_reviews:
            print(f"quality keywords found: {', '.join(quality_reviews[0]['quality_keywords'][:3])}")
            print(f"sentiment: {quality_reviews[0]['overall_sentiment']}")
        
        filtered_reviews = []
        fallback_candidates = []
        
        for r in raw_reviews:
            text = r['review']
            if len(text) < 200 or r["playtime_hours"] < 1:
                continue
            if not is_comprehensible(text):
                continue

            stats = gameplay_keyword_stats(text)
            r["keyword_stats"] = stats

            if stats["total"] < 1:
                continue

            fallback_candidates.append(r)

            if stats["total"] < 6:
                continue
            if is_complaint(text) and mentions_toxicity(text):
                continue

            filtered_reviews.append(r)

        if not filtered_reviews and fallback_candidates:
            best_fallback = sorted(
                fallback_candidates,
                key=lambda r: (r["voted_up"], r["keyword_stats"]["total"]),
                reverse=True
            )[0]
            filtered_reviews.append(best_fallback)

        top_reviews = filtered_reviews[:3]
        
        # Generate hierarchical tags
        tag_data = {
            "main_genre": "unknown",
            "sub_genre": "unknown",
            "sub_sub_genre": "unknown",
            "art_style": "unknown",
            "theme": "unknown",
            "music_style": "unknown",
            "unique_tags": [],
            "subjective_tags": [],
            "tag_ratios": {}
        }
        
        if top_reviews or steam_tags or steam_description:
            review_texts = [r["review"] for r in top_reviews]
            tag_data = generate_hierarchical_tags(game_name, steam_tags, steam_description, review_texts, art_style_reviews, theme_reviews, music_reviews, quality_reviews)
            
            print(f"hierarchy: {tag_data['main_genre']} -> {tag_data['sub_genre']} -> {tag_data['sub_sub_genre']}")
            print(f"art style: {tag_data['art_style']}")
            print(f"theme: {tag_data['theme']}")
            print(f"music style: {tag_data['music_style']}")
            print(f"unique tags: {', '.join(tag_data['unique_tags'])}")
            print(f"subjective tags: {', '.join(tag_data['subjective_tags'])}")
            print(f"breakdown: {' '.join([f'{tag}:{percent}%' for tag, percent in tag_data['tag_ratios'].items()])}")
        
        results[str(appid)] = {
            "game_id": game["game_id"],
            "name": game_name,
            "steam_appid": appid,
            "steam_tags": steam_tags,
            "steam_description": steam_description,
            "reviews": top_reviews,
            "art_style_reviews": art_style_reviews,
            "theme_reviews": theme_reviews,
            "music_reviews": music_reviews,
            "quality_reviews": quality_reviews,
            "main_genre": tag_data["main_genre"],
            "sub_genre": tag_data["sub_genre"],
            "sub_sub_genre": tag_data["sub_sub_genre"],
            "art_style": tag_data["art_style"],
            "theme": tag_data["theme"],
            "music_style": tag_data["music_style"],
            "unique_tags": tag_data["unique_tags"],
            "subjective_tags": tag_data["subjective_tags"],
            "tag_ratios": tag_data["tag_ratios"],
            "processing_date": datetime.now().isoformat(),
            "status": "processed"
        }
        
        print(f"found {len(top_reviews)} quality reviews")
        
        if i % 10 == 0:
            save_checkpoint(results)
            save_tag_context()
            time.sleep(1)
    
    final_output_file = 'steam_games_with_hierarchical_tags.json'
    with open(final_output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    save_tag_context()
    
    print(f"\n{'='*80}")
    print(f"hierarchical analysis complete!")
    print(f"total games processed: {len(results)}")
    print(f"results saved to: {final_output_file}")
    
    print(f"\nfinal tag statistics:")
    print(f"main genres: {len(TAG_CONTEXT['main_genres'])}")
    print(f"sub genres: {len(TAG_CONTEXT['sub_genres'])}")
    print(f"sub-sub genres: {len(TAG_CONTEXT['sub_sub_genres'])}")
    print(f"art styles: {len(TAG_CONTEXT['art_styles'])}")
    print(f"themes: {len(TAG_CONTEXT['themes'])}")
    print(f"music styles: {len(TAG_CONTEXT['music_styles'])}")
    print(f"unique tags: {len(TAG_CONTEXT['unique_tags'])}")
    print(f"subjective tags: {len(TAG_CONTEXT['subjective_tags'])}")
    print(f"ratio tags: {len(TAG_CONTEXT['ratio_tags'])}")
    
    print(f"\ntag context saved to tag_context.json for consistency!")
    print("database ready for similarity-based game recommendations!")
    
    if os.path.exists('checkpoint_steam_analysis.json'):
        os.remove('checkpoint_steam_analysis.json')
        print("checkpoint file removed")

if __name__ == "__main__":
    main()