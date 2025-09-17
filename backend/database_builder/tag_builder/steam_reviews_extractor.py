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
    'main_genres': set()
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

TOXICITY_PHRASES = {
    "toxic", "grief", "flamed", "slur", "racism", "sexism", "trash community",
    "abandoned", "report system", "mute button", "valve doesn't care",
    "worst community", "matchmaking is broken", "smurfs", "trolls", "chain queuing"
}

def check_existing_reviews(db_path="steam_api.db", steam_appid=None):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM ACG_scores WHERE steam_appid = ?", (steam_appid,))
        acg_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM ign_scores WHERE steam_appid = ?", (steam_appid,))
        ign_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM GameRanx_scores WHERE steam_appid = ?", (steam_appid,))
        gameranx_count = cursor.fetchone()[0]
        
        conn.close()
        
        has_reviews = (acg_count > 0) or (ign_count > 0) or (gameranx_count > 0)
        
        if has_reviews:
            sources = []
            if acg_count > 0: sources.append("ACG")
            if ign_count > 0: sources.append("IGN") 
            if gameranx_count > 0: sources.append("GameRanx")
            return True, sources
        
        return False, []
    
    except Exception as e:
        print(f"error checking existing reviews for appid {steam_appid}: {e}")
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

def generate_game_tags_with_ratios(game_name: str, reviews_text: list, retry_count: int = 0):
    system_prompt = f"""you are a game categorization expert. based on steam user reviews, you analyze games and provide:

1. a percentage breakdown of the game's core elements (must total 100%)
2. the main genre classification
3. unique searchable tags that distinguish this game within its genre (2-4 tags)
4. subjective tags that capture the reviewers' opinions (2-4 tags)

critical consistency rules:
- always use lowercase for all tags
- never use plurals (use "horror" not "horrors")
- if a similar tag exists in the existing tags below, use it exactly as written
- for unique tags, use neutral descriptive terms only
- for subjective tags, capture the reviewers' opinions (can include quality assessments)
- for ratio tags, use core gameplay elements that can be weighted

existing tags to reuse (use these exactly when appropriate):
- ratio tags ({len(TAG_CONTEXT['ratio_tags'])} existing): {', '.join(sorted(list(TAG_CONTEXT['ratio_tags']))[:20])}{'...' if len(TAG_CONTEXT['ratio_tags']) > 20 else ''}
- unique tags ({len(TAG_CONTEXT['unique_tags'])} existing): {', '.join(sorted(list(TAG_CONTEXT['unique_tags']))[:20])}{'...' if len(TAG_CONTEXT['unique_tags']) > 20 else ''}
- subjective tags ({len(TAG_CONTEXT['subjective_tags'])} existing): {', '.join(sorted(list(TAG_CONTEXT['subjective_tags']))[:20])}{'...' if len(TAG_CONTEXT['subjective_tags']) > 20 else ''}
- main genres ({len(TAG_CONTEXT['main_genres'])} existing): {', '.join(sorted(list(TAG_CONTEXT['main_genres']))[:15])}{'...' if len(TAG_CONTEXT['main_genres']) > 15 else ''}

for common concepts, always use these canonical forms:
  * "horror" (not "scary", "frightening", "spooky")
  * "rpg" (not "role-playing", "role playing")
  * "fps" (not "first-person", "shooter")
  * "anime" (not "japanese animation")
  * "platformer" (not "platforming")
  * "multiplayer" (not "multi-player")
  * "co-op" (not "cooperative", "coop")

response format:
RATIOS: element1:percentage% element2:percentage% element3:percentage%
MAIN_GENRE: [single genre classification]
UNIQUE_TAGS: tag1, tag2, tag3
SUBJECTIVE_TAGS: tag1, tag2, tag3

example:
RATIOS: combat:40% exploration:30% story:30%
MAIN_GENRE: action rpg
UNIQUE_TAGS: open-world, crafting-system, multiplayer
SUBJECTIVE_TAGS: addictive-gameplay, great-story, polished"""
    
    combined_text = " ".join(reviews_text)
    if len(combined_text) > 1000:
        combined_text = combined_text[:1000] + "..."
    
    user_prompt = f"""game: {game_name}

steam user reviews: {combined_text}

analyze this game based on the user reviews and provide:
1. a percentage breakdown of its core elements (must total 100%)
2. its main genre classification  
3. unique searchable tags that distinguish it within its genre (2-4 tags, objective only)
4. subjective tags that capture the reviewers' opinions (2-4 tags, can include quality assessments)"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=150
        )
        
        response_text = response.choices[0].message.content.strip()
        
        ratios_match = re.search(r'RATIOS:\s*(.+?)(?:\n|$)', response_text)
        genre_match = re.search(r'MAIN_GENRE:\s*(.+?)(?:\n|$)', response_text)
        unique_match = re.search(r'UNIQUE_TAGS:\s*(.+?)(?:\n|$)', response_text)
        subjective_match = re.search(r'SUBJECTIVE_TAGS:\s*(.+?)(?:\n|$)', response_text)
        
        tag_ratios = {}
        main_genre = "unknown"
        unique_tags = []
        subjective_tags = []
        
        if ratios_match:
            ratios_text = ratios_match.group(1)
            ratio_parts = re.findall(r'([^:]+):(\d+)%', ratios_text)
            for tag, percentage in ratio_parts:
                normalized_tag = tag.strip().lower()
                tag_ratios[normalized_tag] = int(percentage)
                TAG_CONTEXT['ratio_tags'].add(normalized_tag)
        
        if genre_match:
            main_genre = genre_match.group(1).strip().lower()
            TAG_CONTEXT['main_genres'].add(main_genre)
        
        if unique_match:
            unique_text = unique_match.group(1)
            raw_tags = [tag.strip().lower() for tag in unique_text.split(',')]
            for tag in raw_tags:
                if tag and tag not in unique_tags:
                    unique_tags.append(tag)
                    TAG_CONTEXT['unique_tags'].add(tag)
        
        if subjective_match:
            subjective_text = subjective_match.group(1)
            raw_tags = [tag.strip().lower() for tag in subjective_text.split(',')]
            for tag in raw_tags:
                if tag and tag not in subjective_tags:
                    subjective_tags.append(tag)
                    TAG_CONTEXT['subjective_tags'].add(tag)
        
        total = sum(tag_ratios.values())
        if total != 100 and total > 0:
            for tag in tag_ratios:
                tag_ratios[tag] = round(tag_ratios[tag] * 100 / total)
            
            diff = 100 - sum(tag_ratios.values())
            if diff != 0 and tag_ratios:
                largest_tag = max(tag_ratios.keys(), key=lambda k: tag_ratios[k])
                tag_ratios[largest_tag] += diff
        
        if not tag_ratios:
            print(f"warning: could not parse ratios for {game_name}, using fallback")
            tag_ratios = {"general": 100}
        
        return tag_ratios, main_genre, unique_tags, subjective_tags
        
    except Exception as e:
        error_str = str(e)
        
        if "insufficient_quota" in error_str:
            print(f"api quota exceeded for {game_name}. skipping...")
            return {"skipped": 100}, "skipped", ["api-limit-reached"], ["skipped"]
        
        elif "rate_limit_exceeded" in error_str:
            if retry_count < 3:
                wait_time = 5 + (retry_count * 2)
                print(f"rate limit hit for {game_name}. waiting {wait_time} seconds before retry {retry_count + 1}/3...")
                time.sleep(wait_time)
                return generate_game_tags_with_ratios(game_name, reviews_text, retry_count + 1)
            else:
                print(f"rate limit persists for {game_name} after 3 retries.")
                return {"rate-limited": 100}, "rate_limited", ["rate-limit-exceeded"], ["rate-limited"]
        
        else:
            print(f"error generating tags for {game_name}: {error_str}")
            return {"error": 100}, "error", ["unknown-error"], ["error"]

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
        'main_genres': sorted(list(TAG_CONTEXT['main_genres']))
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
            
        print(f"loaded existing tag context:")
        print(f"  - ratio tags: {len(TAG_CONTEXT['ratio_tags'])}")
        print(f"  - unique tags: {len(TAG_CONTEXT['unique_tags'])}")
        print(f"  - subjective tags: {len(TAG_CONTEXT['subjective_tags'])}")
        print(f"  - main genres: {len(TAG_CONTEXT['main_genres'])}")
            
    except FileNotFoundError:
        print("warning: tag_context.json not found!")
        print("make sure the file exists in the same directory for tag consistency.")
        print("starting with empty context - tags may not be consistent with your existing system.")

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
    skipped_existing_reviews = 0
    
    for g in games:
        appid_str = str(g["steam_appid"])
        
        if appid_str in processed_appids:
            continue
            
        has_reviews, sources = check_existing_reviews("steam_api.db", g["steam_appid"])
        if has_reviews:
            skipped_existing_reviews += 1
            if skipped_existing_reviews <= 5:
                print(f"skipping {g['game_name']} - already has reviews from: {', '.join(sources)}")
            continue
            
        remaining_games.append(g)
    
    print(f"skipped {skipped_existing_reviews} games with existing reviews (acg/ign/gameranx)")
    print(f"remaining to process: {len(remaining_games)} games")
    
    if skipped_existing_reviews > 5:
        print(f"... and {skipped_existing_reviews - 5} more games with existing reviews")
    
    if not remaining_games:
        print("no games need steam review processing!")
        return
    
    for i, game in enumerate(remaining_games, 1):
        appid = game["steam_appid"]
        game_name = game["game_name"]
        
        print(f"\n=== processing {i}/{len(remaining_games)}: {game_name} (appid: {appid}) ===")
        
        has_reviews, sources = check_existing_reviews("steam_api.db", appid)
        if has_reviews:
            print(f"skipping - found existing reviews from: {', '.join(sources)}")
            results[str(appid)] = {
                "game_id": game["game_id"],
                "name": game_name,
                "steam_appid": appid,
                "reviews": [],
                "tag_ratios": {},
                "main_genre": "unknown",
                "unique_tags": [],
                "subjective_tags": [],
                "processing_date": datetime.now().isoformat(),
                "status": "has_existing_reviews",
                "existing_sources": sources
            }
            continue
        
        raw_reviews = gather_steam_reviews(appid, 200)
        if not raw_reviews:
            print(f"no reviews found for {game_name}")
            results[str(appid)] = {
                "game_id": game["game_id"],
                "name": game_name,
                "steam_appid": appid,
                "reviews": [],
                "tag_ratios": {},
                "main_genre": "unknown",
                "unique_tags": [],
                "subjective_tags": [],
                "processing_date": datetime.now().isoformat(),
                "status": "no_reviews"
            }
            continue
        
        raw_reviews.sort(key=lambda r: r["playtime_hours"], reverse=True)
        
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
        
        tag_ratios = {}
        main_genre = "unknown"
        unique_tags = []
        subjective_tags = []
        
        if top_reviews:
            review_texts = [r["review"] for r in top_reviews]
            tag_ratios, main_genre, unique_tags, subjective_tags = generate_game_tags_with_ratios(game_name, review_texts)
            
            print(f"main genre: {main_genre}")
            print(f"unique tags: {', '.join(unique_tags)}")
            print(f"subjective tags: {', '.join(subjective_tags)}")
            print(f"breakdown: {' '.join([f'{tag}:{percent}%' for tag, percent in tag_ratios.items()])}")
        
        results[str(appid)] = {
            "game_id": game["game_id"],
            "name": game_name,
            "steam_appid": appid,
            "reviews": top_reviews,
            "tag_ratios": tag_ratios,
            "main_genre": main_genre,
            "unique_tags": unique_tags,
            "subjective_tags": subjective_tags,
            "processing_date": datetime.now().isoformat(),
            "status": "processed"
        }
        
        print(f"found {len(top_reviews)} quality reviews")
        
        if i % 10 == 0:
            save_checkpoint(results)
            save_tag_context()
            time.sleep(1)
    
    final_output_file = 'steam_games_with_tags.json'
    with open(final_output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    save_tag_context()
    
    print(f"\n{'='*80}")
    print(f"analysis complete!")
    print(f"total games processed: {len(results)}")
    print(f"results saved to: {final_output_file}")
    
    print(f"\nfinal tag statistics:")
    print(f"ratio tags: {len(TAG_CONTEXT['ratio_tags'])}")
    print(f"unique tags: {len(TAG_CONTEXT['unique_tags'])}")
    print(f"subjective tags: {len(TAG_CONTEXT['subjective_tags'])}")
    print(f"main genres: {len(TAG_CONTEXT['main_genres'])}")
    
    print(f"\ntag context updated and saved to tag_context.json")
    print("this maintains consistency with your existing acg/youtube tagging system!")
    
    if os.path.exists('checkpoint_steam_analysis.json'):
        os.remove('checkpoint_steam_analysis.json')
        print("checkpoint file removed")

if __name__ == "__main__":
    main()