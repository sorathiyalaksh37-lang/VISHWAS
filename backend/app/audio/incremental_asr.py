"""
Incremental ASR — Rolling-window streaming automatic speech recognition with deduplication.
Produces provisional (interim) and finalized transcript segments for real-time live sessions.
"""
from __future__ import annotations

import difflib
import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PartialTranscript:
    """Represents an incremental transcript segment with finality flag."""
    start_time: float
    end_time: float
    text: str
    is_final: bool = False
    confidence: float = 0.9
    speaker: str = "caller"


class IncrementalASR:
    """
    Rolling-window streaming ASR processor.
    
    Maintains a sliding audio buffer, performs overlapping transcription,
    deduplicates overlapping text across window boundaries, and manages
    the provisional vs. finalized status of transcribed segments.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        window_duration_s: float = 3.0,
        step_duration_s: float = 1.0,
    ):
        self.sample_rate = sample_rate
        self.bytes_per_sample = 2  # 16-bit PCM mono
        self.bytes_per_second = self.sample_rate * self.bytes_per_sample
        
        self.window_duration_s = window_duration_s
        self.step_duration_s = step_duration_s
        self.min_window_bytes = int(self.window_duration_s * self.bytes_per_second)
        self.step_bytes = int(self.step_duration_s * self.bytes_per_second)

        self.audio_buffer = bytearray()
        self.total_audio_seconds: float = 0.0
        self.last_finalized_text: str = ""
        self.finalized_segments: List[PartialTranscript] = []
        self.current_provisional: Optional[PartialTranscript] = None
        
        self._whisper_model = None
        self._whisper_attempted = False

    def _get_whisper_model(self):
        """Lazy load faster-whisper if configured and available."""
        if self._whisper_attempted:
            return self._whisper_model
        self._whisper_attempted = True

        if getattr(settings, "analysis_mode", "mock") == "mock":
            return None

        try:
            from faster_whisper import WhisperModel
            self._whisper_model = WhisperModel(
                settings.whisper_model_size,
                device=settings.whisper_device,
                compute_type=settings.whisper_compute_type,
            )
            logger.info("Incremental ASR faster-whisper loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load faster-whisper for streaming ASR ({e}). Falling back to acoustic mode.")
            self._whisper_model = None
        return self._whisper_model

    def add_audio(self, pcm_bytes: bytes, timestamp_ms: Optional[int] = None) -> None:
        """Append raw 16-bit PCM mono audio bytes to buffer."""
        self.audio_buffer.extend(pcm_bytes)
        added_sec = len(pcm_bytes) / self.bytes_per_second
        self.total_audio_seconds += added_sec

    def has_sufficient_audio(self) -> bool:
        """Returns True if buffer has enough audio for a sliding window."""
        return len(self.audio_buffer) >= self.min_window_bytes

    def transcribe_current_window(self) -> List[PartialTranscript]:
        """
        Process the accumulated audio window.
        Returns a list of newly emitted segments (provisional or finalized).
        """
        if not self.has_sufficient_audio():
            return []

        # Extract current window bytes
        window_bytes = bytes(self.audio_buffer[: self.min_window_bytes])
        t_start = max(0.0, self.total_audio_seconds - (len(self.audio_buffer) / self.bytes_per_second))
        t_end = t_start + self.window_duration_s

        # Transcribe window
        raw_text = self._transcribe_window_pcm(window_bytes)
        if not raw_text or not raw_text.strip():
            # Step forward
            self._step_buffer()
            return []

        raw_text = raw_text.strip()

        # Deduplicate against already finalized text
        new_text = self._deduplicate(raw_text, self.last_finalized_text)
        if not new_text:
            self._step_buffer()
            return []

        # Determine if text looks final (e.g., ends in sentence boundary or window step advanced)
        is_sentence_boundary = any(new_text.endswith(p) for p in [".", "!", "?", "\n"])

        emitted: List[PartialTranscript] = []

        if is_sentence_boundary:
            # Commit as finalized
            seg = PartialTranscript(
                start_time=round(t_start, 2),
                end_time=round(t_end, 2),
                text=new_text,
                is_final=True,
                confidence=0.95,
            )
            self.finalized_segments.append(seg)
            self.last_finalized_text = f"{self.last_finalized_text} {new_text}".strip()
            self.current_provisional = None
            emitted.append(seg)
        else:
            # Provisional interim segment
            seg = PartialTranscript(
                start_time=round(t_start, 2),
                end_time=round(t_end, 2),
                text=new_text,
                is_final=False,
                confidence=0.85,
            )
            self.current_provisional = seg
            emitted.append(seg)

        # Advance buffer by step size (preserving overlap)
        self._step_buffer()
        return emitted

    def finalize_remaining(self) -> List[PartialTranscript]:
        """Mark any pending provisional segment as finalized at end of stream."""
        finalized: List[PartialTranscript] = []
        if self.current_provisional and not self.current_provisional.is_final:
            self.current_provisional.is_final = True
            self.finalized_segments.append(self.current_provisional)
            self.last_finalized_text = f"{self.last_finalized_text} {self.current_provisional.text}".strip()
            finalized.append(self.current_provisional)
            self.current_provisional = None
        return finalized

    def _step_buffer(self) -> None:
        """Advance buffer by step_bytes, retaining overlap."""
        if len(self.audio_buffer) >= self.step_bytes:
            self.audio_buffer = self.audio_buffer[self.step_bytes:]
        else:
            self.audio_buffer.clear()

    def _transcribe_window_pcm(self, pcm_bytes: bytes) -> str:
        """Transcribe raw PCM using faster-whisper if available or acoustic simulation."""
        model = self._get_whisper_model()
        if model is not None:
            try:
                import numpy as np
                audio_np = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                segments, _ = model.transcribe(audio_np, beam_size=1, language="en")
                return " ".join(s.text.strip() for s in segments if s.text.strip())
            except Exception as e:
                logger.debug(f"Streaming ASR inference exception: {e}")

        # When running in test/mock mode or no model: check if audio is silence
        return self._extract_acoustic_mock_text(pcm_bytes)

    def _extract_acoustic_mock_text(self, pcm_bytes: bytes) -> str:
        """Compute RMS to determine if signal is present; if silent, return empty."""
        import struct
        count = len(pcm_bytes) // 2
        if count == 0:
            return ""
        shorts = struct.unpack(f"<{count}h", pcm_bytes)
        sum_sq = sum(s * s for s in shorts)
        rms = math.sqrt(sum_sq / count)
        if rms < 100.0:
            # Silence
            return ""
        # Signal present
        return f"Audio signal chunk (RMS {round(rms, 1)})"

    @staticmethod
    def _deduplicate(current_text: str, finalized_text: str) -> str:
        """
        Deduplicate overlapping tokens between current window and previously finalized text.
        Finds overlapping token sequences to avoid repetition across sliding windows.
        """
        if not finalized_text or not current_text:
            return current_text.strip()

        final_words = finalized_text.strip().split()
        curr_words = current_text.strip().split()

        if not final_words or not curr_words:
            return current_text.strip()

        # Check largest suffix of final_words matching prefix of curr_words
        max_overlap_k = min(len(final_words), len(curr_words), 15)
        for k in range(max_overlap_k, 0, -1):
            final_suffix = [w.lower().strip(".,!?:;") for w in final_words[-k:]]
            curr_prefix = [w.lower().strip(".,!?:;") for w in curr_words[:k]]
            if final_suffix == curr_prefix:
                # Omit matched k words
                remaining_words = curr_words[k:]
                return " ".join(remaining_words).strip()

        # Exact substring prefix check
        if current_text.startswith(final_text_clean := finalized_text.strip()):
            return current_text[len(final_text_clean):].strip()

        return current_text.strip()
