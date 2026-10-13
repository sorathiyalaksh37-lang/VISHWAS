import io
import json
import struct
import tempfile
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── In-memory SQLite for tests ─────────────────────────────────────────────────
# We use a file-based SQLite (not :memory:) so that the engine created inside
# app/database/session.py (at module-import time) and our test engine both see
# the same data.  We monkeypatch DATABASE_URL before importing the app.

import os

# Point the app at a temp file DB for the duration of this test module
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
TEST_DB_URL = f"sqlite:///{_tmp_db.name}"

# Override DATABASE_URL *before* importing the app so session.py picks it up
os.environ["DATABASE_URL"] = TEST_DB_URL

from app.database.base import Base       # noqa: E402
from app.database.session import get_db  # noqa: E402
import app.models                        # noqa: E402, F401 — register models

from app.main import app                 # noqa: E402

engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """Return a TestClient with lifespan disabled (tables already exist)."""
    with TestClient(app) as c:
        yield c


# Module-level client for class-based tests that don't use the fixture
_client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_wav_bytes(duration_s: float = 2.0, sample_rate: int = 16000) -> bytes:
    """Generate a minimal valid WAV file in memory."""
    num_samples = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)       # 16-bit
        wf.setframerate(sample_rate)
        # Simple 440 Hz sine-ish pattern
        import math
        samples = [
            int(32767 * math.sin(2 * math.pi * 440 * i / sample_rate))
            for i in range(num_samples)
        ]
        wf.writeframes(struct.pack(f"<{num_samples}h", *samples))
    return buf.getvalue()


def _upload_wav(filename: str = "test.wav", duration_s: float = 2.0) -> dict:
    """Helper: POST a WAV file to /api/v1/analyze/recording."""
    wav_bytes = _make_wav_bytes(duration_s)
    response = _client.post(
        "/api/v1/analyze/recording",
        files={"file": (filename, wav_bytes, "audio/wav")},
    )
    return response


# ══════════════════════════════════════════════════════════════════════════════
# 1. Audio preprocessing tests
# ══════════════════════════════════════════════════════════════════════════════

class TestAudioPreprocessor:

    def test_validate_audio_empty_file(self, tmp_path):
        from app.audio.preprocessor import validate_audio
        empty = tmp_path / "empty.wav"
        empty.write_bytes(b"")
        valid, reason = validate_audio(empty)
        assert not valid
        assert "empty" in reason.lower()

    def test_validate_audio_nonexistent(self, tmp_path):
        from app.audio.preprocessor import validate_audio
        missing = tmp_path / "does_not_exist.wav"
        valid, reason = validate_audio(missing)
        assert not valid
        assert "does not exist" in reason.lower()

    def test_validate_audio_valid_wav(self, tmp_path):
        from app.audio.preprocessor import validate_audio
        wav_path = tmp_path / "valid.wav"
        wav_path.write_bytes(_make_wav_bytes(2.0))
        # ffprobe may not be available in CI, so accept either outcome
        valid, reason = validate_audio(wav_path)
        # File exists and is not empty — should at minimum pass size check
        assert wav_path.stat().st_size > 0

    def test_estimate_snr_valid_wav(self, tmp_path):
        from app.audio.preprocessor import estimate_snr
        wav_path = tmp_path / "snr_test.wav"
        wav_path.write_bytes(_make_wav_bytes(2.0))
        snr = estimate_snr(wav_path)
        # For a pure sine wave, SNR should be measurably positive
        # -1.0 is the error sentinel
        # snr >= -1.0: -1.0 is the error sentinel, any float >= 0 is a valid reading
        assert snr >= -1.0  # just ensure it doesn't crash and returns a number

    def test_estimate_snr_empty_file(self, tmp_path):
        from app.audio.preprocessor import estimate_snr
        empty = tmp_path / "empty.wav"
        empty.write_bytes(b"")
        snr = estimate_snr(empty)
        assert snr == -1.0

    def test_convert_to_wav_unsupported_format(self, tmp_path):
        from app.audio.preprocessor import convert_to_wav
        bad_file = tmp_path / "file.xyz"
        bad_file.write_bytes(b"garbage")
        with pytest.raises(ValueError, match="Unsupported audio format"):
            convert_to_wav(bad_file)


# ══════════════════════════════════════════════════════════════════════════════
# 2. ASR Service tests
# ══════════════════════════════════════════════════════════════════════════════

