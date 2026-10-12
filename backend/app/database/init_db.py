"""
Database initialization script.
Run this to create the database tables.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database.session import init_db
from app.core.logging import setup_logging

if __name__ == "__main__":
    logger = setup_logging()
    logger.info("Initializing VISHWAS database...")
    init_db()
    logger.info("Database initialization complete!")
