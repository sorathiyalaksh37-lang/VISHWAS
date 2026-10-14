"""
Streaming Session Manager — In-memory session storage for streaming voice detection.

Manages active streaming sessions with automatic TTL-based cleanup.
Each session contains a StreamingVoiceDetector instance and metadata.

Design:
  - In-memory dict storage: {session_id: session_data}
  - Thread-safe using threading.Lock
  - Background cleanup task removes expired sessions (max_age_minutes=30)
  - Singleton pattern for application-wide access
"""
import asyncio
import logging
import secrets
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Any

from app.audio.streaming_voice_detector import StreamingVoiceDetector

logger = logging.getLogger(__name__)

# Session configuration
SESSION_MAX_AGE_MINUTES = 30
SESSION_MAX_DURATION_MINUTES = 5
CLEANUP_INTERVAL_SECONDS = 60


class StreamingSessionManager:
    """
    Manages in-memory streaming voice detection sessions.
    
    Each session contains:
      - detector: StreamingVoiceDetector instance
      - created_at: datetime
      - last_accessed: datetime
      - total_chunks: int
      - user_id: str (for multi-user support)
    """
    
    def __init__(self):
        """Initialize session manager."""
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        logger.info("StreamingSessionManager initialized")
    
    def create_session(self, user_id: str) -> str:
        """
        Create a new streaming session.
        
        Args:
            user_id: User ID for session ownership
        
        Returns:
            session_id: Unique session identifier
        """
        with self._lock:
            session_id = secrets.token_urlsafe(32)
            now = datetime.now(timezone.utc)
            
            self._sessions[session_id] = {
                'detector': StreamingVoiceDetector(),
                'created_at': now,
                'last_accessed': now,
                'total_chunks': 0,
                'user_id': user_id,
            }
            
            logger.info(f"Created streaming session {session_id} for user {user_id}")
            return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session data by ID and update last_accessed timestamp.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Session data dict or None if not found
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session['last_accessed'] = datetime.now(timezone.utc)
            return session
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session by ID.
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"Deleted streaming session {session_id}")
                return True
            return False
    
    def cleanup_expired(self, max_age_minutes: int = SESSION_MAX_AGE_MINUTES) -> int:
        """
        Remove expired sessions based on last_accessed timestamp.
        
        Args:
            max_age_minutes: Maximum age in minutes before expiration
        
        Returns:
            Number of sessions deleted
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            expired = []
            
            for session_id, session_data in self._sessions.items():
                last_accessed = session_data['last_accessed']
                age_minutes = (now - last_accessed).total_seconds() / 60
                
                if age_minutes > max_age_minutes:
                    expired.append(session_id)
            
            for session_id in expired:
                del self._sessions[session_id]
            
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired streaming sessions")
            
            return len(expired)
    
    def get_session_count(self) -> int:
        """Get total number of active sessions."""
        with self._lock:
            return len(self._sessions)
    
    def start_cleanup_task(self):
        """Start background cleanup task (called from lifespan)."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Started streaming session cleanup task")
    
    async def _cleanup_loop(self):
        """Background task that periodically cleans up expired sessions."""
        while True:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                self.cleanup_expired()
            except asyncio.CancelledError:
                logger.info("Streaming session cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}", exc_info=True)
    
    def stop_cleanup_task(self):
        """Stop background cleanup task (called from lifespan)."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.info("Stopped streaming session cleanup task")


# ── Singleton instance ────────────────────────────────────────────────────────
_streaming_session_manager: Optional[StreamingSessionManager] = None


def get_streaming_session_manager() -> StreamingSessionManager:
    """Get or create the global StreamingSessionManager singleton."""
    global _streaming_session_manager
    if _streaming_session_manager is None:
        _streaming_session_manager = StreamingSessionManager()
    return _streaming_session_manager
