#!/usr/bin/env python3
"""
Phase 9: Data Retention Cleanup Script

Run this script periodically (e.g., via cron) to enforce retention policies.

Usage:
    # Dry run (show what would be deleted)
    python cleanup_expired_data.py --dry-run
    
    # Actually delete expired data
    python cleanup_expired_data.py
    
    # Delete only specific types
    python cleanup_expired_data.py --recordings-only
    python cleanup_expired_data.py --temp-only

Configuration:
    Set retention periods via environment variables:
    - RETENTION_AUDIO_DAYS (default: 30)
    - RETENTION_TEMP_HOURS (default: 24)
    - RETENTION_REPORT_DAYS (default: 90)

IMPORTANT: Test with --dry-run first in production!
"""
import sys
import argparse
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.services.retention_service import get_retention_service
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main cleanup execution."""
    parser = argparse.ArgumentParser(
        description="VISHWAS Data Retention Cleanup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--recordings-only",
        action="store_true",
        help="Only cleanup expired recordings"
    )
    parser.add_argument(
        "--temp-only",
        action="store_true",
        help="Only cleanup temporary files"
    )
    parser.add_argument(
        "--reports-only",
        action="store_true",
        help="Only cleanup old reports (keep recordings)"
    )
    
    args = parser.parse_args()
    
    # Print configuration
    logger.info("=" * 70)
    logger.info("VISHWAS DATA RETENTION CLEANUP")
    logger.info("=" * 70)
    
    if args.dry_run:
        logger.info("MODE: DRY RUN (no data will be deleted)")
    else:
        logger.warning("MODE: LIVE (data WILL be deleted)")
    
    logger.info("")
    
    # Create database session
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        retention_service = get_retention_service()
        
        # Run cleanup based on flags
        if args.temp_only:
            logger.info("Running temp file cleanup only...")
            temp_deleted = retention_service.cleanup_temporary_files(dry_run=args.dry_run)
            logger.info(f"Result: {temp_deleted} temp files {'would be ' if args.dry_run else ''}deleted")
        
        elif args.reports_only:
            logger.info("Running report cleanup only...")
            reports_deleted = retention_service.cleanup_old_reports(db, dry_run=args.dry_run)
            logger.info(f"Result: {reports_deleted} reports {'would be ' if args.dry_run else ''}deleted")
        
        elif args.recordings_only:
            logger.info("Running recording cleanup only...")
            records, files = retention_service.cleanup_expired_recordings(db, dry_run=args.dry_run)
            logger.info(
                f"Result: {records} records and {files} files "
                f"{'would be ' if args.dry_run else ''}deleted"
            )
        
        else:
            # Full cleanup
            logger.info("Running full cleanup (all types)...")
            stats = retention_service.run_full_cleanup(db, dry_run=args.dry_run)
            logger.info(f"Results: {stats}")
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("CLEANUP COMPLETE")
        logger.info("=" * 70)
        
        if args.dry_run:
            logger.info("This was a DRY RUN. No data was actually deleted.")
            logger.info("Run without --dry-run to perform actual cleanup.")
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        return 1
    finally:
        db.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
