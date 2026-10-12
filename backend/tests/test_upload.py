"""
Tests for file upload functionality.
"""
import pytest
import io


def test_upload_valid_audio(client, sample_audio_file):
    """Test uploading a valid audio file."""
    filename, content, content_type = sample_audio_file
    
    response = client.post(
        "/api/v1/calls",
        files={"file": (filename, io.BytesIO(content), content_type)}
    )
    
    assert response.status_code == 202
    data = response.json()
    assert "call_id" in data
    assert data["status"] == "queued"
    assert data["analysis_mode"] == "mock"
    assert "message" in data


def test_upload_unsupported_format(client):
    """Test uploading an unsupported file format."""
    response = client.post(
        "/api/v1/calls",
        files={"file": ("test.txt", io.BytesIO(b"text content"), "text/plain")}
    )
    
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_upload_empty_file(client):
    """Test uploading an empty file."""
    response = client.post(
        "/api/v1/calls",
        files={"file": ("empty.wav", io.BytesIO(b""), "audio/wav")}
    )
    
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_upload_missing_file(client):
    """Test upload without providing a file."""
    response = client.post("/api/v1/calls")
    
    assert response.status_code == 422  # Validation error
