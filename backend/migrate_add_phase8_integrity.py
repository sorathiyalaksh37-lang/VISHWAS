"""
Phase 8 Database Migration: Add file integrity tracking

Creates the file_integrity_records table for SHA-256 hash storage.

Run this migration ONCE:
    python migrate_add_phase8_integrity.py

Existing call_records without hashes will be represented as 'unavailable'
(not assigned fabricated hashes).
"""
import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings
from app.database.base import Base
from app.models.integrity import FileIntegrityRecord

print("=" * 70)
print("PHASE 8 MIGRATION: File Integrity Tracking")
print("=" * 70)

# Create engine
engine = create_engine(settings.database_url)
inspector = inspect(engine)

# Check if table already exists
existing_tables = inspector.get_table_names()
if "file_integrity_records" in existing_tables:
    print("✓ file_integrity_records table already exists")
    print("\nNo migration needed.")
    sys.exit(0)

print("\n1. Creating file_integrity_records table...")
try:
    # Create only the new table
    FileIntegrityRecord.__table__.create(engine)
    print("   ✓ file_integrity_records table created")
except Exception as e:
    print(f"   ✗ Failed to create table: {e}")
    sys.exit(1)

# Verify table was created
inspector = inspect(engine)
if "file_integrity_records" not in inspector.get_table_names():
    print("   ✗ Table creation verification failed")
    sys.exit(1)

print("\n2. Checking existing call_records...")
with engine.connect() as conn:
    result = conn.execute(text("SELECT COUNT(*) FROM call_records"))
    total_calls = result.scalar()
    print(f"   Found {total_calls} existing call records")
    
    if total_calls > 0:
        print(f"   Note: These {total_calls} records do NOT have integrity hashes")
        print(f"   Their integrity status will be 'unavailable' (not fabricated)")

print("\n" + "=" * 70)
print("MIGRATION COMPLETE")
print("=" * 70)
print("\nWhat happened:")
print("  ✓ Created file_integrity_records table")
print(f"  ✓ Existing {total_calls} call_records preserved (no hashes)")
print("  ✓ Future uploads will automatically record SHA-256 hashes")
print("\nIntegrity verification:")
print("  - New uploads: 'verified' or 'mismatch'")
print("  - Legacy uploads: 'unavailable' (expected)")
print("\nSecurity notes:")
print("  - SHA-256 detects byte-level modifications only")
print("  - Does NOT prove recording authenticity before upload")
print("  - Not a legal-grade forensic chain of custody")
print("=" * 70)
