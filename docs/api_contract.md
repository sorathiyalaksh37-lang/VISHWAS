# VISHWAS API Contract Documentation

This document defines the complete HTTP JSON contracts for the VISHWAS API. All clients (Android app, web dashboard) must depend only on these documented contracts, not on internal Python classes.

## Base URL

- Development: `http://localhost:8000/api/v1`
- Production: TBD

## Common Response Formats

### Success Response

All successful responses return JSON with appropriate HTTP status codes.

### Error Response

```json
{
  "detail": "Human-readable error message",
  "error_code": "ERROR_CODE",
  "timestamp": "2026-10-12T10:30:00Z"
}
```

## Endpoints

### 1. Health Check

**Endpoint:** `GET /api/v1/health`

**Description:** Check if the API service is running.

**Response:** `200 OK`

```json
{
  "status": "ok",
  "service": "vishwas-api",
  "version": "0.1.0"
}
```

**Fields:**
- `status` (string, required): Always "ok" if service is running
- `service` (string, required): Service identifier
- `version` (string, required): API version

---

### 2. Upload Recording

**Endpoint:** `POST /api/v1/calls`

**Description:** Upload a call recording for analysis.

**Request:** `multipart/form-data`

Form fields:
- `file` (file, required): Audio file (WAV, MP3, M4A)

**Response:** `202 Accepted`

```json
{
  "call_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Recording accepted for analysis",
  "analysis_mode": "mock"
}
```

**Fields:**
- `call_id` (string, required): UUID for this call recording
- `status` (string, required): Initial status, always "queued"
- `message` (string, required): Human-readable confirmation
- `analysis_mode` (string, required): "mock" or "real"

**Error Responses:**

`400 Bad Request` - Invalid file
```json
{
  "detail": "Unsupported file format. Allowed: wav, mp3, m4a"
}
```

`413 Payload Too Large` - File too large
```json
{
  "detail": "File size exceeds maximum allowed (50MB)"
}
```

---

### 3. List Calls

**Endpoint:** `GET /api/v1/calls`

**Description:** Retrieve a paginated list of call recordings.

**Query Parameters:**
- `page` (integer, optional, default: 1): Page number (1-indexed)
- `page_size` (integer, optional, default: 20, max: 100): Results per page

**Response:** `200 OK`

```json
{
  "calls": [
    {
      "call_id": "550e8400-e29b-41d4-a716-446655440000",
      "original_filename": "recording_001.mp3",
      "status": "completed",
      "created_at": "2026-10-12T10:30:00Z",
      "updated_at": "2026-10-12T10:30:45Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 45,
    "pages": 3
  }
}
```

**Call Object Fields:**
- `call_id` (string, required): UUID
- `original_filename` (string, required): Original uploaded filename
- `status` (string, required): Current processing status
- `created_at` (string, required): ISO-8601 timestamp
- `updated_at` (string, required): ISO-8601 timestamp

---

### 4. Get Call Status

**Endpoint:** `GET /api/v1/calls/{call_id}/status`

**Description:** Check the processing status of a call.

**Response:** `200 OK`

```json
{
  "call_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "created_at": "2026-10-12T10:30:00Z",
  "updated_at": "2026-10-12T10:30:15Z",
  "completed_at": null,
  "error_message": null
}
```

**Status Values:**
- `queued`: Waiting to be processed
- `processing`: Currently being analyzed
- `completed`: Analysis finished successfully
- `failed`: Analysis encountered an error

**Fields:**
- `call_id` (string, required): UUID
- `status` (string, required): One of the status values above
- `created_at` (string, required): ISO-8601 timestamp
- `updated_at` (string, required): ISO-8601 timestamp
- `completed_at` (string, nullable): ISO-8601 timestamp or null
- `error_message` (string, nullable): Error description if status is "failed"

**Error Response:**

`404 Not Found` - Unknown call_id
```json
{
  "detail": "Call not found"
}
```

---

### 5. Get Transcript

**Endpoint:** `GET /api/v1/calls/{call_id}/transcript`

**Description:** Retrieve the transcription of a call recording.

**Response:** `200 OK`

```json
{
  "call_id": "550e8400-e29b-41d4-a716-446655440000",
  "language": "en",
  "transcription_status": "completed",
  "segments": [
    {
      "start": 0.0,
      "end": 3.5,
      "speaker": null,
      "text": "Hello, this is calling from bank security.",
      "language": "en"
    },
    {
      "start": 3.8,
      "end": 6.2,
      "speaker": null,
      "text": "Please share your OTP immediately.",
      "language": "en"
    }
  ],
  "is_mock": true
}
```

**Fields:**
- `call_id` (string, required): UUID
- `language` (string, nullable): Detected primary language code (ISO 639-1) or null
- `transcription_status` (string, required): "completed", "not_available", or "not_implemented"
- `segments` (array, required): List of transcript segments
- `is_mock` (boolean, required): True if this is mock data

**Transcript Segment:**
- `start` (float, required): Start time in seconds (≥ 0)
- `end` (float, required): End time in seconds (> start)
- `speaker` (string, nullable): Speaker identifier or null
- `text` (string, required): Transcribed text
- `language` (string, nullable): Segment language code or null

