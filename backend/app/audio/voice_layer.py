"""
Voice Layer — Synthetic-speech detection and voiceprint matching.

Implementation Plan §5.4 (NEW in v3):

  Check A: Synthetic-speech / spoof detection
    - Uses a pretrained deepfake / anti-spoofing model
    - Primary: wav2vec2-based deepfake classifier (HuggingFace)
    - Fallback: AASIST-compatible interface
    - Output: spoof_prob ∈ [0, 1]

  Check B: Voiceprint match
    - Uses SpeechBrain ECAPA-TDNN speaker embeddings
    - Cosine similarity vs enrolled contact voiceprint
    - Output: similarity ∈ [0, 1]

Design rules (from plan):
  1. Runs in a background thread — never blocks ASR / Tier 1
  2. Stores embeddings only, never raw audio
  3. Quality gate: short duration / low SNR → "inconclusive"
  4. Degrades gracefully to "unavailable" on any failure
"""
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.audio.preprocessor import get_audio_duration, estimate_snr

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
    logger.warning("PyTorch not installed — voice layer will be unavailable.")

try:
    from transformers import AutoFeatureExtractor, AutoModelForAudioClassification  # type: ignore
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("transformers not installed — Check A (spoof detection) unavailable.")

try:
    from speechbrain.inference.speaker import SpeakerRecognition  # type: ignore
    SPEECHBRAIN_AVAILABLE = True
except ImportError:
    SPEECHBRAIN_AVAILABLE = False
    logger.warning("speechbrain not installed — Check B (voiceprint) unavailable.")

# ── Quality gate thresholds (from plan §5.4) ──────────────────────────────────
MIN_SPEECH_SECONDS = 3.0     # require at least 3s of speech
MIN_SNR_DB = 5.0             # require SNR ≥ 5 dB

# Spoof detection model (HuggingFace, wav2vec2-based deepfake classifier)
SPOOF_MODEL_ID = "facebook/wav2vec2-base"  # placeholder — swap with validated model
# e.g. "mo-thecreator/deepfake-audio-detection" or similar

# SpeechBrain ECAPA-TDNN for voiceprints
ECAPA_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"


@dataclass
class SpeakerMatch:
    """Result of comparing caller voice to an enrolled voiceprint."""
    claimed_contact: str
    similarity: float          # cosine similarity 0-1
    enrolled: bool = True
    threshold: float = 0.75   # tune from test data


@dataclass
class VoiceEvidence:
    """
    The VoiceEvidence JSON contract (§4 Data Contracts).
    status: "ok" | "inconclusive" | "unavailable"
    """
    status: str                        # ok | inconclusive | unavailable
    spoof_prob: Optional[float] = None # Check A result
    windows_analyzed: int = 0
    speaker_match: Optional[SpeakerMatch] = None  # Check B result
    duration_s: float = 0.0
    snr_db: float = 0.0
    model: str = ""
    processing_time_s: float = 0.0
    error: Optional[str] = None


