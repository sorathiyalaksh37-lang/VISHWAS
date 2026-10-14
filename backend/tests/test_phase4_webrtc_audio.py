"""
Unit and integration tests for Phase 4: WebRTC Audio Prototype.
Tests rolling-window incremental ASR with deduplication, provisional vs finalized labeling,
streaming AASIST voice anti-spoof adapter with calibrated score semantics, and quality gates.
"""
import asyncio
import json
import math
import struct
import pytest
from app.audio.aasist_streaming import AASISTStreamingAnalyzer, MIN_AUDIO_DURATION_S
from app.audio.incremental_asr import IncrementalASR, PartialTranscript
from app.schemas.live_session import LiveSessionStartRequest
from app.services.live_session_manager import LiveSessionManager


def _generate_pcm_audio(duration_s: float, sample_rate: int = 16000, frequency: int = 440, amplitude: float = 0.5) -> bytes:
    """Generate 16-bit mono PCM sine wave audio."""
    num_samples = int(duration_s * sample_rate)
    buf = []
    for i in range(num_samples):
        val = int(32767 * amplitude * math.sin(2 * math.pi * frequency * i / sample_rate))
        buf.append(struct.pack("<h", val))
    return b"".join(buf)


# ── Incremental ASR Tests ─────────────────────────────────────────────────────

class TestIncrementalASR:
    """Unit tests for rolling-window incremental ASR and deduplication."""

    def test_buffer_accumulation_and_threshold(self):
        """Audio chunks below window threshold produce no transcription."""
        asr = IncrementalASR(sample_rate=16000, window_duration_s=3.0)
        assert not asr.has_sufficient_audio()

        # Add 1.0s of audio (< 3.0s threshold)
        pcm_1s = _generate_pcm_audio(1.0)
        asr.add_audio(pcm_1s)
        assert not asr.has_sufficient_audio()
        assert asr.transcribe_current_window() == []

        # Add 2.5s more (total 3.5s >= 3.0s threshold)
        pcm_2_5s = _generate_pcm_audio(2.5)
        asr.add_audio(pcm_2_5s)
        assert asr.has_sufficient_audio()

    def test_deduplication_removes_sliding_overlap(self):
        """Ensure repeated words across overlapping windows are stripped."""
        finalized = "Hello this is an official message from the"
        current_window = "official message from the state bank of india."

        deduped = IncrementalASR._deduplicate(current_window, finalized)
        assert deduped == "state bank of india."

    def test_deduplication_exact_prefix_match(self):
        """Ensure exact leading prefix substring is removed."""
        finalized = "Transfer fifty thousand dollars"
        current = "Transfer fifty thousand dollars right now."

        deduped = IncrementalASR._deduplicate(current, finalized)
        assert deduped == "right now."

    def test_provisional_vs_finalized_labeling(self):
        """Sentences with boundary punctuation are marked final; others provisional."""
        asr = IncrementalASR(sample_rate=16000, window_duration_s=1.0, step_duration_s=0.5)

        # Emulate custom transcription
        asr._transcribe_window_pcm = lambda pcm: "Your account is on hold"
        asr.add_audio(_generate_pcm_audio(1.5))
        emitted = asr.transcribe_current_window()

        assert len(emitted) == 1
        assert emitted[0].is_final is False
        assert emitted[0].text == "Your account is on hold"

        # Now complete the sentence with punctuation
        asr._transcribe_window_pcm = lambda pcm: "Your account is on hold right now."
        asr.add_audio(_generate_pcm_audio(1.0))
        emitted2 = asr.transcribe_current_window()

        assert len(emitted2) == 1
        assert emitted2[0].is_final is True
        assert emitted2[0].text == "Your account is on hold right now."

    def test_finalize_remaining_on_stream_end(self):
        """finalize_remaining() commits provisional segments when audio stream ends."""
        asr = IncrementalASR(sample_rate=16000, window_duration_s=1.0)
        asr._transcribe_window_pcm = lambda pcm: "Pending transaction alert"
        asr.add_audio(_generate_pcm_audio(1.5))
        asr.transcribe_current_window()

        assert asr.current_provisional is not None
        assert asr.current_provisional.is_final is False

        finalized = asr.finalize_remaining()
        assert len(finalized) == 1
        assert finalized[0].is_final is True
        assert asr.current_provisional is None


# ── AASIST Anti-Spoof Streaming Analyzer Tests ─────────────────────────────────

