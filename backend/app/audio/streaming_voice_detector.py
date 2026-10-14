"""
Streaming Voice Detector — Real-time audio authenticity analysis.

Wraps the existing VoiceLayer singleton to provide incremental analysis
for streaming audio chunks. Implements temporal smoothing and quality gates
to ensure stable, confident predictions.

Design:
  - Maintains internal buffer of audio chunks using collections.deque
  - Calls VoiceLayer._spoof_prob_for_window() per chunk
  - Applies exponential moving average (EMA) temporal smoothing (alpha=0.3)
  - Quality gate: requires >= 3s accumulated audio before returning confident result
  - Thread-safe using threading.Lock
"""
import logging
import threading
import time
from collections import deque
from typing import Optional, Dict, Any

import numpy as np

from app.audio.voice_layer import get_voice_layer, VoiceLayer

logger = logging.getLogger(__name__)

# Quality gate threshold
MIN_DURATION_FOR_CONFIDENCE_S = 3.0

# Temporal smoothing parameter (exponential moving average)
EMA_ALPHA = 0.3


class StreamingVoiceDetector:
    """
    Streaming voice authenticity detector.
    
    Accumulates audio chunks, processes them through the VoiceLayer model,
    and maintains a temporally-smoothed estimate of spoof probability.
    """
    
    def __init__(self):
        """Initialize streaming detector."""
        self._voice_layer: VoiceLayer = get_voice_layer()
        self._buffer = deque()  # stores (chunk_bytes, timestamp) tuples
        self._chunks_analyzed = 0
        self._accumulated_duration_s = 0.0
        self._current_spoof_prob: Optional[float] = None
        self._lock = threading.Lock()
        self._created_at = time.time()
        
        logger.info("StreamingVoiceDetector initialized")
    
    def process_chunk(self, chunk_bytes: bytes, sample_rate: int = 16000) -> Dict[str, Any]:
        """
        Process an incoming audio chunk.
        
        Args:
            chunk_bytes: Raw audio bytes (PCM int16)
            sample_rate: Sample rate in Hz (default 16000)
        
        Returns:
            Dict with:
                - is_processing: bool
                - current_spoof_prob: float | None (0-1, higher = more likely AI)
                - confidence_level: str ('insufficient_data' | 'low' | 'medium' | 'high')
                - chunks_analyzed: int
                - duration_analyzed_ms: int
        """
        with self._lock:
            # Store chunk in buffer
            chunk_duration_s = len(chunk_bytes) / (sample_rate * 2)  # 2 bytes per sample (int16)
            self._buffer.append((chunk_bytes, time.time()))
            self._accumulated_duration_s += chunk_duration_s
            
            # Convert bytes to numpy array (int16 -> float32 normalized to [-1, 1])
            try:
                samples = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            except Exception as e:
                logger.error(f"Failed to parse audio chunk: {e}")
                return self._build_response(error="Invalid audio format")
            
            # Validate chunk has minimum length for analysis (at least 1s)
            min_samples = sample_rate * 1  # 1 second
            if len(samples) < min_samples:
                logger.debug(f"Chunk too short: {len(samples)} samples < {min_samples}")
                return self._build_response()
            
            # Check if model is loaded
            if not self._voice_layer._load_spoof_model():
                logger.warning("Voice layer model unavailable")
                return self._build_response(error="Model unavailable")
            
            # Run spoof detection on this chunk
            try:
                chunk_spoof_prob = self._voice_layer._spoof_prob_for_window(samples)
                self._chunks_analyzed += 1
                
                # Apply exponential moving average temporal smoothing
                if self._current_spoof_prob is None:
                    self._current_spoof_prob = chunk_spoof_prob
                else:
                    self._current_spoof_prob = (
                        EMA_ALPHA * chunk_spoof_prob + 
                        (1 - EMA_ALPHA) * self._current_spoof_prob
                    )
                
                logger.debug(
                    f"Chunk {self._chunks_analyzed}: raw={chunk_spoof_prob:.3f}, "
                    f"smoothed={self._current_spoof_prob:.3f}, "
                    f"duration={self._accumulated_duration_s:.1f}s"
                )
                
            except Exception as e:
                logger.error(f"Spoof detection failed for chunk: {e}", exc_info=True)
                return self._build_response(error="Detection failed")
            
            return self._build_response()
    
    def _build_response(self, error: Optional[str] = None) -> Dict[str, Any]:
        """
        Build response dict with current state.
        
        Args:
            error: Optional error message
        
        Returns:
            Response dict
        """
        # Determine confidence level based on accumulated duration
        if self._accumulated_duration_s < MIN_DURATION_FOR_CONFIDENCE_S:
            confidence_level = 'insufficient_data'
        elif self._chunks_analyzed < 2:
            confidence_level = 'low'
        elif self._chunks_analyzed < 3:
            confidence_level = 'medium'
        else:
            confidence_level = 'high'
        
        response = {
            'is_processing': True,
            'current_spoof_prob': round(self._current_spoof_prob, 4) if self._current_spoof_prob is not None else None,
            'confidence_level': confidence_level,
            'chunks_analyzed': self._chunks_analyzed,
            'duration_analyzed_ms': int(self._accumulated_duration_s * 1000)
        }
        
        if error:
            response['error'] = error
            response['is_processing'] = False
        
        return response
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get current detector state without processing new data."""
        with self._lock:
            return self._build_response()
    
    def reset(self):
        """Reset detector state (for session cleanup or restart)."""
        with self._lock:
            self._buffer.clear()
            self._chunks_analyzed = 0
            self._accumulated_duration_s = 0.0
            self._current_spoof_prob = None
            logger.debug("StreamingVoiceDetector reset")
