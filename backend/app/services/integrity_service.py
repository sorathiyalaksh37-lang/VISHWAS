"""
File integrity service for SHA-256 hash calculation and verification.
Phase 8: SHA-256 Evidence Integrity

This module provides:
- Streaming SHA-256 calculation (memory-bounded)
- Hash persistence in database
- Verification against stored artifacts
- Clear status reporting (verified, mismatch, unavailable)

LIMITATIONS:
- SHA-256 detects byte-level modifications only
- Does not prove recording authenticity before upload
- Does not detect voice cloning or pre-upload editing
- Not a legal-grade forensic chain of custody
- Hash stored in database can be modified by attacker with database access
"""
import hashlib
import logging
from pathlib import Path
from typing import Optional, Literal, Tuple
from sqlalchemy.orm import Session

from app.models.integrity import FileIntegrityRecord

logger = logging.getLogger(__name__)

# Chunk size for streaming hash calculation (8KB)
HASH_CHUNK_SIZE = 8192

IntegrityStatus = Literal["verified", "mismatch", "unavailable"]


class IntegrityService:
    """Service for file integrity operations."""
    
    def calculate_sha256(self, file_path: Path) -> Tuple[str, int]:
        """
        Calculate SHA-256 hash of a file using streaming approach.
        
        Memory-bounded: reads file in chunks to handle arbitrarily large files.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (hex_digest, file_size_bytes)
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        sha256_hash = hashlib.sha256()
        file_size = 0
        
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(HASH_CHUNK_SIZE):
                    sha256_hash.update(chunk)
                    file_size += len(chunk)
            
            hex_digest = sha256_hash.hexdigest()
            logger.debug(f"Calculated SHA-256 for {file_path.name}: {hex_digest} ({file_size} bytes)")
            return hex_digest, file_size
            
        except IOError as e:
            logger.error(f"Failed to read file for hashing: {file_path} - {e}")
            raise
    
    def record_file_hash(
        self,
        db: Session,
        call_id: str,
        artifact_type: str,
        file_path: str,
        sha256_hash: str,
        file_size_bytes: int,
    ) -> FileIntegrityRecord:
        """
        Store file integrity record in database.
        
        Args:
            db: Database session
            call_id: Associated call record ID
            artifact_type: Type of artifact (e.g., 'original_upload', 'processed_wav')
            file_path: File path or stored filename
            sha256_hash: Hex-encoded SHA-256 digest
            file_size_bytes: File size in bytes
            
        Returns:
            Created FileIntegrityRecord
        """
        record = FileIntegrityRecord(
            call_id=call_id,
            artifact_type=artifact_type,
            file_path=file_path,
            sha256_hash=sha256_hash,
            file_size_bytes=file_size_bytes,
            hash_algorithm="sha256",
        )
        db.add(record)
        db.flush()  # Don't commit, let caller control transaction
        
        logger.info(
            f"Recorded file integrity: call_id={call_id}, artifact={artifact_type}, "
            f"hash={sha256_hash[:16]}..., size={file_size_bytes}"
        )
        return record
    
    def calculate_and_record(
        self,
        db: Session,
        call_id: str,
        artifact_type: str,
        file_path: Path,
    ) -> Optional[FileIntegrityRecord]:
        """
        Calculate SHA-256 hash and record it in database.
        
        Convenience method combining calculation and persistence.
        
        Args:
            db: Database session
            call_id: Associated call record ID
            artifact_type: Type of artifact
            file_path: Path to the file
            
        Returns:
            FileIntegrityRecord if successful, None if file not found
        """
        try:
            sha256_hash, file_size = self.calculate_sha256(file_path)
            return self.record_file_hash(
                db=db,
                call_id=call_id,
                artifact_type=artifact_type,
                file_path=str(file_path.name),  # Store filename, not full path
                sha256_hash=sha256_hash,
                file_size_bytes=file_size,
            )
        except FileNotFoundError:
            logger.warning(f"File not found for integrity recording: {file_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to calculate and record hash: {e}")
            return None
    
    def get_stored_hash(
        self,
        db: Session,
        call_id: str,
        artifact_type: str,
    ) -> Optional[FileIntegrityRecord]:
        """
        Retrieve stored integrity record from database.
        
        Args:
            db: Database session
            call_id: Call record ID
            artifact_type: Type of artifact
            
        Returns:
            FileIntegrityRecord if found, None otherwise
        """
        return (
            db.query(FileIntegrityRecord)
            .filter(
                FileIntegrityRecord.call_id == call_id,
                FileIntegrityRecord.artifact_type == artifact_type,
            )
            .first()
        )
    
    def verify_file_integrity(
        self,
        db: Session,
        call_id: str,
        artifact_type: str,
        file_path: Path,
    ) -> Tuple[IntegrityStatus, Optional[str]]:
        """
        Verify file integrity against stored hash.
        
        Compares current file SHA-256 with recorded digest.
        
        Args:
            db: Database session
            call_id: Call record ID
            artifact_type: Type of artifact
            file_path: Current path to the file
            
        Returns:
            Tuple of (status, message):
            - ("verified", None): File matches stored hash
            - ("mismatch", reason): File differs from stored hash
            - ("unavailable", reason): Hash or file not available for verification
        """
        # Get stored hash
        stored_record = self.get_stored_hash(db, call_id, artifact_type)
        if not stored_record:
            msg = f"No integrity record found for call_id={call_id}, artifact={artifact_type}"
            logger.warning(msg)
            return ("unavailable", msg)
        
        # Check if file exists
        if not file_path.exists():
            msg = f"File not found at {file_path}"
            logger.error(msg)
            return ("unavailable", msg)
        
        # Calculate current hash
        try:
            current_hash, current_size = self.calculate_sha256(file_path)
        except Exception as e:
            msg = f"Failed to calculate hash: {e}"
            logger.error(msg)
            return ("unavailable", msg)
        
        # Compare hashes
        if current_hash != stored_record.sha256_hash:
            msg = (
                f"Hash mismatch detected! "
                f"Stored: {stored_record.sha256_hash[:16]}..., "
                f"Current: {current_hash[:16]}..."
            )
            logger.error(
                f"SECURITY: File integrity violation for call_id={call_id}, "
                f"artifact={artifact_type}. {msg}"
            )
            return ("mismatch", msg)
        
        # Check size changed
        if current_size != stored_record.file_size_bytes:
            msg = (
                f"Size mismatch (hash collision?): "
                f"stored={stored_record.file_size_bytes}, current={current_size}"
            )
            logger.warning(msg)
            # Note: This is extremely unlikely with SHA-256
            return ("mismatch", msg)
        
        logger.debug(f"Integrity verified for call_id={call_id}, artifact={artifact_type}")
        return ("verified", None)
    
    def get_all_hashes_for_call(
        self,
        db: Session,
        call_id: str,
    ) -> list[FileIntegrityRecord]:
        """
        Get all integrity records for a call.
        
        Args:
            db: Database session
            call_id: Call record ID
            
        Returns:
            List of FileIntegrityRecord objects
        """
        return (
            db.query(FileIntegrityRecord)
            .filter(FileIntegrityRecord.call_id == call_id)
            .order_by(FileIntegrityRecord.created_at)
            .all()
        )


# Singleton instance
integrity_service = IntegrityService()
