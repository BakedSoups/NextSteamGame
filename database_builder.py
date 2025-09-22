#!/usr/bin/env python3
"""
Steam Recommender Database Builder - Modular Pipeline Entry Point

This is the new main entry point for the modular database builder.
It replaces the old pipeline_orchestrator.py with enhanced functionality.

Usage:
    python database_builder.py                    # Run full pipeline
    python database_builder.py --stage data_collection  # Run specific stage
    python database_builder.py --status           # Show pipeline status
    python database_builder.py --reset            # Reset pipeline
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import the modular orchestrator
from backend.database_builder.pipeline.orchestrator import main

if __name__ == "__main__":
    main()