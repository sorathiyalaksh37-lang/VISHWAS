"""
Tests for streaming voice detection (FEAT-001).

Comprehensive test coverage:
  - Session lifecycle (create, use, delete)
  - Incremental chunk processing
  - Temporal smoothing verification (EMA)
  - Quality gates (insufficient data)
  - Concurrent sessions (multi-user)
  - Session timeout cleanup
  - Invalid session_id (404)
  - Model unavailable (503)
  - Malformed audio chunk (400)
  - Thread safety (concurrent chunk uploads)
"""
import pytest
import time
import numpy as np
from unittest.mock import patch, MagicMock
from fastapi import status

from app.services.streaming_session_manager import get_streaming_session_manager
from app.audio.streaming_voice_detector import StreamingVoiceDetector
from app.models.user import User


# ── Test fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def auth_headers(test_db):
    """Create test user and return auth headers."""
    from app.auth.security import create_access_token
    
    user = User(
        email="test@example.com",
        hashed_password="fake_hash",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    
    token = create_access_token(data={"sub": user.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_user_headers(test_db):
    """Create second test user for concurrent session tests."""
    from app.auth.security import create_access_token
    
    user = User(
        email="user2@example.com",
        hashed_password="fake_hash",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    
    token = create_access_token(data={"sub": user.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_audio_chunk():
    """Generate a sample audio chunk (1.5s at 16kHz mono PCM int16)."""
    sample_rate = 16000
    duration_s = 1.5
    num_samples = int(sample_rate * duration_s)
    
    # Generate sine wave
    frequency = 440  # A4 note
    t = np.linspace(0, duration_s, num_samples)
    samples = np.sin(2 * np.pi * frequency * t) * 0.5  # [-0.5, 0.5]
    samples_int16 = (samples * 32767).astype(np.int16)
    
    return samples_int16.tobytes()


# ── Test 1: Session lifecycle (create, use, delete) ───────────────────────────

def test_session_lifecycle(client, auth_headers):
    """Test basic session lifecycle: start -> process -> delete."""
    # Start session
    response = client.post(
        "/api/v1/voice-detection/stream/start",
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "session_id" in data
    assert data["status"] == "ready"
    assert data["format"] == "wav_16khz_mono"
    
    session_id = data["session_id"]
    
    # Delete session
    response = client.delete(
        f"/api/v1/voice-detection/stream/{session_id}",
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "deleted"
    
    # Verify session is deleted (attempt to delete again)
    response = client.delete(
        f"/api/v1/voice-detection/stream/{session_id}",
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ── Test 2: Incremental chunk processing (3 chunks of 3s each) ───────────────

@patch('app.audio.voice_layer.VoiceLayer._spoof_prob_for_window')
def test_incremental_chunk_processing(mock_spoof, client, auth_headers, sample_audio_chunk):
    """Test processing multiple chunks incrementally."""
    # Mock model to return fixed probabilities
    mock_spoof.return_value = 0.7
    
    # Start session
    response = client.post(
        "/api/v1/voice-detection/stream/start",
        headers=auth_headers
    )
    session_id = response.json()["session_id"]
    
    # Process first chunk (1.5s) - should be insufficient
    response = client.post(
        f"/api/v1/voice-detection/stream/{session_id}/chunk",
        headers=auth_headers,
        files={"chunk": ("audio.raw", sample_audio_chunk, "application/octet-stream")}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["label"] == "insufficient_data"
    assert data["confidence"] == "insufficient_data"
    assert data["chunks_processed"] == 1
    
    # Process second chunk (3s total) - should have low/medium confidence
    response = client.post(
        f"/api/v1/voice-detection/stream/{session_id}/chunk",
        headers=auth_headers,
        files={"chunk": ("audio.raw", sample_audio_chunk, "application/octet-stream")}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["chunks_processed"] == 2
    assert data["confidence"] in ("low", "medium")
    assert data["duration_analyzed_ms"] >= 3000
    
    # Process third chunk (4.5s total) - should have high confidence
    response = client.post(
        f"/api/v1/voice-detection/stream/{session_id}/chunk",
        headers=auth_headers,
        files={"chunk": ("audio.raw", sample_audio_chunk, "application/octet-stream")}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["chunks_processed"] == 3
    assert data["confidence"] == "high"
    assert data["label"] == "ai_generated"  # prob=0.7 > 0.5 threshold
    assert data["spoof_prob"] is not None
    
    # Cleanup
    client.delete(f"/api/v1/voice-detection/stream/{session_id}", headers=auth_headers)


# ── Test 3: Temporal smoothing verification (EMA) ─────────────────────────────

@patch('app.audio.voice_layer.VoiceLayer._spoof_prob_for_window')
def test_temporal_smoothing_ema(mock_spoof, client, auth_headers, sample_audio_chunk):
    """Verify exponential moving average temporal smoothing."""
    # Mock model to return specific sequence: 0.8, 0.6, 0.7
    mock_spoof.side_effect = [0.8, 0.6, 0.7]
    
    # Start session
    response = client.post(
        "/api/v1/voice-detection/stream/start",
        headers=auth_headers
    )
    session_id = response.json()["session_id"]
    
    # Process chunks and verify EMA calculation
    # EMA formula: smoothed = alpha * new + (1 - alpha) * old
    # alpha = 0.3
    
    # Chunk 1: smoothed = 0.8 (first value)
    response = client.post(
        f"/api/v1/voice-detection/stream/{session_id}/chunk",
        headers=auth_headers,
        files={"chunk": ("audio.raw", sample_audio_chunk, "application/octet-stream")}
    )
    prob1 = response.json()["spoof_prob"]
    assert prob1 == 0.8
    
    # Chunk 2: smoothed = 0.3 * 0.6 + 0.7 * 0.8 = 0.18 + 0.56 = 0.74
    response = client.post(
        f"/api/v1/voice-detection/stream/{session_id}/chunk",
        headers=auth_headers,
        files={"chunk": ("audio.raw", sample_audio_chunk, "application/octet-stream")}
    )
    prob2 = response.json()["spoof_prob"]
    expected2 = 0.3 * 0.6 + 0.7 * 0.8
    assert abs(prob2 - expected2) < 0.01
    
    # Chunk 3: smoothed = 0.3 * 0.7 + 0.7 * 0.74 = 0.21 + 0.518 = 0.728
    response = client.post(
        f"/api/v1/voice-detection/stream/{session_id}/chunk",
        headers=auth_headers,
        files={"chunk": ("audio.raw", sample_audio_chunk, "application/octet-stream")}
    )
    prob3 = response.json()["spoof_prob"]
    expected3 = 0.3 * 0.7 + 0.7 * expected2
    assert abs(prob3 - expected3) < 0.01
    
    # Cleanup
    client.delete(f"/api/v1/voice-detection/stream/{session_id}", headers=auth_headers)


# ── Test 4: Quality gate (send 1s chunk, verify 'insufficient_data') ──────────

@patch('app.audio.voice_layer.VoiceLayer._spoof_prob_for_window')
def test_quality_gate_insufficient_data(mock_spoof, client, auth_headers):
    """Test quality gate: short chunks return insufficient_data."""
    mock_spoof.return_value = 0.8
    
    # Start session
    response = client.post(
        "/api/v1/voice-detection/stream/start",
        headers=auth_headers
    )
    session_id = response.json()["session_id"]
    
    # Create short chunk (1s at 16kHz mono)
    sample_rate = 16000
    duration_s = 1.0
    num_samples = int(sample_rate * duration_s)
    samples_int16 = np.zeros(num_samples, dtype=np.int16)
    short_chunk = samples_int16.tobytes()
    
    # Process short chunk
    response = client.post(
        f"/api/v1/voice-detection/stream/{session_id}/chunk",
        headers=auth_headers,
        files={"chunk": ("audio.raw", short_chunk, "application/octet-stream")}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["label"] == "insufficient_data"
    assert data["confidence"] == "insufficient_data"
    assert data["duration_analyzed_ms"] < 3000
    
    # Cleanup
    client.delete(f"/api/v1/voice-detection/stream/{session_id}", headers=auth_headers)


# ── Test 5: Concurrent sessions (2 users, 2 session_ids) ──────────────────────

@patch('app.audio.voice_layer.VoiceLayer._spoof_prob_for_window')
def test_concurrent_sessions(mock_spoof, client, auth_headers, second_user_headers, sample_audio_chunk):
    """Test concurrent sessions from different users."""
    mock_spoof.return_value = 0.5
    
    # User 1 starts session
    response1 = client.post(
        "/api/v1/voice-detection/stream/start",
        headers=auth_headers
    )
    session_id1 = response1.json()["session_id"]
    
    # User 2 starts session
    response2 = client.post(
        "/api/v1/voice-detection/stream/start",
        headers=second_user_headers
    )
    session_id2 = response2.json()["session_id"]
    
    # Verify different session IDs
    assert session_id1 != session_id2
    
    # User 1 processes chunk
    response = client.post(
        f"/api/v1/voice-detection/stream/{session_id1}/chunk",
        headers=auth_headers,
        files={"chunk": ("audio.raw", sample_audio_chunk, "application/octet-stream")}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # User 2 processes chunk
    response = client.post(
        f"/api/v1/voice-detection/stream/{session_id2}/chunk",
        headers=second_user_headers,
        files={"chunk": ("audio.raw", sample_audio_chunk, "application/octet-stream")}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # User 1 cannot access User 2's session
    response = client.post(
        f"/api/v1/voice-detection/stream/{session_id2}/chunk",
        headers=auth_headers,
        files={"chunk": ("audio.raw", sample_audio_chunk, "application/octet-stream")}
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    
    # Cleanup
    client.delete(f"/api/v1/voice-detection/stream/{session_id1}", headers=auth_headers)
    client.delete(f"/api/v1/voice-detection/stream/{session_id2}", headers=second_user_headers)


# ── Test 6: Session timeout cleanup ───────────────────────────────────────────

def test_session_timeout_cleanup(test_db):
    """Test automatic cleanup of expired sessions."""
    from app.services.streaming_session_manager import StreamingSessionManager
    from datetime import datetime, timezone, timedelta
    
    manager = StreamingSessionManager()
    
    # Create session
    session_id = manager.create_session(user_id="test_user")
    assert manager.get_session_count() == 1
    
    # Manually expire session by backdating last_accessed
    session = manager.get_session(session_id)
    session['last_accessed'] = datetime.now(timezone.utc) - timedelta(minutes=31)
    
    # Run cleanup
    deleted = manager.cleanup_expired(max_age_minutes=30)
    assert deleted == 1
    assert manager.get_session_count() == 0


# ── Test 7: Invalid session_id (404) ──────────────────────────────────────────

def test_invalid_session_id(client, auth_headers, sample_audio_chunk):
    """Test error handling for invalid session_id."""
    fake_session_id = "nonexistent_session"
    
    # Attempt to process chunk with invalid session
    response = client.post(
        f"/api/v1/voice-detection/stream/{fake_session_id}/chunk",
        headers=auth_headers,
        files={"chunk": ("audio.raw", sample_audio_chunk, "application/octet-stream")}
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()
    
    # Attempt to delete invalid session
    response = client.delete(
        f"/api/v1/voice-detection/stream/{fake_session_id}",
        headers=auth_headers
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ── Test 8: Model unavailable (503) ───────────────────────────────────────────

@patch('app.audio.voice_layer.VoiceLayer._load_spoof_model')
def test_model_unavailable(mock_load, client, auth_headers, sample_audio_chunk):
    """Test error handling when model is unavailable."""
    # Mock model loading to fail
    mock_load.return_value = False
    
    # Start session
    response = client.post(
        "/api/v1/voice-detection/stream/start",
        headers=auth_headers
    )
    session_id = response.json()["session_id"]
    
    # Process chunk - should return 503
    response = client.post(
        f"/api/v1/voice-detection/stream/{session_id}/chunk",
        headers=auth_headers,
        files={"chunk": ("audio.raw", sample_audio_chunk, "application/octet-stream")}
    )
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "unavailable" in response.json()["detail"].lower()
    
    # Cleanup
    client.delete(f"/api/v1/voice-detection/stream/{session_id}", headers=auth_headers)


# ── Test 9: Malformed audio chunk (400) ───────────────────────────────────────

@patch('app.audio.voice_layer.VoiceLayer._spoof_prob_for_window')
def test_malformed_audio_chunk(mock_spoof, client, auth_headers):
    """Test error handling for malformed audio chunks."""
    mock_spoof.return_value = 0.5
    
    # Start session
    response = client.post(
        "/api/v1/voice-detection/stream/start",
        headers=auth_headers
    )
    session_id = response.json()["session_id"]
    
    # Send malformed chunk (too short to parse)
    malformed_chunk = b"invalid"
    
    response = client.post(
        f"/api/v1/voice-detection/stream/{session_id}/chunk",
        headers=auth_headers,
        files={"chunk": ("audio.raw", malformed_chunk, "application/octet-stream")}
    )
    # Should return 400 or process but get insufficient data
    # Due to short length, it will be rejected by min_samples check
    assert response.status_code in (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST)
    
    # Cleanup
    client.delete(f"/api/v1/voice-detection/stream/{session_id}", headers=auth_headers)


# ── Test 10: Thread safety (simulate concurrent chunk uploads) ────────────────

@patch('app.audio.voice_layer.VoiceLayer._spoof_prob_for_window')
def test_thread_safety_concurrent_uploads(mock_spoof, client, auth_headers, sample_audio_chunk):
    """Test thread safety with concurrent chunk uploads to same session."""
    import concurrent.futures
    
    mock_spoof.return_value = 0.6
    
    # Start session
    response = client.post(
        "/api/v1/voice-detection/stream/start",
        headers=auth_headers
    )
    session_id = response.json()["session_id"]
    
    # Function to upload chunk
    def upload_chunk(chunk_num):
        response = client.post(
            f"/api/v1/voice-detection/stream/{session_id}/chunk",
            headers=auth_headers,
            files={"chunk": ("audio.raw", sample_audio_chunk, "application/octet-stream")}
        )
        return response.status_code == status.HTTP_200_OK
    
    # Upload 5 chunks concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(upload_chunk, i) for i in range(5)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    # All uploads should succeed
    assert all(results), "Some concurrent uploads failed"
    
    # Verify final state
    manager = get_streaming_session_manager()
    session = manager.get_session(session_id)
    assert session is not None
    assert session['total_chunks'] == 5
    
    # Cleanup
    client.delete(f"/api/v1/voice-detection/stream/{session_id}", headers=auth_headers)


# ── Test 11: Authentication required ──────────────────────────────────────────

def test_authentication_required(client, sample_audio_chunk):
    """Test that all endpoints require authentication."""
    # Start session without auth
    response = client.post("/api/v1/voice-detection/stream/start")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # Process chunk without auth
    response = client.post(
        "/api/v1/voice-detection/stream/fake_session/chunk",
        files={"chunk": ("audio.raw", sample_audio_chunk, "application/octet-stream")}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # Delete session without auth
    response = client.delete("/api/v1/voice-detection/stream/fake_session")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
