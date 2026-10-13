"""
Tests for analysis and report endpoints.
"""
import pytest
import io
import time


def test_get_status_unknown_call(client):
    """Test getting status for non-existent call."""
    response = client.get("/api/v1/calls/unknown-id/status")
    assert response.status_code == 404


def test_get_report_before_completion(client, sample_audio_file):
    """Test getting report while analysis is in progress.
    
    Note: With mock analysis service, processing completes synchronously,
    so this test verifies the endpoint works whether analysis is complete or not.
    """
    filename, content, content_type = sample_audio_file
    
    # Upload file
    upload_response = client.post(
        "/api/v1/calls",
        files={"file": (filename, io.BytesIO(content), content_type)}
    )
    call_id = upload_response.json()["call_id"]
    
    # Try to get report immediately
    # Mock analysis completes synchronously, so expect 200 with completed report
    # Real ASR would return 425 if still processing
    report_response = client.get(f"/api/v1/calls/{call_id}/report")
    assert report_response.status_code in [200, 425]  # Either complete or too early
    
    if report_response.status_code == 200:
        # Analysis completed (mock behavior)
        data = report_response.json()
        assert "level" in data  # v3 API: risk_level renamed to level
        assert "score" in data  # v3 API: risk_score renamed to score


def test_full_workflow(client, sample_audio_file):
    """Test complete workflow: upload -> status -> report."""
    filename, content, content_type = sample_audio_file
    
    # Step 1: Upload
    upload_response = client.post(
        "/api/v1/calls",
        files={"file": (filename, io.BytesIO(content), content_type)}
    )
    assert upload_response.status_code == 202
    call_id = upload_response.json()["call_id"]
    
    # Step 2: Check status (initially queued or processing)
    status_response = client.get(f"/api/v1/calls/{call_id}/status")
    assert status_response.status_code == 200
    status = status_response.json()["status"]
    assert status in ["queued", "processing", "completed"]
    
    # Step 3: Wait for completion (with timeout)
    max_wait = 10  # seconds
    waited = 0
    while waited < max_wait:
        status_response = client.get(f"/api/v1/calls/{call_id}/status")
        status = status_response.json()["status"]
        if status == "completed":
            break
        time.sleep(0.5)
        waited += 0.5
    
    assert status == "completed", f"Analysis did not complete in {max_wait}s"
    
    # Step 4: Get report
    report_response = client.get(f"/api/v1/calls/{call_id}/report")
    assert report_response.status_code == 200
    
    report = report_response.json()
    assert report["call_id"] == call_id
    assert report["status"] == "completed"
    assert report["analysis_mode"] == "mock"
    assert "level" in report
    assert "score" in report
    assert "reasons" in report
    assert "recommended_actions" in report
    assert len(report["warnings"]) > 0


def test_get_transcript(client, sample_audio_file):
    """Test getting transcript after analysis."""
    filename, content, content_type = sample_audio_file
    
    # Upload and wait for completion
    upload_response = client.post(
        "/api/v1/calls",
        files={"file": (filename, io.BytesIO(content), content_type)}
    )
    call_id = upload_response.json()["call_id"]
    
    # Wait for completion
    max_wait = 10
    waited = 0
    while waited < max_wait:
        status_response = client.get(f"/api/v1/calls/{call_id}/status")
        if status_response.json()["status"] == "completed":
            break
        time.sleep(0.5)
        waited += 0.5
    
    # Get transcript
    transcript_response = client.get(f"/api/v1/calls/{call_id}/transcript")
    assert transcript_response.status_code == 200
    
    transcript = transcript_response.json()
    assert transcript["call_id"] == call_id
    assert transcript["is_mock"] is True
    assert "segments" in transcript


def test_list_calls(client, sample_audio_file):
    """Test listing calls with pagination."""
    # Initially empty
    response = client.get("/api/v1/calls")
    assert response.status_code == 200
    data = response.json()
    initial_count = data["pagination"]["total"]
    
    # Upload a call
    filename, content, content_type = sample_audio_file
    client.post(
        "/api/v1/calls",
        files={"file": (filename, io.BytesIO(content), content_type)}
    )
    
    # List again
    response = client.get("/api/v1/calls")
    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["total"] == initial_count + 1
    assert len(data["calls"]) >= 1
    
    # Check pagination parameters
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["page_size"] == 20


def test_list_calls_pagination(client, sample_audio_file):
    """Test pagination parameters."""
    response = client.get("/api/v1/calls?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["page_size"] == 5
