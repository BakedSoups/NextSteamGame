"""
Steam Recommender Flask Application
Main application entry point with refactored modular architecture
"""
import os
from flask import Flask

from backend.api import api
from backend.config import WEB_CONFIG, validate_config, ensure_directories


def create_app():
    """Application factory"""
    # Validate configuration
    validate_config()
    ensure_directories()

    app = Flask(__name__,
                template_folder='frontend/templates',
                static_folder='frontend/static')

    # Configuration
    app.secret_key = WEB_CONFIG['secret_key']

    # Register blueprints
    app.register_blueprint(api)

    return app


if __name__ == '__main__':
    app = create_app()

    # Check for required databases
    from backend.config import DATABASE_CONFIG

    recommendations_db = str(DATABASE_CONFIG['recommendations_db'])
    steam_api_db = str(DATABASE_CONFIG['steam_api_db'])
    vectorizer_path = str(DATABASE_CONFIG['vectorizer_path'])

    if not os.path.exists(recommendations_db):
        print(f"❌ {recommendations_db} not found!")
        print("Please run the database builder first:")
        print("python backend/database_builder/pipeline_orchestrator.py")
        exit(1)
    else:
        print(f"✅ Found recommendations database: {recommendations_db}")

    if not os.path.exists(steam_api_db):
        print(f"⚠️ {steam_api_db} not found - images and pricing will use defaults")
    else:
        print(f"✅ Found Steam API database: {steam_api_db}")

    if not os.path.exists(vectorizer_path):
        print(f"⚠️ {vectorizer_path} not found - will use tag-based similarity")
    else:
        print(f"✅ Found TF-IDF vectorizer: {vectorizer_path}")

    print(f"\n🚀 Starting Steam Recommender on http://{WEB_CONFIG['host']}:{WEB_CONFIG['port']}")
    app.run(
        host=WEB_CONFIG['host'],
        port=WEB_CONFIG['port'],
        debug=WEB_CONFIG['debug']
    )