"""
AI Voice Detector — Synthetic-speech / deepfake audio detection service.

Dedicated service for detecting AI-generated or spoofed speech in audio recordings.
This is SEPARATE from voiceprint matching (speaker similarity) and ASR (transcription).

Model: Vansh180/deepfake-audio-wav2vec2
  - Architecture: wav2vec2-base with binary classification head
  - Training data: ASVspoof 2021 PA (Physical Access) dataset
  - Labels: {0: 'real', 1: 'fake'}
  - Input: 16 kHz mono audio
  - Output: logits → softmax → P(real), P(fake)

IMPORTANT LIMITATIONS:
  - Scores are uncalibrated softmax outputs, NOT true probabilities.
  - Model was trained on ASVspoof 2021 PA dataset which focuses on physical
    access (replay) attacks. It may not generalize well to:
      · Modern TTS systems (ElevenLabs, Bark, XTTS, etc.)
      · Voice cloning / conversion attacks
      · Compressed telephony audio (8kHz narrowband)
      · Indian English accents and code-mixing
  - A low spoof score does NOT prove speech is genuine.
  - A high spoof score does NOT prove speech is AI-generated with certainty.
  - Without calibration on representative data, specific probability thresholds
    cannot be claimed to correspond to fixed false-positive/negative rates.
"""
import logging
import time
import wave
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Optional heavy imports ────────────────────────────────────────────────────
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


# ── Constants ─────────────────────────────────────────────────────────────────

# Model identifier on HuggingFace
DETECTOR_MODEL_ID = "Vansh180/deepfake-audio-wav2vec2"

# Expected input sample rate
EXPECTED_SAMPLE_RATE = 16000

# Audio analysis constraints
MIN_DURATION_S = 1.0        # Minimum audio duration for analysis
MAX_DURATION_S = 600.0      # Maximum audio duration (10 min)
WINDOW_DURATION_S = 5.0     # Analysis window size
WINDOW_HOP_S = 2.5          # Window hop (50% overlap)
MIN_WINDOW_S = 3.0          # Minimum valid window length

# Silence detection threshold (RMS amplitude)
SILENCE_RMS_THRESHOLD = 0.001


class AIVoiceStatus(str, Enum):
    """
    Possible statuses for AI voice detection.

    ai_generated_or_spoof_suspected: Model output suggests synthetic/spoofed speech.
    likely_genuine: Model output does not suggest synthetic speech.
    inconclusive: Audio quality, duration, or model confidence insufficient.
    unavailable: Model could not run (missing deps, load failure, etc).
    """
    AI_GENERATED_OR_SPOOF_SUSPECTED = "ai_generated_or_spoof_suspected"
    LIKELY_GENUINE = "likely_genuine"
    INCONCLUSIVE = "inconclusive"
    UNAVAILABLE = "unavailable"


@dataclass
class AIVoiceDetectionResult:
    """
    Result from the AI voice detector.

    All fields are explicitly typed and documented.
    Scores are labeled as uncalibrated softmax outputs.
    """
    # Status determination
    ai_voice_status: str          # One of AIVoiceStatus values

    # Model raw outputs (None if model didn't run)
    spoof_score: Optional[float] = None        # P(fake) from softmax, 0-1
    genuine_score: Optional[float] = None      # P(real) from softmax, 0-1
    score_type: str = "uncalibrated_softmax"   # Always identify the score type

    # Model metadata
    detector_model: str = DETECTOR_MODEL_ID
    detector_version: str = "wav2vec2-base-asvspoof2021-pa"

    # Analysis metadata
    windows_analyzed: int = 0
    audio_duration_s: float = 0.0
    audio_sample_rate: int = EXPECTED_SAMPLE_RATE
    processing_time_s: float = 0.0

    # Window-level detail (for transparency)
    window_scores: list = field(default_factory=list)

    # Explanation
    evidence: list = field(default_factory=list)     # Human-readable evidence items
    limitations: list = field(default_factory=list)   # Known limitations for this result
    error: Optional[str] = None                       # Error message if unavailable

    @property
    def is_actionable(self) -> bool:
        """Whether this result provides actionable detection information."""
        return self.ai_voice_status in (
            AIVoiceStatus.AI_GENERATED_OR_SPOOF_SUSPECTED.value,
            AIVoiceStatus.LIKELY_GENUINE.value,
        )