**Phase 1 Note:** In Phase 1, actual transcription is not implemented. The endpoint returns mock data with `"transcription_status": "not_implemented"` and `"is_mock": true`.

---

### 6. Get Analysis Report

**Endpoint:** `GET /api/v1/calls/{call_id}/report`

**Description:** Retrieve the complete analysis report for a call.

**Response:** `200 OK`

```json
{
  "call_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "analysis_mode": "mock",
  "language": "en",
  "transcript": {
    "segments": [
      {
        "start": 0.0,
        "end": 3.5,
        "speaker": null,
        "text": "Hello, this is calling from bank security.",
        "language": "en"
      }
    ],
    "is_mock": true
  },
  "agent_findings": [
    {
      "agent": "impersonation_agent",
      "signal": "authority_impersonation",
      "severity": "high",
      "evidence_text": "Hello, this is calling from bank security.",
      "start_time": 0.0,
      "end_time": 3.5,
      "confidence": null,
      "source": "mock"
    },
    {
      "agent": "request_agent",
      "signal": "sensitive_credential_request",
      "severity": "critical",
      "evidence_text": "Please share your OTP immediately.",
      "start_time": 3.8,
      "end_time": 6.2,
      "confidence": null,
      "source": "mock"
    }
  ],
  "risk_level": "high",
  "risk_score": null,
  "reasons": [
    "Authority impersonation detected (bank security claim)",
    "Sensitive credential request (OTP)",
    "Urgency tactics employed"
  ],
  "recommended_actions": [
    "Do not share OTP or sensitive information with this caller",
    "Hang up and contact your bank directly using official channels",
    "Verify the caller's identity through independent means",
    "Report this incident to your bank's fraud department"
  ],
  "warnings": [
    "This is a mock analysis for Phase 1 demonstration",
    "Real fraud detection will be implemented in future phases"
  ],
  "created_at": "2026-10-12T10:30:00Z",
  "completed_at": "2026-10-12T10:30:45Z",
  "is_mock": true
}
```

**Fields:**
- `call_id` (string, required): UUID
- `status` (string, required): Processing status
- `analysis_mode` (string, required): "mock" or "real"
- `language` (string, nullable): Detected language or null
- `transcript` (object, nullable): Transcript object (same as transcript endpoint)
- `agent_findings` (array, required): List of findings from detection agents
- `risk_level` (string, required): "low", "medium", "high", or "critical"
- `risk_score` (float, nullable): Numeric risk score (0-100) or null
- `reasons` (array[string], required): List of human-readable risk factors
- `recommended_actions` (array[string], required): Recommended user actions
- `warnings` (array[string], optional): Important warnings or limitations
- `created_at` (string, required): ISO-8601 timestamp
- `completed_at` (string, nullable): ISO-8601 timestamp or null
- `is_mock` (boolean, required): True if this is mock data

**Agent Finding:**
- `agent` (string, required): Agent identifier
- `signal` (string, required): Signal type detected
- `severity` (string, required): "low", "medium", "high", or "critical"
- `evidence_text` (string, required): Supporting text evidence
- `start_time` (float, nullable): Evidence start time in seconds
- `end_time` (float, nullable): Evidence end time in seconds
- `confidence` (float, nullable): Confidence score (0-1) or null
- `source` (string, required): "mock" or model identifier

**Error Responses:**

`404 Not Found` - Unknown call_id
```json
{
  "detail": "Call not found"
}
```

`425 Too Early` - Analysis not yet complete
```json
{
  "detail": "Analysis in progress. Current status: processing"
}
```

---

## Status Flow

```
queued → processing → completed
                   ↘ failed
```

Once a call reaches `completed` or `failed` status, it does not change.

## Mock Data Indicators

In Phase 1, all analysis data is mock. Reports always include:
- `"is_mock": true` at the top level
- `"analysis_mode": "mock"`
- `"source": "mock"` in agent findings
- Warnings explaining limitations

Clients should display prominent labels when showing mock data.

## Rate Limits

Phase 1 has no enforced rate limits (local development only).

## Authentication

Phase 1 has no authentication (local development only). 

**Warning:** Do not expose Phase 1 to the internet without implementing proper authentication and authorization.

## Pagination

List endpoints support pagination:
- Default page size: 20
- Maximum page size: 100
- Pages are 1-indexed

## Error Codes

Standard HTTP status codes:
- `200 OK`: Success
- `202 Accepted`: Request accepted for async processing
- `400 Bad Request`: Invalid request
- `404 Not Found`: Resource not found
- `413 Payload Too Large`: File too large
- `422 Unprocessable Entity`: Validation error
- `425 Too Early`: Resource not ready yet
- `500 Internal Server Error`: Server error

## Timestamps

All timestamps are in ISO-8601 format with UTC timezone:
```
2026-10-12T10:30:00Z
```

## File Size Limits

- Maximum upload size: 50 MB (configurable)

## Supported Audio Formats

- WAV (.wav)
- MP3 (.mp3)
- M4A (.m4a)

Additional formats may be added in future versions.