class TestAASISTStreamingAnalyzer:
    """Unit tests for AASIST anti-spoof streaming adapter and calibration."""

    @pytest.mark.asyncio
    async def test_quality_gate_duration_under_3s_inconclusive(self):
        """Windows shorter than 3.0 seconds must return status='inconclusive'."""
        analyzer = AASISTStreamingAnalyzer()
        short_pcm = _generate_pcm_audio(duration_s=2.0)  # 2.0s < 3.0s minimum

        result = await analyzer.analyze_pcm_window(short_pcm, sample_rate=16000, audio_authorized=True)
        assert result["status"] == "inconclusive"
        assert result["spoof_prob"] is None
        assert "quality gate" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_unauthorized_audio_returns_unavailable(self):
        """When audio authorization is false, returns status='unavailable'."""
        analyzer = AASISTStreamingAnalyzer()
        pcm = _generate_pcm_audio(duration_s=4.0)

        result = await analyzer.analyze_pcm_window(pcm, sample_rate=16000, audio_authorized=False)
        assert result["status"] == "unavailable"
        assert result["spoof_prob"] is None

    def test_logit_calibration_semantics_never_raw_logit(self):
        """
        Verify logit calibration semantics:
        Never interpret raw logits as calibrated probabilities.
        """
        analyzer = AASISTStreamingAnalyzer(temperature=1.5)

        # Equal logits: P(spoof) = 0.50
        p_neutral = analyzer.calibrate_logits(logit_bonafide=2.0, logit_spoof=2.0)
        assert round(p_neutral, 2) == 0.50

        # Strong spoof signal: logit_spoof >> logit_bonafide
        p_high_spoof = analyzer.calibrate_logits(logit_bonafide=-3.0, logit_spoof=4.5)
        assert p_high_spoof > 0.95
        assert 0.0 <= p_high_spoof <= 1.0

        # Strong bonafide signal: logit_bonafide >> logit_spoof
        p_bonafide = analyzer.calibrate_logits(logit_bonafide=5.0, logit_spoof=-2.0)
        assert p_bonafide < 0.05
        assert 0.0 <= p_bonafide <= 1.0

        # Verify raw logit is not used directly (raw logit 4.5 is outside [0, 1])
        assert p_high_spoof <= 1.0

    @pytest.mark.asyncio
    async def test_sufficient_audio_produces_calibrated_result(self):
        """Sufficient active audio (>= 3.0s) produces ok status and calibrated probability."""
        analyzer = AASISTStreamingAnalyzer()
        pcm = _generate_pcm_audio(duration_s=3.5, amplitude=0.4)

        result = await analyzer.analyze_pcm_window(pcm, sample_rate=16000, audio_authorized=True)
        assert result["status"] == "ok"
        assert result["spoof_prob"] is not None
        assert 0.0 <= result["spoof_prob"] <= 1.0
        assert result["windows_analyzed"] >= 1
        assert result["duration_s"] >= 3.0


# ── Live Session Audio Streaming Integration Tests ────────────────────────────

class TestLiveAudioStreamingIntegration:
    """End-to-end integration tests for streaming audio chunks through LiveSessionManager."""

    @pytest.mark.asyncio
    async def test_audio_streaming_pipeline_produces_events(self):
        """Streaming audio chunks triggers background loop, ASR, and voice updates."""
        mgr = LiveSessionManager()
        req = LiveSessionStartRequest(mode="webrtc", audio_authorized=True)
        session = await mgr.create_session(user_id="user-webrtc-test", request=req)

        # Start audio background loop
        session.processing_task = asyncio.create_task(mgr._audio_processing_loop(session))

        # Stream 3.5 seconds of audio in 500ms chunks (7 chunks)
        sample_rate = 16000
        chunk_sec = 0.5
        chunk_pcm = _generate_pcm_audio(chunk_sec, sample_rate=sample_rate)

        for i in range(1, 8):
            ok = await mgr.submit_audio_chunk(
                session_id=session.session_id,
                user_id="user-webrtc-test",
                sequence_number=i,
                timestamp_ms=int(i * chunk_sec * 1000),
                sample_rate=sample_rate,
                channel_count=1,
                audio_data=chunk_pcm,
            )
            assert ok is True

        # Allow background processor to consume chunks
        for _ in range(25):
            if session.windows_analyzed >= 1:
                break
            await asyncio.sleep(0.1)

        # Verify chunks processed and voice analyzed before cancelling
        assert session.total_chunks_processed >= 6
        assert session.windows_analyzed >= 1
        assert session.voice_status == "analyzed"
        assert session.voice_spoof_prob is not None

        # End session
        await mgr.cancel_session(session.session_id, user_id="user-webrtc-test")
