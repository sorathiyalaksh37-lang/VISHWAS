"""
ASR (Automatic Speech Recognition) service using faster-whisper.

Implementation Plan §3 pipeline step [2]:
  faster-whisper (base/small, int8, VAD) → timestamped segments + language detection

Supports:
- English, Hindi, Hinglish (auto-detected)
- Voice Activity Detection (VAD) filter
- Graceful fallback if faster-whisper is not installed
"""
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Try importing faster-whisper ──────────────────────────────────────────────
try:
    from faster_whisper import WhisperModel  # type: ignore
    FASTER_WHISPER_AVAILABLE = True
    logger.info("faster-whisper is available ✓")
    
    # Monkey-patch PyAV to fix metadata_errors compatibility issue with PyAV 19.x
    # faster-whisper internally uses av.open() with metadata_errors parameter
    # which was added after PyAV 11.0 but the signature changed in 19.x
    try:
        import av
        _original_av_open = av.open
        def _patched_av_open(file, *args, metadata_errors="ignore", **kwargs):
            # Remove metadata_errors if it causes issues
            try:
                return _original_av_open(file, *args, metadata_errors=metadata_errors, **kwargs)
            except TypeError:
                # If metadata_errors is not supported, try without it
                return _original_av_open(file, *args, **kwargs)
        av.open = _patched_av_open
        logger.info("Applied PyAV compatibility patch for metadata_errors")
    except Exception as e:
        logger.warning(f"Could not patch PyAV: {e}")
        
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logger.warning(
        "faster-whisper not installed. ASR will return empty transcript. "
        "Install with: pip install faster-whisper"
    )


@dataclass
class TranscriptSegment:
    """One timestamped segment of speech."""
    start: float            # seconds
    end: float              # seconds
    text: str
    language: Optional[str] = None
    speaker: Optional[str] = None
    confidence: float = 1.0  # word-level avg if available


@dataclass
class ASRResult:
    """Full result returned by the ASR service."""
    call_id: str
    language: Optional[str]
    language_probability: float
    segments: list[TranscriptSegment] = field(default_factory=list)
    transcription_status: str = "completed"   # completed | failed | unavailable
    duration_seconds: float = 0.0
    processing_time_seconds: float = 0.0
    model_name: str = "faster-whisper"
    is_mock: bool = False
    error: Optional[str] = None


class ASRService:
    """
    Wraps faster-whisper for audio transcription.

    Model selection:
      - 'base'  — fast, good for demos (default)
      - 'small' — more accurate, ~2× slower
      - 'medium'— high accuracy, 4× slower

    Compute type:
      - 'int8'  — fastest, lowest memory (recommended for CPU)
      - 'float16' — faster on GPU
    """

    def __init__(
        self,
        model_size: str = "base",
        compute_type: str = "int8",
        device: str = "cpu",
    ):
        self.model_size = model_size
        self.compute_type = compute_type
        self.device = device
        self._model: Optional[object] = None

    def _load_model(self) -> bool:
        """Lazy-load the Whisper model (only once)."""
        if self._model is not None:
            return True
        if not FASTER_WHISPER_AVAILABLE:
            return False
        try:
            logger.info(
                f"Loading faster-whisper model: {self.model_size} "
                f"({self.compute_type} on {self.device})…"
            )
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("faster-whisper model loaded ✓")
            return True
        except Exception as e:
            logger.error(f"Failed to load faster-whisper model: {e}")
            return False

    def transcribe(
        self,
        wav_path: Path,
        call_id: str,
        language: Optional[str] = None,   # None = auto-detect
        vad_filter: bool = True,
    ) -> ASRResult:
        """
        Transcribe a 16 kHz mono WAV file.

        Args:
            wav_path:   Path to preprocessed WAV.
            call_id:    UUID of the call (for logging).
            language:   Force language code (e.g. 'en', 'hi'). None = auto.
            vad_filter: Apply VAD to skip silence (recommended).

        Returns:
            ASRResult with timestamped TranscriptSegment list.
        """
        if not self._load_model():
            return ASRResult(
                call_id=call_id,
                language=None,
                language_probability=0.0,
                transcription_status="unavailable",
                is_mock=False,
                error="faster-whisper not installed or failed to load",
            )

        t0 = time.perf_counter()
        try:
            logger.info(f"[{call_id}] Starting ASR transcription: {wav_path}")

            segments_iter, info = self._model.transcribe(
                str(wav_path),
                language=language,
                vad_filter=vad_filter,
                vad_parameters={
                    "min_silence_duration_ms": 500,
                    "speech_pad_ms": 200,
                },
                word_timestamps=False,  # set True for word-level timing
                beam_size=5,
            )

            segments: list[TranscriptSegment] = []
            for seg in segments_iter:
                text = seg.text.strip()
                if not text:
                    continue
                segments.append(
                    TranscriptSegment(
                        start=round(seg.start, 3),
                        end=round(seg.end, 3),
                        text=text,
                        language=info.language,
                        confidence=round(getattr(seg, "avg_logprob", 0.0) + 1.0, 3),
                    )
                )

            processing_time = round(time.perf_counter() - t0, 2)
            logger.info(
                f"[{call_id}] ASR done: {len(segments)} segments, "
                f"lang={info.language} ({info.language_probability:.2f}), "
                f"took {processing_time}s"
            )

            return ASRResult(
                call_id=call_id,
                language=info.language,
                language_probability=round(info.language_probability, 3),
                segments=segments,
                transcription_status="completed",
                duration_seconds=round(info.duration, 2),
                processing_time_seconds=processing_time,
                model_name=f"faster-whisper-{self.model_size}",
                is_mock=False,
            )

        except Exception as e:
            processing_time = round(time.perf_counter() - t0, 2)
            logger.error(f"[{call_id}] ASR failed after {processing_time}s: {e}", exc_info=True)
            return ASRResult(
                call_id=call_id,
                language=None,
                language_probability=0.0,
                transcription_status="failed",
                processing_time_seconds=processing_time,
                is_mock=False,
                error=str(e),
            )


# ── Singleton ─────────────────────────────────────────────────────────────────
# Loaded lazily on first use — avoids blocking startup.
_asr_service_instance: Optional[ASRService] = None


def get_asr_service(model_size: str = "base") -> ASRService:
    """Return (or create) the global ASRService singleton."""
    global _asr_service_instance
    if _asr_service_instance is None:
        _asr_service_instance = ASRService(model_size=model_size)
    return _asr_service_instance
