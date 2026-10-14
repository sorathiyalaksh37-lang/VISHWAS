"""
Migration: Add owner_id column to contacts table
"""
import sqlite3
from pathlib import Path

# Path to database
db_path = Path(__file__).parent / "vishwas.db"

def migrate():
    """Add owner_id column to contacts table if it doesn't exist."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(contacts)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'owner_id' not in columns:
            print("Adding owner_id column to contacts table...")
            cursor.execute("""
                ALTER TABLE contacts 
                ADD COLUMN owner_id TEXT
            """)
            
            # Create index for owner_id
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS ix_contacts_owner_id 
                ON contacts(owner_id)
            """)
            
            conn.commit()
            print("✓ Migration completed: owner_id column added")
        else:
            print("✓ Column owner_id already exists")
            
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
