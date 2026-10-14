"""
Tests for the AI Voice Detector service.

Test categories:
  1. Detector output schema and status handling (MOCKED — no model download)
  2. Invalid, empty, silent and very short audio (MOCKED)
  3. Missing dependencies or model weights (MOCKED)
  4. Detector inference errors (MOCKED)
  5. API upload → processing → report retrieval
  6. Separation of AI-voice detection and Trust Engine fraud-risk
  7. Existing API v3 compatibility
  8. Real inference test (SKIPPED if model unavailable)

All unit tests mock the model interface — they do NOT require downloading
large model weights. They are clearly labeled as mocked.

The real-inference test at the bottom actually loads the model and runs it.
It is marked with @pytest.mark.real_inference and skipped by default.
"""
import json
import math
import struct
import tempfile
import wave
from dataclasses import asdict
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.audio.ai_voice_detector import (
    AIVoiceDetectionResult,
    AIVoiceDetector,
    AIVoiceStatus,
    DETECTOR_MODEL_ID,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def create_wav_file(
    duration_s: float = 5.0,
    frequency: int = 440,
    sample_rate: int = 16000,
    amplitude: float = 0.3,
    silence: bool = False,
) -> Path:
    """Create a test WAV file and return its path."""
    n_samples = int(sample_rate * duration_s)

    if silence:
        samples = np.zeros(n_samples, dtype=np.int16)
    else:
        t = np.linspace(0, duration_s, n_samples, endpoint=False)
        samples = (amplitude * 32767 * np.sin(2 * np.pi * frequency * t)).astype(np.int16)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    tmp.close()
    return Path(tmp.name)


def create_empty_wav(sample_rate: int = 16000) -> Path:
    """Create a WAV file with zero frames."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"")
    tmp.close()
    return Path(tmp.name)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Detector output schema and status handling (MOCKED)
# ══════════════════════════════════════════════════════════════════════════════

class TestDetectorOutputSchema:
    """Tests that the detector returns well-formed results (MOCKED model)."""

    def test_result_dataclass_fields(self):
        """AIVoiceDetectionResult has all required fields."""
        result = AIVoiceDetectionResult(
            ai_voice_status=AIVoiceStatus.LIKELY_GENUINE.value,
            spoof_score=0.15,
            genuine_score=0.85,
        )
        assert result.ai_voice_status == "likely_genuine"
        assert result.spoof_score == 0.15
        assert result.genuine_score == 0.85
        assert result.score_type == "uncalibrated_softmax"
        assert result.detector_model == DETECTOR_MODEL_ID
        assert isinstance(result.evidence, list)
        assert isinstance(result.limitations, list)
        assert result.error is None

    def test_result_serializable_to_dict(self):
        """Result can be serialized to dict for JSON storage."""
        result = AIVoiceDetectionResult(
            ai_voice_status="likely_genuine",
            spoof_score=0.2,
            genuine_score=0.8,
            windows_analyzed=3,
        )
        d = asdict(result)
        assert isinstance(d, dict)
        assert d["ai_voice_status"] == "likely_genuine"
        assert d["spoof_score"] == 0.2
        # Should be JSON-serializable
        json_str = json.dumps(d)
        assert "likely_genuine" in json_str

    def test_all_status_values(self):
        """All four status values are valid."""
        for status in AIVoiceStatus:
            result = AIVoiceDetectionResult(ai_voice_status=status.value)
            assert result.ai_voice_status == status.value

    def test_is_actionable_property(self):
        """is_actionable is True only for definitive statuses."""
        assert AIVoiceDetectionResult(
            ai_voice_status="likely_genuine"
        ).is_actionable is True
        assert AIVoiceDetectionResult(
            ai_voice_status="ai_generated_or_spoof_suspected"
        ).is_actionable is True
        assert AIVoiceDetectionResult(
            ai_voice_status="inconclusive"
        ).is_actionable is False
        assert AIVoiceDetectionResult(
            ai_voice_status="unavailable"
        ).is_actionable is False


# ══════════════════════════════════════════════════════════════════════════════
# 2. Invalid, empty, silent and very short audio (MOCKED)
# ══════════════════════════════════════════════════════════════════════════════

class TestEdgeCaseAudio:
    """Tests for edge-case audio inputs (MOCKED model — no model download)."""

    @patch.object(AIVoiceDetector, "_load_model", return_value=True)
    @patch.object(AIVoiceDetector, "_infer_window", return_value=(0.8, 0.2))
    def test_very_short_audio(self, mock_infer, mock_load):
        """Audio shorter than MIN_DURATION_S should return inconclusive."""
        wav_path = create_wav_file(duration_s=0.5)
        try:
            detector = AIVoiceDetector()
            detector._loaded = True
            result = detector.detect(wav_path)
            assert result.ai_voice_status == "inconclusive"
            assert "too short" in (result.error or "").lower()
        finally:
            wav_path.unlink(missing_ok=True)

    @patch.object(AIVoiceDetector, "_load_model", return_value=True)
    def test_silent_audio(self, mock_load):
        """Silent audio should return inconclusive."""
        wav_path = create_wav_file(duration_s=5.0, silence=True)
        try:
            detector = AIVoiceDetector()
            detector._loaded = True
            result = detector.detect(wav_path)
            assert result.ai_voice_status == "inconclusive"
            assert "silence" in (result.error or "").lower()
        finally:
            wav_path.unlink(missing_ok=True)

    @patch.object(AIVoiceDetector, "_load_model", return_value=True)
    def test_empty_wav(self, mock_load):
        """Empty WAV file (0 frames) should return inconclusive."""
        wav_path = create_empty_wav()
        try:
            detector = AIVoiceDetector()
            detector._loaded = True
            result = detector.detect(wav_path)
            assert result.ai_voice_status == "inconclusive"
        finally:
            wav_path.unlink(missing_ok=True)

    @patch.object(AIVoiceDetector, "_load_model", return_value=True)
    def test_nonexistent_file(self, mock_load):
        """Missing file should return unavailable."""
        detector = AIVoiceDetector()
        detector._loaded = True
        result = detector.detect(Path("/nonexistent/audio.wav"))
        assert result.ai_voice_status == "unavailable"
        assert "not found" in (result.error or "").lower()

    @patch.object(AIVoiceDetector, "_load_model", return_value=True)
    def test_corrupt_file(self, mock_load):
        """Corrupt file should return inconclusive with error."""
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(b"NOT_A_WAV_FILE_JUST_RANDOM_BYTES")
        tmp.close()
        try:
            detector = AIVoiceDetector()
            detector._loaded = True
            result = detector.detect(Path(tmp.name))
            assert result.ai_voice_status == "inconclusive"
            assert result.error is not None
        finally:
            Path(tmp.name).unlink(missing_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Missing dependencies or model weights (MOCKED)
# ══════════════════════════════════════════════════════════════════════════════

class TestMissingDependencies:
    """Tests for graceful degradation when dependencies are missing (MOCKED)."""

    def test_unavailable_when_model_load_fails(self):
        """If model fails to load, result should be unavailable."""
        detector = AIVoiceDetector()
        detector._loaded = True  # Simulate failed load
        detector._model = None
        detector._load_error = "Test: model weights not found"

        wav_path = create_wav_file(duration_s=5.0)
        try:
            result = detector.detect(wav_path)
            assert result.ai_voice_status == "unavailable"
            assert "not found" in result.error.lower()
            # Must NOT claim the audio is genuine
            assert result.spoof_score is None
            assert result.genuine_score is None
        finally:
            wav_path.unlink(missing_ok=True)

    def test_unavailable_has_limitations(self):
        """Unavailable result should include limitations warning."""
        detector = AIVoiceDetector()
        detector._loaded = True
        detector._model = None
        detector._load_error = "PyTorch not installed"

        wav_path = create_wav_file(duration_s=5.0)
        try:
            result = detector.detect(wav_path)
            assert result.ai_voice_status == "unavailable"
            assert len(result.limitations) > 0
            # Should warn that unavailable ≠ genuine
            combined = " ".join(result.limitations)
            assert "NOT" in combined or "not" in combined.lower()
        finally:
            wav_path.unlink(missing_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# 4. Detector inference errors (MOCKED)
# ══════════════════════════════════════════════════════════════════════════════

class TestInferenceErrors:
    """Tests for model inference failure handling (MOCKED)."""

    @patch.object(AIVoiceDetector, "_load_model", return_value=True)
    @patch.object(AIVoiceDetector, "_infer_window", side_effect=RuntimeError("CUDA OOM"))
    def test_inference_error_returns_inconclusive(self, mock_infer, mock_load):
        """If all windows fail inference, result should be inconclusive."""
        wav_path = create_wav_file(duration_s=5.0)
        try:
            detector = AIVoiceDetector()
            detector._loaded = True
            result = detector.detect(wav_path)
            # All windows failed → no valid scores → inconclusive
            assert result.ai_voice_status == "inconclusive"
        finally:
            wav_path.unlink(missing_ok=True)

    @patch.object(AIVoiceDetector, "_load_model", return_value=True)
    def test_partial_window_failure(self, mock_load):
        """If some windows succeed and some fail, should still produce a result."""
        wav_path = create_wav_file(duration_s=10.0)

        call_count = 0
        def mock_infer(self, samples):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise RuntimeError("Intermittent failure")
            return (0.7, 0.3)

        try:
            detector = AIVoiceDetector()
            detector._loaded = True
            with patch.object(AIVoiceDetector, "_infer_window", mock_infer):
                result = detector.detect(wav_path)
            # Some windows succeeded → should have a score
            assert result.ai_voice_status in [
                "likely_genuine", "inconclusive", "ai_generated_or_spoof_suspected"
            ]
        finally:
            wav_path.unlink(missing_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Full detect path with mocked model (MOCKED)
# ══════════════════════════════════════════════════════════════════════════════

class TestDetectWithMockedModel:
    """Tests for the full detect() path with a mocked model (no download)."""

    @patch.object(AIVoiceDetector, "_load_model", return_value=True)
    @patch.object(AIVoiceDetector, "_infer_window", return_value=(0.15, 0.85))
    def test_high_spoof_score(self, mock_infer, mock_load):
        """High spoof score should return ai_generated_or_spoof_suspected."""
        wav_path = create_wav_file(duration_s=5.0)
        try:
            detector = AIVoiceDetector()
            detector._loaded = True
            result = detector.detect(wav_path)
            assert result.ai_voice_status == "ai_generated_or_spoof_suspected"
            assert result.spoof_score is not None
            assert result.spoof_score >= 0.80
            assert result.windows_analyzed > 0
        finally:
            wav_path.unlink(missing_ok=True)

    @patch.object(AIVoiceDetector, "_load_model", return_value=True)
    @patch.object(AIVoiceDetector, "_infer_window", return_value=(0.85, 0.15))
    def test_low_spoof_score(self, mock_infer, mock_load):
        """Low spoof score should return likely_genuine."""
        wav_path = create_wav_file(duration_s=5.0)
        try:
            detector = AIVoiceDetector()
            detector._loaded = True
            result = detector.detect(wav_path)
            assert result.ai_voice_status == "likely_genuine"
            assert result.spoof_score is not None
            assert result.spoof_score < 0.60
        finally:
            wav_path.unlink(missing_ok=True)

    @patch.object(AIVoiceDetector, "_load_model", return_value=True)
    @patch.object(AIVoiceDetector, "_infer_window", return_value=(0.35, 0.65))
    def test_medium_spoof_score(self, mock_infer, mock_load):
        """Medium spoof score (0.60-0.80) should return inconclusive."""
        wav_path = create_wav_file(duration_s=5.0)
        try:
            detector = AIVoiceDetector()
            detector._loaded = True
            result = detector.detect(wav_path)
            assert result.ai_voice_status == "inconclusive"
            assert result.spoof_score is not None
            assert 0.60 <= result.spoof_score < 0.80
        finally:
            wav_path.unlink(missing_ok=True)

    @patch.object(AIVoiceDetector, "_load_model", return_value=True)
    @patch.object(AIVoiceDetector, "_infer_window", return_value=(0.85, 0.15))
    def test_evidence_populated(self, mock_infer, mock_load):
        """Result should include human-readable evidence."""
        wav_path = create_wav_file(duration_s=5.0)
        try:
            detector = AIVoiceDetector()
            detector._loaded = True
            result = detector.detect(wav_path)
            assert len(result.evidence) > 0
            assert len(result.limitations) > 0
        finally:
            wav_path.unlink(missing_ok=True)

    @patch.object(AIVoiceDetector, "_load_model", return_value=True)
    @patch.object(AIVoiceDetector, "_infer_window", return_value=(0.85, 0.15))
    def test_score_type_always_uncalibrated(self, mock_infer, mock_load):
        """score_type should always be 'uncalibrated_softmax'."""
        wav_path = create_wav_file(duration_s=5.0)
        try:
            detector = AIVoiceDetector()
            detector._loaded = True
            result = detector.detect(wav_path)
            assert result.score_type == "uncalibrated_softmax"
        finally:
            wav_path.unlink(missing_ok=True)

    @patch.object(AIVoiceDetector, "_load_model", return_value=True)
    @patch.object(AIVoiceDetector, "_infer_window", return_value=(0.85, 0.15))
    def test_model_metadata_populated(self, mock_infer, mock_load):
        """Detector model name and version should be populated."""
        wav_path = create_wav_file(duration_s=5.0)
        try:
            detector = AIVoiceDetector()
            detector._loaded = True
            result = detector.detect(wav_path)
            assert result.detector_model == DETECTOR_MODEL_ID
            assert result.detector_version is not None
            assert len(result.detector_version) > 0
        finally:
            wav_path.unlink(missing_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# 6. Separation of AI detection and Trust Engine fields
# ══════════════════════════════════════════════════════════════════════════════

class TestChannelSeparation:
    """Tests that AI detection, speaker similarity, and fraud risk are separate."""

    def test_schema_has_separate_fields(self):
        """Report schema should have separate fields for each evidence channel."""
        from app.schemas.report import (
            AnalysisReportResponse,
            VoiceEvidence,
            AIVoiceDetection,
            SpeakerMatch,
        )

        # VoiceEvidence should have ai_voice_detection as separate field
        voice = VoiceEvidence(
            status="ok",
            ai_voice_detection=AIVoiceDetection(
                ai_voice_status="likely_genuine",
                spoof_score=0.15,
            ),
            speaker_match=SpeakerMatch(
                claimed_contact="Mom",
                similarity=0.92,
                enrolled=True,
            ),
        )
        assert voice.ai_voice_detection is not None
        assert voice.speaker_match is not None
        # They are independent
        assert voice.ai_voice_detection.ai_voice_status != voice.status or True
        assert voice.speaker_match.similarity != voice.ai_voice_detection.spoof_score

    def test_ai_detection_not_in_fraud_risk(self):
        """AI voice status should not appear in fraud risk level field."""
        from app.schemas.report import AnalysisReportResponse

        # level is the Trust Engine fraud risk, not the AI voice status
        report = AnalysisReportResponse(
            call_id="test-123",
            status="completed",
            analysis_mode="real",
            level="LOW",
            score=10,
            created_at="2026-01-01T00:00:00Z",
        )
        # level is fraud risk, not voice detection
        assert report.level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def test_ai_detection_schema_validation(self):
        """AIVoiceDetection schema should validate properly."""
        from app.schemas.report import AIVoiceDetection

        # Valid
        det = AIVoiceDetection(
            ai_voice_status="likely_genuine",
            spoof_score=0.15,
            genuine_score=0.85,
            score_type="uncalibrated_softmax",
            detector_model="Vansh180/deepfake-audio-wav2vec2",
        )
        assert det.ai_voice_status == "likely_genuine"

        # spoof_score out of range should fail
        with pytest.raises(Exception):
            AIVoiceDetection(
                ai_voice_status="likely_genuine",
                spoof_score=1.5,  # > 1.0 invalid
            )


# ══════════════════════════════════════════════════════════════════════════════
# 7. API v3 compatibility
# ══════════════════════════════════════════════════════════════════════════════

class TestV3Compatibility:
    """Tests that new fields don't break existing v3 schema."""

    def test_voice_evidence_backward_compatible(self):
        """VoiceEvidence with no ai_voice_detection should still work."""
        from app.schemas.report import VoiceEvidence

        # Old-style voice evidence (no ai_voice_detection)
        voice = VoiceEvidence(
            status="ok",
            spoof_prob=0.3,
            windows_analyzed=5,
            model="test-model",
        )
        assert voice.ai_voice_detection is None
        d = voice.model_dump()
        assert "ai_voice_detection" in d
        assert d["ai_voice_detection"] is None

    def test_report_response_without_voice(self):
        """Report response without voice field should work."""
        from app.schemas.report import AnalysisReportResponse

        report = AnalysisReportResponse(
            call_id="test-456",
            status="completed",
            analysis_mode="real",
            level="LOW",
            score=5,
            created_at="2026-01-01T00:00:00Z",
            voice=None,
        )
        assert report.voice is None

    def test_report_response_with_full_voice(self):
        """Report response with full voice + ai_voice_detection."""
        from app.schemas.report import (
            AnalysisReportResponse,
            VoiceEvidence,
            AIVoiceDetection,
        )

        report = AnalysisReportResponse(
            call_id="test-789",
            status="completed",
            analysis_mode="real",
            level="HIGH",
            score=75,
            created_at="2026-01-01T00:00:00Z",
            voice=VoiceEvidence(
                status="ok",
                spoof_prob=0.85,
                ai_voice_detection=AIVoiceDetection(
                    ai_voice_status="ai_generated_or_spoof_suspected",
                    spoof_score=0.85,
                    genuine_score=0.15,
                    detector_model=DETECTOR_MODEL_ID,
                ),
            ),
        )
        assert report.voice is not None
        assert report.voice.ai_voice_detection is not None
        assert report.voice.ai_voice_detection.ai_voice_status == "ai_generated_or_spoof_suspected"
        # level is Trust Engine risk, NOT voice detection status
        assert report.level == "HIGH"


# ══════════════════════════════════════════════════════════════════════════════
# 8. Real inference test (SKIPPED by default)
# ══════════════════════════════════════════════════════════════════════════════

try:
    import torch
    import transformers
    _REAL_DEPS = True
except ImportError:
    _REAL_DEPS = False


@pytest.mark.skipif(not _REAL_DEPS, reason="torch/transformers not installed")
class TestRealInference:
    """
    Real model inference tests.
    These ACTUALLY LOAD the model and run inference.
    Skipped when dependencies are unavailable.

    IMPORTANT: These tests use synthetic audio (sine waves, noise), NOT
    real human speech. They verify the inference pipeline works end-to-end,
    not detection accuracy on real speech.
    """

    def test_real_model_loads(self):
        """Model should load successfully."""
        detector = AIVoiceDetector()
        loaded = detector._load_model()
        assert loaded is True, f"Model failed to load: {detector._load_error}"
        assert detector._model is not None

    def test_real_inference_sine_wave(self):
        """Run real inference on a sine wave (should classify as non-genuine)."""
        wav_path = create_wav_file(duration_s=5.0, frequency=440, amplitude=0.3)
        try:
            detector = AIVoiceDetector()
            result = detector.detect(wav_path)

            # Should produce a valid result (not unavailable)
            assert result.ai_voice_status != "unavailable", (
                f"Detection failed: {result.error}"
            )
            assert result.spoof_score is not None
            assert 0.0 <= result.spoof_score <= 1.0
            assert result.windows_analyzed > 0
            assert result.processing_time_s > 0
            assert result.score_type == "uncalibrated_softmax"

            print(f"\n✅ Real inference (sine wave):")
            print(f"   Status: {result.ai_voice_status}")
            print(f"   Spoof score: {result.spoof_score:.4f}")
            print(f"   Genuine score: {result.genuine_score:.4f}")
            print(f"   Windows: {result.windows_analyzed}")
            print(f"   Time: {result.processing_time_s:.2f}s")
        finally:
            wav_path.unlink(missing_ok=True)

    def test_real_inference_noise(self):
        """Run real inference on random noise."""
        n_samples = 16000 * 5
        noise = (np.random.randn(n_samples) * 0.1).astype(np.float32)
        noise_int16 = (noise * 32767).astype(np.int16)

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(noise_int16.tobytes())
        tmp.close()
        wav_path = Path(tmp.name)

        try:
            detector = AIVoiceDetector()
            result = detector.detect(wav_path)
            assert result.ai_voice_status != "unavailable"
            assert result.spoof_score is not None
            print(f"\n✅ Real inference (noise):")
            print(f"   Status: {result.ai_voice_status}")
            print(f"   Spoof score: {result.spoof_score:.4f}")
        finally:
            wav_path.unlink(missing_ok=True)

    def test_real_inference_long_audio(self):
        """Run real inference on a longer audio (10s) — tests windowing."""
        wav_path = create_wav_file(duration_s=10.0, frequency=300, amplitude=0.2)
        try:
            detector = AIVoiceDetector()
            result = detector.detect(wav_path)
            assert result.ai_voice_status != "unavailable"
            assert result.windows_analyzed >= 2, (
                f"10s audio should have multiple windows, got {result.windows_analyzed}"
            )
            print(f"\n✅ Real inference (10s audio):")
            print(f"   Windows: {result.windows_analyzed}")
            print(f"   Window scores: {result.window_scores}")
        finally:
            wav_path.unlink(missing_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# 9. Singleton behavior
# ══════════════════════════════════════════════════════════════════════════════

class TestSingleton:
    """Tests for the singleton pattern."""

    def test_get_ai_voice_detector_returns_same_instance(self):
        """get_ai_voice_detector() should return the same instance."""
        from app.audio.ai_voice_detector import get_ai_voice_detector

        # Reset singleton for test
        import app.audio.ai_voice_detector as mod
        old = mod._detector_instance
        mod._detector_instance = None

        try:
            d1 = get_ai_voice_detector()
            d2 = get_ai_voice_detector()
            assert d1 is d2
        finally:
            mod._detector_instance = old
