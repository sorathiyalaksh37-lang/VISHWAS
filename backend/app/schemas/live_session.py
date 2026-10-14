"""
Pydantic schemas and protocol models for real-time live analysis sessions.
Supports non-audio detection, WebRTC internet calls, and cellular adapter sessions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

from app.schemas.parameters import CallParameters, EvidenceStatus
from app.schemas.report import TranscriptSegment, CategoryScores


SessionMode = Literal["non_audio", "webrtc", "cellular"]
SessionState = Literal["initializing", "active", "finalizing", "completed", "cancelled", "error"]


# ── REST Request & Response Models ──────────────────────────────────────────

class LiveSessionStartRequest(BaseModel):
    """Request to create a live analysis session."""
    mode: SessionMode = Field("non_audio", description="Session mode: non_audio, webrtc, cellular")
    caller_number: Optional[str] = Field(None, description="Caller's phone number or identifier if known")
    claimed_identity: Optional[str] = Field(None, description="Optional claimed name or organisation")
    claimed_relationship: Optional[str] = Field(None, description="e.g. relative, bank, police")
    audio_authorized: bool = Field(False, description="Whether caller/receiver consent for audio capture is granted")
    audio_source_type: Optional[str] = Field(None, description="microphone, webrtc_stream, cellular_adapter")


class LiveSessionStartResponse(BaseModel):
    """Response after creating a live session."""
    session_id: str
    mode: SessionMode
    state: SessionState
    audio_authorized: bool
    voice_analysis_status: Literal["available", "not_authorized", "unavailable", "pending"]
    created_at: datetime
    ws_endpoint: str = "/api/v1/live/ws/analyze"


class SubmitNonAudioMessageRequest(BaseModel):
    """Request to submit a suspicious message or statement heard during call."""
    text: str = Field(..., min_length=1, max_length=10000, description="Message text or statement excerpt")
    speaker: Optional[str] = Field("caller", description="caller | recipient | other")
    timestamp_s: Optional[float] = Field(None, ge=0.0, description="Offset in seconds from session start")


class LiveSessionStateResponse(BaseModel):
    """Current live state of an active or completed session."""
    session_id: str
    mode: SessionMode
    state: SessionState
    audio_authorized: bool
    caller_number: Optional[str] = None
    transcript: List[TranscriptSegment] = Field(default_factory=list)
    current_score: int = Field(0, ge=0, le=100)
    current_level: str = "LOW"
    category_scores: Optional[CategoryScores] = None
    fired_rules: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    voice_status: Literal["available", "not_authorized", "unavailable", "pending", "analyzed"] = "unavailable"
    voice_spoof_prob: Optional[float] = None
    is_provisional: bool = True
    parameters: Optional[Dict[str, Any]] = None
    call_id: Optional[str] = None  # Populated once finalized to DB


# ── WebSocket Messages & Events ──────────────────────────────────────────────

class WSAuthMessage(BaseModel):
    """Client auth handshake message."""
    type: Literal["auth"] = "auth"
    token: str
    session_id: Optional[str] = None
    source_type: Optional[str] = "microphone"
    audio_authorized: bool = False


class WSSubmitTextMessage(BaseModel):
    """Client event to submit non-audio suspicious text."""
    type: Literal["submit_message"] = "submit_message"
    text: str = Field(..., min_length=1, max_length=10000)
    speaker: Optional[str] = "caller"
    timestamp_s: Optional[float] = None


class WSStopMessage(BaseModel):
    """Client event to finalize and stop the session."""
    type: Literal["stop"] = "stop"


class WSCancelMessage(BaseModel):
    """Client event to cancel/abort session without report."""
    type: Literal["cancel"] = "cancel"


class WSEvent(BaseModel):
    """Generic outgoing server event."""
    type: str
    timestamp_ms: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp() * 1000)
    data: Dict[str, Any] = Field(default_factory=dict)
