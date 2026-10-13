"""
Database models for file integrity tracking.
Phase 8: SHA-256 Evidence Integrity
"""
from sqlalchemy import Column, String, DateTime, Integer, BigInteger, ForeignKey
from sqlalchemy.sql import func
from app.database.base import Base
import uuid


class FileIntegrityRecord(Base):
    """
    Model for tracking SHA-256 hashes of stored files.
    
    Provides tamper detection for audio artifacts. Does NOT prove:
    - Authenticity of the recording before upload
    - Freedom from voice cloning or pre-upload editing
    - Legal-grade forensic chain of custody
    
    Use this for detecting post-storage file modifications only.
    """

    __tablename__ = "file_integrity_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    call_id = Column(String(36), ForeignKey("call_records.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_type = Column(String(50), nullable=False, index=True)  # e.g., 'original_upload', 'processed_wav'
    file_path = Column(String(500), nullable=False)  # Relative or stored filename
    sha256_hash = Column(String(64), nullable=False, index=True)  # Hex-encoded SHA-256 digest
    file_size_bytes = Column(BigInteger, nullable=False)  # File size at hash time
    hash_algorithm = Column(String(20), nullable=False, default="sha256")  # For future-proofing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<FileIntegrityRecord(call_id={self.call_id}, artifact_type={self.artifact_type}, hash={self.sha256_hash[:16]}...)>"