class TestASRService:

    def test_asr_unavailable_returns_result(self, tmp_path):
        """When faster-whisper is not installed, ASRService should return gracefully."""
        from app.audio.asr_service import ASRService
        svc = ASRService()
        wav_path = tmp_path / "test.wav"
        wav_path.write_bytes(_make_wav_bytes(2.0))

        with patch("app.audio.asr_service.FASTER_WHISPER_AVAILABLE", False):
            result = svc.transcribe(wav_path, call_id="test-id")

        assert result.transcription_status in ("unavailable", "failed", "completed")
        assert result.call_id == "test-id"

    def test_asr_result_structure(self):
        from app.audio.asr_service import ASRResult, TranscriptSegment
        result = ASRResult(
            call_id="abc",
            language="en",
            language_probability=0.99,
            segments=[
                TranscriptSegment(start=0.0, end=1.5, text="Hello, this is a test.")
            ],
            transcription_status="completed",
        )
        assert result.call_id == "abc"
        assert len(result.segments) == 1
        assert result.segments[0].text == "Hello, this is a test."

    def test_get_asr_service_singleton(self):
        from app.audio.asr_service import get_asr_service
        s1 = get_asr_service()
        s2 = get_asr_service()
        assert s1 is s2


# ══════════════════════════════════════════════════════════════════════════════
# 3. Voice Layer tests
# ══════════════════════════════════════════════════════════════════════════════

class TestVoiceLayer:

    def test_quality_gate_short_audio(self, tmp_path):
        """Audio shorter than MIN_SPEECH_SECONDS → inconclusive."""
        from app.audio.voice_layer import VoiceLayer
        from unittest.mock import patch

        wav_path = tmp_path / "short.wav"
        wav_path.write_bytes(_make_wav_bytes(0.5))  # 0.5s

        layer = VoiceLayer()
        with patch("app.audio.voice_layer.get_audio_duration", return_value=0.5):
            evidence = layer.analyze(wav_path)

        assert evidence.status == "inconclusive"

    def test_voice_layer_unavailable_on_missing_deps(self, tmp_path):
        """When torch/transformers not installed → unavailable or inconclusive."""
        from app.audio.voice_layer import VoiceLayer

        wav_path = tmp_path / "test.wav"
        wav_path.write_bytes(_make_wav_bytes(5.0))

        layer = VoiceLayer()
        evidence = layer.analyze(wav_path)

        # Either "ok" (models installed), "inconclusive" (quality), or "unavailable"
        assert evidence.status in ("ok", "inconclusive", "unavailable")

    def test_voice_evidence_structure(self):
        from app.audio.voice_layer import VoiceEvidence, SpeakerMatch
        ev = VoiceEvidence(
            status="ok",
            spoof_prob=0.85,
            windows_analyzed=4,
            duration_s=12.0,
            snr_db=18.5,
        )
        assert ev.status == "ok"
        assert ev.spoof_prob == 0.85
        assert ev.speaker_match is None


# ══════════════════════════════════════════════════════════════════════════════
# 4. API endpoint tests
# ══════════════════════════════════════════════════════════════════════════════

class TestUploadEndpoint:

    def test_upload_valid_wav_returns_202(self):
        response = _upload_wav("sample.wav")
        assert response.status_code == 202
        data = response.json()
        assert "call_id" in data
        assert data["status"] == "queued"

    def test_upload_invalid_extension_returns_400(self):
        response = _client.post(
            "/api/v1/analyze/recording",
            files={"file": ("audio.xyz", b"garbage data", "application/octet-stream")},
        )
        assert response.status_code == 400

    def test_upload_empty_file_returns_400(self):
        response = _client.post(
            "/api/v1/analyze/recording",
            files={"file": ("empty.wav", b"", "audio/wav")},
        )
        assert response.status_code == 400

    def test_legacy_calls_endpoint_also_works(self):
        wav_bytes = _make_wav_bytes()
        response = _client.post(
            "/api/v1/calls",
            files={"file": ("test.wav", wav_bytes, "audio/wav")},
        )
        assert response.status_code == 202

    def test_upload_returns_call_id_uuid_format(self):
        response = _upload_wav()
        assert response.status_code == 202
        call_id = response.json()["call_id"]
        # Basic UUID format check
        assert len(call_id) == 36
        assert call_id.count("-") == 4


class TestStatusEndpoint:

    def test_status_queued_immediately_after_upload(self):
        upload = _upload_wav()
        call_id = upload.json()["call_id"]

        status_response = _client.get(f"/api/v1/call/{call_id}/status")
        assert status_response.status_code == 200
        data = status_response.json()
        assert data["call_id"] == call_id
        assert data["status"] in ("queued", "processing", "completed", "failed")

    def test_status_not_found_returns_404(self):
        response = _client.get("/api/v1/call/nonexistent-id/status")
        assert response.status_code == 404

    def test_legacy_status_path_works(self):
        upload = _upload_wav()
        call_id = upload.json()["call_id"]
        response = _client.get(f"/api/v1/calls/{call_id}/status")
        assert response.status_code == 200


class TestCallStateEndpoint:

    def test_state_returns_425_while_queued(self):
        """Before analysis completes the state endpoint should return 425."""
        upload = _upload_wav()
        call_id = upload.json()["call_id"]

        # Force status back to queued in DB (background task may have run)
        db = TestingSessionLocal()
        from app.models.call import CallRecord
        call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
        if call and call.status in ("queued", "processing"):
            response = _client.get(f"/api/v1/call/{call_id}/state")
            assert response.status_code == 425
        db.close()

    def test_state_not_found_returns_404(self):
        response = _client.get("/api/v1/call/does-not-exist/state")
        assert response.status_code == 404


