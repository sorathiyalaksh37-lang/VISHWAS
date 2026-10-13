"""
Phase 7 Migration: Add authentication and ownership.

Adds:
- users table
- owner_id to call_records
- owner_id to contacts

IMPORTANT: Run this BEFORE starting the server with Phase 7 code.
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.models.user import User
from app.auth.security import get_password_hash
from app.database.base import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """Run Phase 7 migration."""
    engine = create_engine(settings.database_url)
    inspector = inspect(engine)
    
    # Import all models
    from app.models.user import User  # noqa
    from app.models.call import CallRecord, AnalysisReport, Contact  # noqa
    
    with engine.begin() as conn:
        # Check if users table exists
        if 'users' not in inspector.get_table_names():
            logger.info("Creating users table...")
            Base.metadata.tables['users'].create(engine)
            logger.info("✓ users table created")
        else:
            logger.info("users table already exists")
        
        # Check if owner_id column exists in call_records
        call_record_columns = [c['name'] for c in inspector.get_columns('call_records')]
        if 'owner_id' not in call_record_columns:
            logger.info("Adding owner_id to call_records...")
            
            # Check if there are existing records
            result = conn.execute(text("SELECT COUNT(*) FROM call_records"))
            count = result.scalar()
            
            if count > 0:
                logger.warning(f"Found {count} existing call_records without owners.")
                logger.warning("These records will be deleted as they cannot be associated with a user.")
                response = input("Delete existing call records? (yes/no): ")
                if response.lower() != 'yes':
                    logger.error("Migration cancelled. Please backup and clear call_records manually.")
                    return False
                
                # Delete existing records
                conn.execute(text("DELETE FROM analysis_reports"))
                conn.execute(text("DELETE FROM call_records"))
                logger.info("Existing records deleted")
            
            # Add the column
            conn.execute(text(
                "ALTER TABLE call_records ADD COLUMN owner_id VARCHAR(36) NOT NULL DEFAULT 'temp'"
            ))
            conn.execute(text(
                "CREATE INDEX ix_call_records_owner_id ON call_records (owner_id)"
            ))
            logger.info("✓ owner_id added to call_records")
        else:
            logger.info("owner_id already exists in call_records")
        
        # Check if owner_id column exists in contacts
        contact_columns = [c['name'] for c in inspector.get_columns('contacts')]
        if 'owner_id' not in contact_columns:
            logger.info("Adding owner_id to contacts...")
            
            # Check for existing contacts
            result = conn.execute(text("SELECT COUNT(*) FROM contacts"))
            count = result.scalar()
            
            if count > 0:
                logger.warning(f"Found {count} existing contacts without owners.")
                logger.warning("These contacts will be deleted as they cannot be associated with a user.")
                response = input("Delete existing contacts? (yes/no): ")
                if response.lower() != 'yes':
                    logger.error("Migration cancelled. Please backup and clear contacts manually.")
                    return False
                
                conn.execute(text("DELETE FROM contacts"))
                logger.info("Existing contacts deleted")
            
            # Add the column
            conn.execute(text(
                "ALTER TABLE contacts ADD COLUMN owner_id VARCHAR(36) NOT NULL DEFAULT 'temp'"
            ))
            conn.execute(text(
                "CREATE INDEX ix_contacts_owner_id ON contacts (owner_id)"
            ))
            logger.info("✓ owner_id added to contacts")
        else:
            logger.info("owner_id already exists in contacts")
    
    logger.info("✓ Migration complete")
    
    # Create default admin user if none exists
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        existing_users = session.query(User).count()
        if existing_users == 0:
            logger.info("Creating default admin user...")
            admin_user = User(
                email="admin@vishwas.local",
                hashed_password=get_password_hash("admin123"),
                full_name="Admin User",
                is_active=True,
                is_admin=True
            )
            session.add(admin_user)
            session.commit()
            logger.info("✓ Default admin user created")
            logger.info("  Email: admin@vishwas.local")
            logger.info("  Password: admin123")
            logger.info("  ⚠️  CHANGE THIS PASSWORD IMMEDIATELY IN PRODUCTION!")
        else:
            logger.info(f"{existing_users} user(s) already exist")
    finally:
        session.close()
    
    return True


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("VISHWAS Phase 7 Migration: Authentication & Authorization")
    logger.info("=" * 60)
    
    success = migrate()
    
    if success:
        logger.info("\n✓ Migration successful!")
        logger.info("\nNext steps:")
        logger.info("1. Ensure SECRET_KEY is set in .env")
        logger.info("2. Start the backend: python -m uvicorn app.main:app --reload")
        logger.info("3. Login with admin@vishwas.local / admin123")
        logger.info("4. Create new users via /api/v1/auth/register")
    else:
        logger.error("\n✗ Migration failed!")
        sys.exit(1)
