"""
API client for communicating with VISHWAS backend.
"""
import requests
from typing import Optional, Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class VishwasAPIClient:
    """Client for VISHWAS API."""
    
    def __init__(self, base_url: str = "http://localhost:8000/api/v1"):
        """Initialize API client with base URL."""
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
    
    def health_check(self) -> Optional[Dict]:
        """Check if API is healthy."""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return None
    
    def upload_recording(self, file_path: str, filename: str) -> Optional[Dict]:
        """
        Upload a recording file.
        
        Args:
            file_path: Path to the file to upload
            filename: Original filename
        
        Returns:
            Response dict with call_id and status, or None on error
        """
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f)}
                response = self.session.post(
                    f"{self.base_url}/calls",
                    files=files,
                    timeout=30
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return None
    
    def upload_recording_bytes(self, file_bytes: bytes, filename: str) -> Optional[Dict]:
        """
        Upload a recording from bytes.
        
        Args:
            file_bytes: File content as bytes
            filename: Original filename
        
        Returns:
            Response dict with call_id and status, or None on error
        """
        try:
            files = {'file': (filename, file_bytes)}
            response = self.session.post(
                f"{self.base_url}/calls",
                files=files,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return None
    
    def get_call_status(self, call_id: str) -> Optional[Dict]:
        """Get status of a call."""
        try:
            response = self.session.get(
                f"{self.base_url}/calls/{call_id}/status",
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return None
    
    def get_transcript(self, call_id: str) -> Optional[Dict]:
        """Get transcript for a call."""
        try:
            response = self.session.get(
                f"{self.base_url}/calls/{call_id}/transcript",
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get transcript: {e}")
            return None
    
    def get_report(self, call_id: str) -> Optional[Dict]:
        """Get analysis report for a call."""
        try:
            response = self.session.get(
                f"{self.base_url}/calls/{call_id}/report",
                timeout=5
            )
            if response.status_code == 425:
                # Analysis in progress
                return {"status": "in_progress"}
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 425:
                return {"status": "in_progress"}
            logger.error(f"Failed to get report: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get report: {e}")
            return None
    
    def list_calls(self, page: int = 1, page_size: int = 20) -> Optional[Dict]:
        """List all calls with pagination."""
        try:
            response = self.session.get(
                f"{self.base_url}/calls",
                params={"page": page, "page_size": page_size},
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list calls: {e}")
            return None