class AIVoiceDetector:
    """
    Singleton AI voice detector service.

    Wraps the Vansh180/deepfake-audio-wav2vec2 binary classifier.
    Loads model lazily on first use and caches it for subsequent requests.

    Thread-safety: Model inference is done under torch.no_grad() and the model
    is in eval mode. Multiple concurrent reads are safe with CPython GIL.
    """

    def __init__(self):
        self._model = None
        self._feature_extractor = None
        self._loaded = False
        self._load_error: Optional[str] = None

    def _load_model(self) -> bool:
        """
        Lazy-load the detection model. Called once on first inference.

        Returns:
            True if model is ready for inference.
        """
        if self._loaded:
            return self._model is not None

        self._loaded = True

        # Check dependencies
        if not NUMPY_AVAILABLE:
            self._load_error = "numpy is not installed"
            logger.warning(f"AI Voice Detector unavailable: {self._load_error}")
            return False

        if not TORCH_AVAILABLE:
            self._load_error = "PyTorch is not installed"
            logger.warning(f"AI Voice Detector unavailable: {self._load_error}")
            return False

        if not TRANSFORMERS_AVAILABLE:
            self._load_error = "transformers library is not installed"
            logger.warning(f"AI Voice Detector unavailable: {self._load_error}")
            return False

        try:
            logger.info(f"Loading AI voice detector: {DETECTOR_MODEL_ID}...")
            self._feature_extractor = AutoFeatureExtractor.from_pretrained(
                DETECTOR_MODEL_ID
            )
            self._model = AutoModelForAudioClassification.from_pretrained(
                DETECTOR_MODEL_ID
            )
            self._model.eval()

            # Verify model config
            config = self._model.config
            if config.num_labels != 2:
                self._load_error = (
                    f"Expected binary classifier (2 labels), "
                    f"got {config.num_labels} labels"
                )
                logger.error(f"AI Voice Detector: {self._load_error}")
                self._model = None
                return False

            # Verify label mapping
            id2label = config.id2label
            if id2label.get(0) != 'real' or id2label.get(1) != 'fake':
                self._load_error = (
                    f"Unexpected label mapping: {id2label}. "
                    f"Expected {{0: 'real', 1: 'fake'}}"
                )
                logger.error(f"AI Voice Detector: {self._load_error}")
                self._model = None
                return False

            logger.info(
                f"AI Voice Detector loaded ✓ "
                f"(labels: {id2label}, device: cpu)"
            )
            return True

        except Exception as e:
            self._load_error = f"Failed to load model: {str(e)[:200]}"
            logger.error(f"AI Voice Detector: {self._load_error}")
            self._model = None
            return False

    def _infer_window(self, samples: "np.ndarray") -> tuple[float, float]:
        """
        Run inference on a single audio window.

        Args:
            samples: Float32 numpy array of audio samples, normalized to [-1, 1].

        Returns:
            (genuine_score, spoof_score) — softmax probabilities for each class.
        """
        import torch

        inputs = self._feature_extractor(
            samples,
            sampling_rate=EXPECTED_SAMPLE_RATE,
            return_tensors="pt",
            padding=True,
        )
        with torch.no_grad():
            logits = self._model(**inputs).logits
            probs = torch.softmax(logits, dim=-1).squeeze()

        if probs.ndim == 0 or probs.shape[0] < 2:
            logger.warning(
                f"Model returned unexpected output shape: {probs.shape}"
            )
            return 0.5, 0.5

        genuine_score = float(probs[0].item())  # class 0 = real
        spoof_score = float(probs[1].item())     # class 1 = fake
        return genuine_score, spoof_score

    def _is_silence(self, samples: "np.ndarray") -> bool:
        """Check if audio window is effectively silence."""
        import numpy as np
        rms = float(np.sqrt(np.mean(samples ** 2)))
        return rms < SILENCE_RMS_THRESHOLD

    def _read_wav(self, wav_path: Path) -> tuple[Optional["np.ndarray"], float, str]:
        """
        Read a WAV file and return samples, duration, and any error.

        Returns:
            (samples, duration_s, error_message)
            samples is None if reading failed.
        """
        import numpy as np

        try:
            with wave.open(str(wav_path), "rb") as wf:
                n_channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                frame_rate = wf.getframerate()
                n_frames = wf.getnframes()
                raw_frames = wf.readframes(n_frames)

            if n_frames == 0:
                return None, 0.0, "Audio file contains no frames"

            duration_s = n_frames / float(frame_rate)

            # Convert to float32 normalized samples
            if sample_width == 2:
                samples = np.frombuffer(raw_frames, dtype=np.int16).astype(np.float32)
                samples = samples / 32768.0
            elif sample_width == 4:
                samples = np.frombuffer(raw_frames, dtype=np.int32).astype(np.float32)
                samples = samples / 2147483648.0
            else:
                return None, duration_s, f"Unsupported sample width: {sample_width}"

            # If stereo, take first channel
            if n_channels > 1:
                samples = samples[::n_channels]

            return samples, duration_s, ""

        except wave.Error as e:
            return None, 0.0, f"Invalid WAV file: {e}"
        except Exception as e:
            return None, 0.0, f"Error reading audio: {e}"

    def detect(self, wav_path: Path) -> AIVoiceDetectionResult:
        """
        Analyze an audio file for AI-generated / synthetic speech.

        Accepts a 16 kHz mono WAV file (the preprocessor should convert
        other formats before calling this).

        The method:
          1. Validates the audio file.
          2. Splits it into overlapping windows.
          3. Runs the binary classifier on each window.
          4. Aggregates window scores (median).
          5. Returns a structured result with honest score interpretation.

        Args:
            wav_path: Path to a 16 kHz mono WAV file.

        Returns:
            AIVoiceDetectionResult with status, scores, evidence, and limitations.
        """
        t0 = time.perf_counter()
        limitations = [
            "Model trained on ASVspoof 2021 PA dataset — may not detect "
            "modern TTS/voice-cloning attacks not in training data.",
            "Scores are uncalibrated softmax outputs, not true probabilities.",
        ]

        # ── Check model availability ──────────────────────────────────────
        if not self._load_model():
            return AIVoiceDetectionResult(
                ai_voice_status=AIVoiceStatus.UNAVAILABLE.value,
                error=self._load_error or "Model not available",
                limitations=limitations + [
                    "Detection model could not be loaded. "
                    "This result does NOT mean the audio is genuine."
                ],
                evidence=["AI voice detection was not performed due to model unavailability."],
                processing_time_s=round(time.perf_counter() - t0, 3),
            )

        import numpy as np

        # ── Validate input ────────────────────────────────────────────────
        if not wav_path.exists():
            return AIVoiceDetectionResult(
                ai_voice_status=AIVoiceStatus.UNAVAILABLE.value,
                error=f"Audio file not found: {wav_path.name}",
                limitations=limitations,
                processing_time_s=round(time.perf_counter() - t0, 3),
            )

        # ── Read audio ────────────────────────────────────────────────────
        samples, duration_s, read_error = self._read_wav(wav_path)
        if samples is None:
            return AIVoiceDetectionResult(
                ai_voice_status=AIVoiceStatus.INCONCLUSIVE.value,
                audio_duration_s=duration_s,
                error=read_error,
                limitations=limitations,
                evidence=[f"Could not read audio: {read_error}"],
                processing_time_s=round(time.perf_counter() - t0, 3),
            )

        # ── Duration checks ───────────────────────────────────────────────
        if duration_s < MIN_DURATION_S:
            return AIVoiceDetectionResult(
                ai_voice_status=AIVoiceStatus.INCONCLUSIVE.value,
                audio_duration_s=round(duration_s, 2),
                error=f"Audio too short ({duration_s:.1f}s < {MIN_DURATION_S}s minimum)",
                limitations=limitations,
                evidence=[
                    f"Audio duration {duration_s:.1f}s is below the {MIN_DURATION_S}s "
                    f"minimum required for reliable detection."
                ],
                processing_time_s=round(time.perf_counter() - t0, 3),
            )

        # ── Check for silence ─────────────────────────────────────────────
        if self._is_silence(samples):
            return AIVoiceDetectionResult(
                ai_voice_status=AIVoiceStatus.INCONCLUSIVE.value,
                audio_duration_s=round(duration_s, 2),
                error="Audio appears to be silence or near-silence",
                limitations=limitations,
                evidence=["Audio contains no detectable speech content."],
                processing_time_s=round(time.perf_counter() - t0, 3),
            )

        # ── Windowed inference ────────────────────────────────────────────
        win_samples = int(EXPECTED_SAMPLE_RATE * WINDOW_DURATION_S)
        hop_samples = int(EXPECTED_SAMPLE_RATE * WINDOW_HOP_S)

        window_genuine = []
        window_spoof = []

        for start in range(0, len(samples), hop_samples):
            window = samples[start:start + win_samples]
            if len(window) < int(EXPECTED_SAMPLE_RATE * MIN_WINDOW_S):
                break  # Window too short

            # Skip silent windows
            if self._is_silence(window):
                continue

            try:
                g_score, s_score = self._infer_window(window)
                window_genuine.append(g_score)
                window_spoof.append(s_score)
            except Exception as e:
                logger.warning(f"Window inference error (skipping): {e}")
                continue

        processing_time = round(time.perf_counter() - t0, 3)

        # ── No valid windows ──────────────────────────────────────────────
        if not window_spoof:
            return AIVoiceDetectionResult(
                ai_voice_status=AIVoiceStatus.INCONCLUSIVE.value,
                audio_duration_s=round(duration_s, 2),
                error="No valid speech windows could be analyzed",
                limitations=limitations,
                evidence=[
                    "Audio did not contain enough non-silent content for analysis."
                ],
                processing_time_s=processing_time,
            )

        # ── Aggregate scores ──────────────────────────────────────────────
        median_spoof = float(np.median(window_spoof))
        median_genuine = float(np.median(window_genuine))
        mean_spoof = float(np.mean(window_spoof))
        std_spoof = float(np.std(window_spoof))

        # ── Determine status ──────────────────────────────────────────────
        # These thresholds are based on the model's softmax output distribution
        # on the ASVspoof dataset. They are NOT calibrated on our deployment data.
        # We use two thresholds to distinguish likely-genuine from suspected-spoof,
        # with an inconclusive zone in between for borderline cases.
        THRESHOLD_HIGH = 0.80   # Strong spoof signal
        THRESHOLD_MEDIUM = 0.60  # Moderate spoof signal
        # Below 0.60: leaning genuine

        evidence_items = []
        evidence_items.append(
            f"Analyzed {len(window_spoof)} audio window(s) "
            f"(median spoof score: {median_spoof:.4f}, "
            f"mean: {mean_spoof:.4f}, std: {std_spoof:.4f})"
        )

        if median_spoof >= THRESHOLD_HIGH:
            status = AIVoiceStatus.AI_GENERATED_OR_SPOOF_SUSPECTED.value
            evidence_items.append(
                f"Median spoof score {median_spoof:.4f} exceeds high threshold "
                f"({THRESHOLD_HIGH}). The model's output suggests this audio "
                f"may contain synthetic or replayed speech."
            )
        elif median_spoof >= THRESHOLD_MEDIUM:
            status = AIVoiceStatus.INCONCLUSIVE.value
            evidence_items.append(
                f"Median spoof score {median_spoof:.4f} is in the moderate zone "
                f"({THRESHOLD_MEDIUM}–{THRESHOLD_HIGH}). The model output is "
                f"ambiguous — cannot confidently classify as genuine or synthetic."
            )
            limitations.append(
                "Score falls in the ambiguous range. Additional verification "
                "is recommended."
            )
        else:
            status = AIVoiceStatus.LIKELY_GENUINE.value
            evidence_items.append(
                f"Median spoof score {median_spoof:.4f} is below the medium "
                f"threshold ({THRESHOLD_MEDIUM}). The model does not flag this "
                f"audio as synthetic, but this does NOT guarantee authenticity."
            )

        # High variance warning
        if std_spoof > 0.2 and len(window_spoof) > 1:
            evidence_items.append(
                f"High score variance across windows (std={std_spoof:.4f}). "
                f"Detection consistency is low — treat result with caution."
            )
            if status == AIVoiceStatus.LIKELY_GENUINE.value:
                status = AIVoiceStatus.INCONCLUSIVE.value
                evidence_items.append(
                    "Status changed to inconclusive due to high variance."
                )

        return AIVoiceDetectionResult(
            ai_voice_status=status,
            spoof_score=round(median_spoof, 4),
            genuine_score=round(median_genuine, 4),
            score_type="uncalibrated_softmax",
            detector_model=DETECTOR_MODEL_ID,
            detector_version="wav2vec2-base-asvspoof2021-pa",
            windows_analyzed=len(window_spoof),
            audio_duration_s=round(duration_s, 2),
            audio_sample_rate=EXPECTED_SAMPLE_RATE,
            processing_time_s=processing_time,
            window_scores=[round(s, 4) for s in window_spoof],
            evidence=evidence_items,
            limitations=limitations,
        )


# ── Singleton ─────────────────────────────────────────────────────────────────
_detector_instance: Optional[AIVoiceDetector] = None


def get_ai_voice_detector() -> AIVoiceDetector:
    """Return (or create) the global AIVoiceDetector singleton."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = AIVoiceDetector()
    return _detector_instance
