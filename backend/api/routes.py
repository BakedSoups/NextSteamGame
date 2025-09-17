"""
Flask routes for the Steam Recommender API
"""
import os
import sqlite3
import traceback
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify

from backend.core import SQLiteGameSearcher, SimilarityEngine
from backend.config import DATABASE_CONFIG

# Create blueprint
api = Blueprint('api', __name__)

# Initialize game searcher
game_searcher = SQLiteGameSearcher()


@api.route('/')
def index():
    """Home page"""
    session.clear()
    return render_template('index.html')


@api.route('/search', methods=['POST'])
def search():
    """Search for a game and redirect to preferences"""
    search_query = request.form.get('search_query', '')
    if not search_query:
        return redirect(url_for('api.index'))

    matches = game_searcher.find_game_by_name(search_query)

    if not matches:
        return redirect(url_for('api.index'))

    # Take the best match
    best_match = matches[0]
    target_appid = best_match['steam_appid']

    # Get full game details
    reference_game = game_searcher.get_game_details(target_appid)
    if not reference_game:
        return redirect(url_for('api.index'))

    # Get available preferences
    preferences = game_searcher.get_available_preferences(target_appid)

    # Store in session
    session['reference_game'] = reference_game
    session['target_appid'] = target_appid
    session['available_preferences'] = preferences

    return render_template('preference_hierarchical.html',
                          reference_game=reference_game,
                          preferences=preferences)


@api.route('/recommend', methods=['POST'])
def recommend():
    """Generate recommendations based on user preferences"""
    target_appid = session.get('target_appid')
    reference_game = session.get('reference_game', {})

    if not target_appid:
        return redirect(url_for('api.index'))

    # Get user preferences from form
    user_preferences = {
        'aesthetics': {},
        'preferred_tags': [],
        'preferred_steam_tags': []
    }

    # Aesthetic preferences
    for aesthetic in ['art_style', 'theme', 'music_style']:
        pref_value = request.form.get(f'prefer_{aesthetic}')
        if pref_value:
            user_preferences['aesthetics'][aesthetic] = pref_value

    # Tag preferences
    preferred_tags = request.form.getlist('preferred_tags')
    user_preferences['preferred_tags'] = preferred_tags

    # Steam tag preferences
    preferred_steam_tags = request.form.getlist('preferred_steam_tags')
    user_preferences['preferred_steam_tags'] = preferred_steam_tags

    print(f"User preferences: {user_preferences}")

    # Find similar games using similarity engine
    similarity_engine = SimilarityEngine(str(DATABASE_CONFIG['recommendations_db']))
    similar_games = similarity_engine.find_similar_games(target_appid, user_preferences, limit=10)

    return render_template('results_hierarchical.html',
                          games=similar_games,
                          reference_game=reference_game,
                          user_preferences=user_preferences)


@api.route('/api/search', methods=['GET'])
def api_search():
    """API endpoint for search suggestions"""
    search_query = request.args.get('search_query', request.args.get('q', ''))

    if len(search_query) < 2:
        if request.headers.get('HX-Request'):
            return render_template('partials/search_results.html', games=[])
        return jsonify([])

    try:
        matches = game_searcher.find_game_by_name(search_query, limit=10)

        if request.headers.get('HX-Request') or 'text/html' in request.headers.get('Accept', ''):
            return render_template('partials/search_results.html', games=matches)

        results = []
        for match in matches:
            results.append({
                'id': match['steam_appid'],
                'name': match['name'],
                'image': match['header_image'],
                'genre': f"{match['main_genre']} → {match['sub_genre']}",
                'data_source': 'hierarchical'
            })

        return jsonify(results)
    except Exception as e:
        print(f"Error in API search: {str(e)}")
        traceback.print_exc()
        if request.headers.get('HX-Request'):
            return render_template('partials/search_results.html', games=[])
        return jsonify([])


@api.route('/debug/game/<int:steam_appid>')
def debug_game(steam_appid):
    """Debug endpoint to see game details"""
    game = game_searcher.get_game_details(steam_appid)
    preferences = game_searcher.get_available_preferences(steam_appid)

    return jsonify({
        'game': game,
        'preferences': preferences
    })


@api.route('/debug/stats')
def debug_stats():
    """Debug endpoint to see database statistics"""
    recommendations_db = str(DATABASE_CONFIG['recommendations_db'])
    conn = sqlite3.connect(recommendations_db)
    cursor = conn.cursor()

    try:
        stats = {}

        # Basic counts
        cursor.execute("SELECT COUNT(*) FROM games")
        stats['total_games'] = cursor.fetchone()[0]

        # Top hierarchies
        cursor.execute("""
        SELECT main_genre, sub_genre, sub_sub_genre, COUNT(*) as count
        FROM games
        GROUP BY main_genre, sub_genre, sub_sub_genre
        ORDER BY count DESC
        LIMIT 20
        """)
        stats['top_hierarchies'] = cursor.fetchall()

        # Popular tags
        cursor.execute("""
        SELECT tag, COUNT(*) as count
        FROM unique_tags
        GROUP BY tag
        ORDER BY count DESC
        LIMIT 20
        """)
        stats['popular_unique_tags'] = cursor.fetchall()

        return jsonify(stats)
    finally:
        conn.close()


@api.route('/health')
def health_check():
    """Health check endpoint"""
    recommendations_db = str(DATABASE_CONFIG['recommendations_db'])
    steam_api_db = str(DATABASE_CONFIG['steam_api_db'])
    vectorizer_path = str(DATABASE_CONFIG['vectorizer_path'])

    status = {
        'status': 'healthy',
        'databases': {
            'recommendations_db': os.path.exists(recommendations_db),
            'steam_api_db': os.path.exists(steam_api_db)
        },
        'vectorizer': os.path.exists(vectorizer_path)
    }

    return jsonify(status)