class VoiceLayer:
    """
    Orchestrates Check A (synthetic detection) and Check B (voiceprint).
    Designed to run as a background task — never blocks ASR.
    """

    def __init__(self):
        self._spoof_extractor = None
        self._spoof_model = None
        self._ecapa_model = None
        self._spoof_loaded = False
        self._ecapa_loaded = False

    # ── Check A: Spoof / Deepfake Detection ───────────────────────────────────

    def _load_spoof_model(self) -> bool:
        """Lazy-load the spoof detection model."""
        if self._spoof_loaded:
            return self._spoof_model is not None

        self._spoof_loaded = True
        if not TRANSFORMERS_AVAILABLE or not TORCH_AVAILABLE:
            logger.warning("Check A unavailable: transformers or torch missing.")
            return False
        try:
            logger.info(f"Loading spoof model: {SPOOF_MODEL_ID}…")
            self._spoof_extractor = AutoFeatureExtractor.from_pretrained(SPOOF_MODEL_ID)
            self._spoof_model = AutoModelForAudioClassification.from_pretrained(SPOOF_MODEL_ID)
            self._spoof_model.eval()
            logger.info("Spoof model loaded ✓")
            return True
        except Exception as e:
            logger.error(f"Failed to load spoof model: {e}")
            self._spoof_model = None
            return False

    def _spoof_prob_for_window(self, samples: "np.ndarray") -> float:
        """Run spoof detection on one audio window. Returns spoof_prob."""
        try:
            import torch
            inputs = self._spoof_extractor(
                samples,
                sampling_rate=16000,
                return_tensors="pt",
                padding=True,
            )
            with torch.no_grad():
                logits = self._spoof_model(**inputs).logits
                probs = torch.softmax(logits, dim=-1).squeeze()

            # Convention: class 0 = bonafide, class 1 = spoof
            # If model only has 1 class, handle gracefully
            if probs.ndim == 0:
                return float(probs.item())
            spoof_idx = 1 if probs.shape[0] > 1 else 0
            return float(probs[spoof_idx].item())
        except Exception as e:
            logger.debug(f"Window spoof detection error: {e}")
            return 0.5   # neutral on error

    def run_check_a(self, wav_path: Path) -> tuple[Optional[float], int]:
        """
        Run synthetic-speech detection over VAD-sliced windows.

        Returns:
            (median_spoof_prob, windows_analyzed)
        """
        if not self._load_spoof_model():
            return None, 0

        if not NUMPY_AVAILABLE:
            return None, 0

        try:
            import numpy as np
            import wave

            with wave.open(str(wav_path), "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

            sample_rate = 16000
            win_samples = int(sample_rate * 5)   # 5s windows
            hop_samples = int(sample_rate * 2.5) # 2.5s hop

            windows = [
                samples[i: i + win_samples]
                for i in range(0, len(samples) - win_samples, hop_samples)
            ]

            if not windows:
                return None, 0

            probs = [self._spoof_prob_for_window(w) for w in windows]
            median_prob = float(np.median(probs))
            logger.info(
                f"Check A: {len(windows)} windows, "
                f"spoof_prob median={median_prob:.3f}"
            )
            return median_prob, len(windows)

        except Exception as e:
            logger.error(f"Check A failed: {e}", exc_info=True)
            return None, 0

    # ── Check B: Voiceprint Match ─────────────────────────────────────────────

    def _load_ecapa(self) -> bool:
        """Lazy-load SpeechBrain ECAPA-TDNN."""
        if self._ecapa_loaded:
            return self._ecapa_model is not None

        self._ecapa_loaded = True
        if not SPEECHBRAIN_AVAILABLE:
            logger.warning("Check B unavailable: speechbrain missing.")
            return False
        try:
            logger.info(f"Loading ECAPA-TDNN: {ECAPA_SOURCE}…")
            self._ecapa_model = SpeakerRecognition.from_hparams(
                source=ECAPA_SOURCE,
                savedir="pretrained_models/ecapa-tdnn",
            )
            logger.info("ECAPA-TDNN loaded ✓")
            return True
        except Exception as e:
            logger.error(f"Failed to load ECAPA-TDNN: {e}")
            self._ecapa_model = None
            return False

    def get_embedding(self, wav_path: Path) -> Optional["np.ndarray"]:
        """
        Compute a speaker embedding for the given WAV file.
        Used for enrollment and for comparison during analysis.
        """
        if not self._load_ecapa() or not NUMPY_AVAILABLE:
            return None
        try:
            import torchaudio
            signal, fs = torchaudio.load(str(wav_path))
            embedding = self._ecapa_model.encode_batch(signal)
            return embedding.squeeze().detach().numpy()
        except Exception as e:
            logger.error(f"Embedding extraction failed: {e}", exc_info=True)
            return None

    def cosine_similarity(self, emb1: "np.ndarray", emb2: "np.ndarray") -> float:
        """Compute cosine similarity between two embeddings."""
        try:
            import numpy as np
            n1 = np.linalg.norm(emb1)
            n2 = np.linalg.norm(emb2)
            if n1 == 0 or n2 == 0:
                return 0.0
            return float(np.dot(emb1, emb2) / (n1 * n2))
        except Exception:
            return 0.0

    def run_check_b(
        self,
        wav_path: Path,
        claimed_contact: str,
        enrolled_embedding: "np.ndarray",
    ) -> Optional[SpeakerMatch]:
        """
        Compare caller voice embedding to enrolled contact voiceprint.

        Args:
            wav_path:           Caller's audio (16 kHz mono WAV).
            claimed_contact:    Name of the claimed identity.
            enrolled_embedding: Stored embedding for that contact.

        Returns:
            SpeakerMatch or None if unavailable.
        """
        caller_embedding = self.get_embedding(wav_path)
        if caller_embedding is None or enrolled_embedding is None:
            return None

        similarity = self.cosine_similarity(caller_embedding, enrolled_embedding)
        logger.info(
            f"Check B: claimed={claimed_contact}, similarity={similarity:.3f}"
        )
        return SpeakerMatch(
            claimed_contact=claimed_contact,
            similarity=round(similarity, 4),
            enrolled=True,
        )

    # ── Main entry point ──────────────────────────────────────────────────────

    def analyze(
        self,
        wav_path: Path,
        claimed_contact: Optional[str] = None,
        enrolled_embedding: Optional["np.ndarray"] = None,
    ) -> VoiceEvidence:
        """
        Run the full voice layer (Check A + Check B) on a 16 kHz mono WAV.

        Design rules:
          - Quality gate checked first
          - Check A always runs if model is available
          - Check B only runs if claimed_contact + enrolled_embedding provided
          - Any failure returns "unavailable" — never breaks the main pipeline

        Returns:
            VoiceEvidence dataclass
        """
        t0 = time.perf_counter()

        try:
            # ── Quality gate ─────────────────────────────────────────────────
            duration = get_audio_duration(wav_path)
            snr = estimate_snr(wav_path)

            if duration < MIN_SPEECH_SECONDS or (snr > 0 and snr < MIN_SNR_DB):
                reason = (
                    f"duration={duration:.1f}s < {MIN_SPEECH_SECONDS}s"
                    if duration < MIN_SPEECH_SECONDS
                    else f"SNR={snr:.1f}dB < {MIN_SNR_DB}dB"
                )
                logger.info(f"Voice layer: inconclusive ({reason})")
                return VoiceEvidence(
                    status="inconclusive",
                    duration_s=round(duration, 2),
                    snr_db=round(snr, 2),
                    processing_time_s=round(time.perf_counter() - t0, 2),
                    error=reason,
                )

            # ── Check A: Synthetic-speech detection ───────────────────────────
            spoof_prob, windows_analyzed = self.run_check_a(wav_path)

            # ── Check B: Voiceprint match ─────────────────────────────────────
            speaker_match: Optional[SpeakerMatch] = None
            if (
                claimed_contact
                and enrolled_embedding is not None
                and SPEECHBRAIN_AVAILABLE
            ):
                speaker_match = self.run_check_b(
                    wav_path, claimed_contact, enrolled_embedding
                )

            processing_time = round(time.perf_counter() - t0, 2)

            return VoiceEvidence(
                status="ok",
                spoof_prob=round(spoof_prob, 4) if spoof_prob is not None else None,
                windows_analyzed=windows_analyzed,
                speaker_match=speaker_match,
                duration_s=round(duration, 2),
                snr_db=round(snr, 2),
                model=f"Check A: {SPOOF_MODEL_ID} | Check B: {ECAPA_SOURCE}",
                processing_time_s=processing_time,
            )

        except Exception as e:
            logger.error(f"Voice layer failed: {e}", exc_info=True)
            return VoiceEvidence(
                status="unavailable",
                processing_time_s=round(time.perf_counter() - t0, 2),
                error=str(e),
            )


# ── Singleton ─────────────────────────────────────────────────────────────────
_voice_layer_instance: Optional[VoiceLayer] = None


def get_voice_layer() -> VoiceLayer:
    """Return (or create) the global VoiceLayer singleton."""
    global _voice_layer_instance
    if _voice_layer_instance is None:
        _voice_layer_instance = VoiceLayer()
    return _voice_layer_instance
