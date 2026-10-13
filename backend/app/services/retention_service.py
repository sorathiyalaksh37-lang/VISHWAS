"""
Retention Service for Phase 9: File and Data Cleanup

Implements configurable retention policies for:
- Original uploaded audio files
- Processed/converted audio files  
- Temporary files created during processing
- Old analysis reports (optional)

IMPORTANT: This is a destructive operation. Configuration must be explicit.
Do NOT hardcode production cleanup schedules.
"""
import logging
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.call import CallRecord, AnalysisReport
from app.core.config import settings

logger = logging.getLogger(__name__)


class RetentionService:
    """
    Service for enforcing data retention policies.
    
    Design principles:
    - Configurable retention periods via environment variables
    - Idempotent: safe to run multiple times
    - Non-destructive on active jobs (status='processing')
    - Path traversal protection
    - Audit logging of all deletions
    - Handles missing files gracefully
    """
    
    def __init__(self):
        """Initialize retention service with configuration."""
        # Default retention periods (in days)
        # Override via environment variables in production
        self.audio_retention_days = int(os.getenv("RETENTION_AUDIO_DAYS", "30"))
        self.temp_file_retention_hours = int(os.getenv("RETENTION_TEMP_HOURS", "24"))
        self.report_retention_days = int(os.getenv("RETENTION_REPORT_DAYS", "90"))
        
        # Safety limits
        self.min_retention_days = 7  # Minimum 7 days to prevent accidental data loss
        self.max_batch_size = 100  # Process in batches to avoid long locks
        
        # Storage root for path validation
        self.storage_root = Path(settings.upload_dir).resolve()
        
        logger.info(
            f"RetentionService initialized: audio={self.audio_retention_days}d, "
            f"reports={self.report_retention_days}d, temp={self.temp_file_retention_hours}h"
        )
    
    def _is_safe_path(self, file_path: Path) -> bool:
        """
        Validate file path is within storage root (prevent path traversal).
        
        Args:
            file_path: Path to validate
            
        Returns:
            True if path is safe to delete
        """
        try:
            resolved = file_path.resolve()
            return resolved.is_relative_to(self.storage_root)
        except (ValueError, OSError):
            return False
    
    def _delete_file_safe(self, file_path: Path) -> bool:
        """
        Safely delete a file with validation and error handling.
        
        Args:
            file_path: Path to file to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        # Path traversal protection
        if not self._is_safe_path(file_path):
            logger.error(f"SECURITY: Attempted to delete file outside storage root: {file_path}")
            return False
        
        try:
            if file_path.exists() and file_path.is_file():
                file_size = file_path.stat().st_size
                file_path.unlink()
                logger.info(f"Deleted file: {file_path.name} ({file_size} bytes)")
                return True
            elif not file_path.exists():
                logger.debug(f"File already deleted: {file_path.name}")
                return True  # Already gone, consider success
            else:
                logger.warning(f"Not a file, skipping: {file_path}")
                return False
        except PermissionError:
            logger.error(f"Permission denied deleting file: {file_path}")
            return False
        except OSError as e:
            logger.error(f"OS error deleting file {file_path}: {e}")
            return False
    
    def cleanup_expired_recordings(
        self,
        db: Session,
        dry_run: bool = False
    ) -> Tuple[int, int]:
        """
        Delete expired call recordings and their files.
        
        Only deletes completed or failed calls older than retention period.
        Active jobs (status='processing') are never deleted.
        
        Args:
            db: Database session
            dry_run: If True, only report what would be deleted
            
        Returns:
            Tuple of (records_deleted, files_deleted)
        """
        if self.audio_retention_days < self.min_retention_days:
            logger.warning(
                f"Audio retention period ({self.audio_retention_days}d) is below "
                f"minimum ({self.min_retention_days}d), using minimum"
            )
            retention_days = self.min_retention_days
        else:
            retention_days = self.audio_retention_days
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        # Find eligible records
        eligible_records = (
            db.query(CallRecord)
            .filter(
                and_(
                    CallRecord.created_at < cutoff_date,
                    CallRecord.status.in_(["completed", "failed"])  # Never delete 'processing'
                )
            )
            .limit(self.max_batch_size)
            .all()
        )
        
        if not eligible_records:
            logger.info("No expired recordings found for cleanup")
            return 0, 0
        
        logger.info(
            f"Found {len(eligible_records)} expired recordings "
            f"(older than {retention_days} days)"
        )
        
        records_deleted = 0
        files_deleted = 0
        
        for record in eligible_records:
            if dry_run:
                logger.info(f"[DRY RUN] Would delete call {record.id} and file {record.stored_filename}")
                records_deleted += 1
                continue
            
            # Delete physical file
            file_path = Path(record.storage_reference)
            if self._delete_file_safe(file_path):
                files_deleted += 1
            
            # Delete database record (cascade will delete report and integrity records)
            try:
                db.delete(record)
                records_deleted += 1
                logger.info(f"Deleted call record {record.id} (created: {record.created_at})")
            except Exception as e:
                logger.error(f"Failed to delete call record {record.id}: {e}")
                db.rollback()
        
        if not dry_run:
            try:
                db.commit()
                logger.info(
                    f"Cleanup complete: deleted {records_deleted} records, "
                    f"{files_deleted} files"
                )
            except Exception as e:
                logger.error(f"Failed to commit cleanup transaction: {e}")
                db.rollback()
                return 0, 0
        
        return records_deleted, files_deleted
    
    def cleanup_temporary_files(
        self,
        temp_dir: Optional[Path] = None,
        dry_run: bool = False
    ) -> int:
        """
        Delete old temporary files created during processing.
        
        Args:
            temp_dir: Directory to scan for temp files (default: system temp)
            dry_run: If True, only report what would be deleted
            
        Returns:
            Number of files deleted
        """
        if temp_dir is None:
            temp_dir = Path(os.getenv("TMPDIR", "/tmp"))
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.temp_file_retention_hours)
        files_deleted = 0
        
        # Look for VISHWAS temp files
        temp_patterns = [
            "vishwas_*.wav",
            "vishwas_*.mp3",
            "vishwas_*.m4a",
            "tmp_audio_*.wav",
        ]
        
        for pattern in temp_patterns:
            for temp_file in temp_dir.glob(pattern):
                try:
                    # Check file age
                    mtime = datetime.fromtimestamp(temp_file.stat().st_mtime, tz=timezone.utc)
                    
                    if mtime < cutoff_time:
                        if dry_run:
                            logger.info(f"[DRY RUN] Would delete temp file: {temp_file.name}")
                            files_deleted += 1
                        else:
                            if self._delete_file_safe(temp_file):
                                files_deleted += 1
                except (OSError, PermissionError) as e:
                    logger.warning(f"Could not process temp file {temp_file}: {e}")
        
        if files_deleted > 0:
            logger.info(
                f"Temp file cleanup {'(dry run) ' if dry_run else ''}complete: "
                f"{files_deleted} files {'would be ' if dry_run else ''}deleted"
            )
        
        return files_deleted
    
    def cleanup_old_reports(
        self,
        db: Session,
        dry_run: bool = False
    ) -> int:
        """
        Delete old analysis reports while keeping call records.
        
        WARNING: This deletes analysis results but keeps the recording.
        Only use if storage is critical and you have audit requirements
        for keeping metadata but not full analysis.
        
        Args:
            db: Database session
            dry_run: If True, only report what would be deleted
            
        Returns:
            Number of reports deleted
        """
        if self.report_retention_days < self.min_retention_days:
            logger.warning(
                f"Report retention period ({self.report_retention_days}d) is below "
                f"minimum ({self.min_retention_days}d), using minimum"
            )
            retention_days = self.min_retention_days
        else:
            retention_days = self.report_retention_days
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        # Find old reports
        old_reports = (
            db.query(AnalysisReport)
            .filter(AnalysisReport.created_at < cutoff_date)
            .limit(self.max_batch_size)
            .all()
        )
        
        if not old_reports:
            logger.info("No expired reports found for cleanup")
            return 0
        
        reports_deleted = 0
        
        for report in old_reports:
            if dry_run:
                logger.info(f"[DRY RUN] Would delete report for call {report.call_id}")
                reports_deleted += 1
                continue
            
            try:
                db.delete(report)
                reports_deleted += 1
                logger.info(f"Deleted report for call {report.call_id} (created: {report.created_at})")
            except Exception as e:
                logger.error(f"Failed to delete report {report.call_id}: {e}")
                db.rollback()
        
        if not dry_run:
            try:
                db.commit()
                logger.info(f"Report cleanup complete: deleted {reports_deleted} reports")
            except Exception as e:
                logger.error(f"Failed to commit report cleanup: {e}")
                db.rollback()
                return 0
        
        return reports_deleted
    
    def run_full_cleanup(
        self,
        db: Session,
        dry_run: bool = False
    ) -> dict:
        """
        Run complete cleanup of all expired data.
        
        Args:
            db: Database session
            dry_run: If True, only report what would be deleted
            
        Returns:
            Dictionary with cleanup statistics
        """
        logger.info(f"Starting full retention cleanup {'(DRY RUN)' if dry_run else ''}")
        
        # Cleanup recordings and files
        records_deleted, files_deleted = self.cleanup_expired_recordings(db, dry_run)
        
        # Cleanup temp files
        temp_deleted = self.cleanup_temporary_files(dry_run=dry_run)
        
        # Note: Keeping reports separate from recordings
        # Uncomment if you want to delete old reports:
        # reports_deleted = self.cleanup_old_reports(db, dry_run)
        
        stats = {
            "dry_run": dry_run,
            "records_deleted": records_deleted,
            "files_deleted": files_deleted,
            "temp_files_deleted": temp_deleted,
            # "reports_deleted": reports_deleted,
        }
        
        logger.info(f"Full cleanup complete: {stats}")
        return stats


# Singleton instance
_retention_service_instance = None


def get_retention_service() -> RetentionService:
    """Get or create the global RetentionService singleton."""
    global _retention_service_instance
    if _retention_service_instance is None:
        _retention_service_instance = RetentionService()
    return _retention_service_instance
