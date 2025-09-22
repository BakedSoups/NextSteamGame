#!/usr/bin/env python3
"""
Test environment setup for Steam Recommender
Run this to verify your environment variables are correctly configured
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_environment():
    """Test if environment is properly configured"""
    print("Steam Recommender - Environment Test")
    print("=" * 50)

    # Test 1: Python version
    python_version = sys.version.split()[0]
    print(f"Python Version: {python_version}")
    if sys.version_info < (3, 8):
        print("  ⚠️  Warning: Python 3.8+ recommended")
    else:
        print("  ✅ Python version OK")

    # Test 2: Check if .env file exists
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        print(f"\n.env File: Found at {env_file}")
        print("  ✅ .env file exists")
    else:
        print(f"\n.env File: Not found")
        print("  ℹ️  Create one with: cp .env.example .env")

    # Test 3: Load configuration
    try:
        from backend.config import settings
        print("\n✅ Configuration loaded successfully")
    except Exception as e:
        print(f"\n❌ Error loading configuration: {e}")
        return False

    # Test 4: Check OpenAI API key
    api_key = settings.API_CONFIG.get('openai_api_key', '')
    if api_key and api_key != 'your-openai-api-key-here':
        print(f"\nOpenAI API Key: {'*' * 20}...{api_key[-4:]}")
        print("  ✅ OpenAI API key configured")
    else:
        print("\nOpenAI API Key: Not configured")
        print("  ⚠️  Required for database building")
        print("  ℹ️  Get your key from: https://platform.openai.com/api-keys")

    # Test 5: Check Flask configuration
    flask_key = settings.WEB_CONFIG.get('secret_key', '')
    if flask_key and flask_key != 'steam_game_recommender_secret_key':
        print(f"\nFlask Secret Key: Configured")
        print("  ✅ Flask secret key set")
    else:
        print("\nFlask Secret Key: Using default")
        print("  ⚠️  Set FLASK_SECRET_KEY for production")

    # Test 6: Check database files
    print("\n" + "=" * 50)
    print("Database Status:")

    recommendations_db = settings.DATABASE_CONFIG['recommendations_db']
    steam_api_db = settings.DATABASE_CONFIG['steam_api_db']
    vectorizer_path = settings.DATABASE_CONFIG['vectorizer_path']

    if recommendations_db.exists():
        size_mb = recommendations_db.stat().st_size / (1024 * 1024)
        print(f"  ✅ Recommendations DB: {size_mb:.1f} MB")
    else:
        print(f"  ❌ Recommendations DB: Not found")
        print(f"     Run: python -m backend.database_builder.pipeline_orchestrator")

    if steam_api_db.exists():
        size_mb = steam_api_db.stat().st_size / (1024 * 1024)
        print(f"  ✅ Steam API DB: {size_mb:.1f} MB")
    else:
        print(f"  ⚠️  Steam API DB: Not found (images will use defaults)")

    if vectorizer_path.exists():
        size_mb = vectorizer_path.stat().st_size / (1024 * 1024)
        print(f"  ✅ Vectorizer: {size_mb:.1f} MB")
    else:
        print(f"  ⚠️  Vectorizer: Not found (will use tag-based similarity)")

    # Test 7: Check dependencies
    print("\n" + "=" * 50)
    print("Dependencies:")

    try:
        import flask
        print(f"  ✅ Flask: {flask.__version__}")
    except ImportError:
        print("  ❌ Flask: Not installed")

    try:
        import openai
        print(f"  ✅ OpenAI: {openai.__version__}")
    except ImportError:
        print("  ❌ OpenAI: Not installed")

    try:
        import numpy
        print(f"  ✅ NumPy: {numpy.__version__}")
    except ImportError:
        print("  ❌ NumPy: Not installed")

    try:
        import sklearn
        print(f"  ✅ Scikit-learn: {sklearn.__version__}")
    except ImportError:
        print("  ❌ Scikit-learn: Not installed")

    print("\n" + "=" * 50)

    # Summary
    if api_key and api_key != 'your-openai-api-key-here':
        print("\n✅ Environment is ready for database building!")
        print("   Run: python -m backend.database_builder.pipeline_orchestrator")
    else:
        print("\n⚠️  Environment partially configured")
        print("   - Web app will work with existing databases")
        print("   - OpenAI API key needed for database building")

    if recommendations_db.exists():
        print("\n✅ Ready to run the web app!")
        print("   Run: python app.py")

    return True

if __name__ == "__main__":
    test_environment()