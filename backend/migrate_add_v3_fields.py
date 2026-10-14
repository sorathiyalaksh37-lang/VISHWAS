"""
Database migration: Add v3 Trust Engine fields to analysis_reports table.

Adds columns:
- category_scores_json (Text)
- fired_rules_json (Text)
- verification_json (Text)
- killchain_stage (String)

Run this script to update the database schema.
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "vishwas.db"


def migrate():
    """Add v3 fields to analysis_reports table."""
    print(f"Connecting to database: {DB_PATH}")
    
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check current schema
        print("\n1. Checking current schema...")
        cursor.execute("PRAGMA table_info(analysis_reports)")
        columns = {row[1] for row in cursor.fetchall()}
        print(f"   Current columns: {len(columns)} columns found")
        
        # Add missing columns
        migrations = [
            ("voice_json", "ALTER TABLE analysis_reports ADD COLUMN voice_json TEXT"),
            ("category_scores_json", "ALTER TABLE analysis_reports ADD COLUMN category_scores_json TEXT"),
            ("fired_rules_json", "ALTER TABLE analysis_reports ADD COLUMN fired_rules_json TEXT"),
            ("verification_json", "ALTER TABLE analysis_reports ADD COLUMN verification_json TEXT"),
            ("killchain_stage", "ALTER TABLE analysis_reports ADD COLUMN killchain_stage VARCHAR(50)"),
        ]
        
        print("\n2. Adding missing columns...")
        for column_name, sql in migrations:
            if column_name in columns:
                print(f"   ✓ {column_name} already exists, skipping")
            else:
                print(f"   + Adding {column_name}...", end=" ")
                cursor.execute(sql)
                print("✓ Done")
        
        # Commit changes
        conn.commit()
        print("\n3. Migration completed successfully!")
        
        # Verify new schema
        print("\n4. Verifying new schema...")
        cursor.execute("PRAGMA table_info(analysis_reports)")
        new_columns = [(row[0], row[1], row[2]) for row in cursor.fetchall()]
        print(f"   Total columns: {len(new_columns)}")
        for idx, name, col_type in new_columns:
            marker = "NEW" if name in ["category_scores_json", "fired_rules_json", "verification_json", "killchain_stage"] else "   "
            print(f"   [{marker}] {idx}: {name} ({col_type})")
        
    except sqlite3.Error as e:
        print(f"\n❌ ERROR: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()
    
    print("\n✅ Database migration complete!")
    print("   You can now restart the backend server.")


if __name__ == "__main__":
    migrate()
