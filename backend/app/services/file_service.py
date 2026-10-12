"""
File handling service for audio uploads.
"""
import os
import uuid
import logging
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException

from app.core.config import settings

# Try to import python-magic, but make it optional
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    logging.warning("python-magic not available, MIME type validation will be skipped")

logger = logging.getLogger(__name__)


class FileService:
    """Service for handling file uploads and validation."""
    
    def __init__(self):
        """Initialize file service and create storage directory."""
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Upload directory initialized: {self.upload_dir}")
    
    def validate_file_extension(self, filename: str) -> bool:
        """Validate file extension against allowlist."""
        extension = filename.lower().split(".")[-1] if "." in filename else ""
        is_valid = extension in settings.allowed_extensions_list
        logger.debug(f"Extension validation for '{filename}': {is_valid}")
        return is_valid
    
    def validate_file_size(self, file: UploadFile) -> bool:
        """Validate file size is within limits."""
        # Note: For streaming large files, this should be checked during upload
        # For now, we'll check content-length header if available
        content_length = file.size
        if content_length and content_length > settings.max_upload_size_bytes:
            logger.warning(f"File too large: {content_length} bytes")
            return False
        return True
    
    def validate_mime_type(self, file_path: Path) -> bool:
        """Validate file MIME type using magic numbers."""
        if not MAGIC_AVAILABLE:
            logger.debug("python-magic not available, skipping MIME type validation")
            return True
        
        try:
            mime = magic.Magic(mime=True)
            file_type = mime.from_file(str(file_path))
            
            # Accept audio files
            valid_types = ["audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/x-m4a"]
            is_valid = file_type in valid_types or file_type.startswith("audio/")
            
            logger.debug(f"MIME type validation: {file_type} - {is_valid}")
            return is_valid
        except Exception as e:
            logger.warning(f"Could not validate MIME type: {e}")
            # If validation fails, fall back to extension validation
            return True
    
    def generate_safe_filename(self, original_filename: str) -> Tuple[str, str]:
        """
        Generate a safe, unique filename for storage.
        Returns: (safe_filename, file_extension)
        """
        # Extract extension
        extension = original_filename.lower().split(".")[-1] if "." in original_filename else "bin"
        
        # Generate unique filename
        unique_id = str(uuid.uuid4())
        safe_filename = f"{unique_id}.{extension}"
        
        return safe_filename, extension
    
    async def save_upload(self, file: UploadFile) -> Tuple[str, str, str]:
        """
        Save uploaded file to storage.
        
        Returns:
            Tuple of (stored_filename, storage_reference, original_filename)
        
        Raises:
            HTTPException: If validation fails or storage error occurs
        """
        original_filename = file.filename or "unknown"
        
        # Validate extension
        if not self.validate_file_extension(original_filename):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format. Allowed: {', '.join(settings.allowed_extensions_list)}"
            )
        
        # Validate size
        if not self.validate_file_size(file):
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum allowed ({settings.max_upload_size_mb}MB)"
            )
        
        # Generate safe filename
        stored_filename, extension = self.generate_safe_filename(original_filename)
        storage_path = self.upload_dir / stored_filename
        
        try:
            # Stream file to disk
            with open(storage_path, "wb") as f:
                while chunk := await file.read(8192):  # Read in 8KB chunks
                    f.write(chunk)
            
            logger.info(f"File saved: {stored_filename} (original: {original_filename})")
            
            # Validate MIME type after saving
            # Note: In production, you might want to validate before saving
            # or use a temporary location first
            if not self.validate_mime_type(storage_path):
                storage_path.unlink()  # Delete invalid file
                raise HTTPException(
                    status_code=400,
                    detail="Invalid file type detected"
                )
            
            # Check if file is empty
            if storage_path.stat().st_size == 0:
                storage_path.unlink()
                raise HTTPException(
                    status_code=400,
                    detail="Uploaded file is empty"
                )
            
            storage_reference = str(storage_path.absolute())
            return stored_filename, storage_reference, original_filename
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            # Clean up partial file if it exists
            if storage_path.exists():
                storage_path.unlink()
            raise HTTPException(
                status_code=500,
                detail="Failed to save uploaded file"
            )
    
    def get_file_path(self, stored_filename: str) -> Optional[Path]:
        """Get full path to stored file."""
        file_path = self.upload_dir / stored_filename
        return file_path if file_path.exists() else None
    
    def delete_file(self, stored_filename: str) -> bool:
        """Delete a stored file."""
        try:
            file_path = self.upload_dir / stored_filename
            if file_path.exists():
                file_path.unlink()
                logger.info(f"File deleted: {stored_filename}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete file {stored_filename}: {e}")
            return False


# Singleton instance
file_service = FileService()