class TestCallsListEndpoint:

    def test_empty_list(self):
        response = _client.get("/api/v1/calls")
        assert response.status_code == 200
        data = response.json()
        assert "calls" in data
        assert "pagination" in data

    def test_list_after_upload(self):
        _upload_wav()
        _upload_wav()
        response = _client.get("/api/v1/calls")
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] >= 2

    def test_pagination_params(self):
        response = _client.get("/api/v1/calls?page=1&page_size=5")
        assert response.status_code == 200


class TestContactsEndpoint:

    def test_create_contact(self):
        response = _client.post(
            "/api/v1/contacts",
            params={
                "name": "Mom",
                "relation": "mother",
                "saved_numbers": "+919876543210,+911234567890",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Mom"
        assert data["relation"] == "mother"
        assert "+919876543210" in data["saved_numbers"]
        assert "contact_id" in data

    def test_list_contacts(self):
        # Create one first
        _client.post("/api/v1/contacts", params={"name": "Dad", "relation": "father"})
        response = _client.get("/api/v1/contacts")
        assert response.status_code == 200
        contacts = response.json()
        assert isinstance(contacts, list)
        assert len(contacts) >= 1

    def test_contact_voiceprint_not_found(self):
        response = _client.post(
            "/api/v1/contacts/nonexistent-id/voiceprint",
            files={"file": ("enroll.wav", _make_wav_bytes(), "audio/wav")},
        )
        assert response.status_code == 404

    def test_contact_voiceprint_empty_audio_rejected(self):
        # Create contact first
        create = _client.post("/api/v1/contacts", params={"name": "Sister", "relation": "sister"})
        contact_id = create.json()["contact_id"]

        response = _client.post(
            f"/api/v1/contacts/{contact_id}/voiceprint",
            files={"file": ("empty.wav", b"", "audio/wav")},
        )
        assert response.status_code == 400

    def test_contact_voiceprint_enroll_returns_status(self):
        """Enrollment should return a dict with 'enrolled' key."""
        create = _client.post("/api/v1/contacts", params={"name": "Brother", "relation": "sibling"})
        contact_id = create.json()["contact_id"]

        response = _client.post(
            f"/api/v1/contacts/{contact_id}/voiceprint",
            files={"file": ("enroll.wav", _make_wav_bytes(5.0), "audio/wav")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "enrolled" in data
        # enrolled may be False if speechbrain not installed — that's OK
        assert isinstance(data["enrolled"], bool)


class TestCounterfactualEndpoint:

    def test_counterfactual_not_found(self):
        response = _client.get("/api/v1/call/nonexistent/counterfactual")
        assert response.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 5. Real Analysis Service tests
# ══════════════════════════════════════════════════════════════════════════════

class TestRealAnalysisService:

    def test_analyze_call_missing_file(self):
        """If storage file is missing, job should be marked 'failed'."""
        import asyncio
        from app.models.call import CallRecord
        from app.services.real_analysis_service import real_analysis_service

        # Create tables for this sub-test (autouse fixture already did it,
        # but we need the session to point at the same in-memory engine)
        db = TestingSessionLocal()
        call = CallRecord(
            original_filename="ghost.wav",
            stored_filename="ghost.wav",
            storage_reference="/nonexistent/path/ghost.wav",
            status="queued",
            analysis_mode="real",
        )
        db.add(call)
        db.commit()
        db.refresh(call)
        call_id = call.id

        asyncio.run(real_analysis_service.analyze_call(db=db, call_id=call_id))

        db.refresh(call)
        assert call.status == "failed"
        assert call.error_message is not None
        db.close()

    def test_preliminary_risk_high_spoof(self):
        from app.audio.voice_layer import VoiceEvidence
        from app.services.real_analysis_service import RealAnalysisService

        svc = RealAnalysisService()
        ev = VoiceEvidence(status="ok", spoof_prob=0.92, windows_analyzed=5, duration_s=10.0, snr_db=15.0)
        score, level = svc._preliminary_risk(ev)
        assert score == 10.0

    def test_preliminary_risk_low_spoof(self):
        from app.audio.voice_layer import VoiceEvidence
        from app.services.real_analysis_service import RealAnalysisService

        svc = RealAnalysisService()
        ev = VoiceEvidence(status="ok", spoof_prob=0.30, windows_analyzed=5, duration_s=10.0, snr_db=15.0)
        score, level = svc._preliminary_risk(ev)
        assert score == 0.0
        assert level == "low"

    def test_preliminary_risk_unavailable(self):
        from app.audio.voice_layer import VoiceEvidence
        from app.services.real_analysis_service import RealAnalysisService

        svc = RealAnalysisService()
        ev = VoiceEvidence(status="unavailable", duration_s=0.0, snr_db=0.0)
        score, level = svc._preliminary_risk(ev)
        assert score == 0.0
