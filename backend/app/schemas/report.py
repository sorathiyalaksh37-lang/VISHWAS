"""
Pydantic schemas for analysis reports and transcripts.
"""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List


class TranscriptSegment(BaseModel):
    """A segment of transcribed speech."""
    start: float = Field(..., ge=0, description="Start time in seconds")
    end: float = Field(..., gt=0, description="End time in seconds")
    speaker: Optional[str] = Field(None, description="Speaker identifier")
    text: str = Field(..., description="Transcribed text")
    language: Optional[str] = Field(None, description="Language code (ISO 639-1)")
    
    # Phase 1: Streaming ASR support
    is_final: Optional[bool] = Field(None, description="Whether text is committed (True) or partial/provisional (False). None = unknown (treat as partial)")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="ASR confidence score 0-1, if available")
    session_id: Optional[str] = Field(None, description="Session/chunk identifier for deduplication")
    
    @field_validator('end')
    @classmethod
    def end_after_start(cls, v: float, info) -> float:
        """Validate that end time is after start time."""
        if 'start' in info.data and v <= info.data['start']:
            raise ValueError('end time must be after start time')
        return v


class TranscriptResponse(BaseModel):
    """Response for transcript endpoint."""
    call_id: str = Field(..., description="Call UUID")
    language: Optional[str] = Field(None, description="Detected primary language")
    transcription_status: str = Field(..., description="Transcription status")
    segments: List[TranscriptSegment] = Field(default_factory=list, description="Transcript segments")
    is_mock: bool = Field(..., description="Whether this is mock data")


class AgentFinding(BaseModel):
    """A finding from a detection agent."""
    agent: str = Field(..., description="Agent identifier")
    signal: str = Field(..., description="Signal type detected")
    severity: str = Field(..., description="Severity level: low, medium, high, critical")
    evidence_text: str = Field(..., description="Supporting text evidence")
    start_time: Optional[float] = Field(None, ge=0, description="Evidence start time")
    end_time: Optional[float] = Field(None, gt=0, description="Evidence end time")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Confidence score (0-1)")
    source: str = Field(..., description="Source: mock or model identifier")


class CategoryScores(BaseModel):
    """Score breakdown by category (caps: identity 25, request 30, behavior 20, channel 15, voice 10)."""
    identity: Optional[int] = Field(None, ge=0, le=25)
    request: Optional[int] = Field(None, ge=0, le=30)
    behavior: Optional[int] = Field(None, ge=0, le=20)
    channel: Optional[int] = Field(None, ge=0, le=15)
    voice: Optional[int] = Field(None, ge=0, le=10)


class Verification(BaseModel):
    """Suggested verification action for the user."""
    action: Optional[str] = Field(None, description="snake_case action, e.g. callback_saved_number")
    target: Optional[str] = Field(None, description="Human-readable target, e.g. 'Mom (saved: +91-98xxxx)'")
    safe_word_prompt: Optional[bool] = Field(None, description="Whether to ask for safe word")


class SpeakerMatch(BaseModel):
    """Speaker similarity result."""
    claimed_contact: Optional[str] = Field(None)
    similarity: Optional[float] = Field(None, ge=0.0, le=1.0)
    enrolled: Optional[bool] = Field(None)


class VoiceEvidence(BaseModel):
    """Voice layer analysis result."""
    status: Optional[str] = Field(None, description="ok | inconclusive | unavailable")
    spoof_prob: Optional[float] = Field(None, ge=0.0, le=1.0)
    windows_analyzed: Optional[int] = Field(None, ge=0)
    speaker_match: Optional[SpeakerMatch] = Field(None)
    quality: Optional[dict] = Field(None, description="{duration_s, snr_db}")
    model: Optional[str] = Field(None)


class Counterfactual(BaseModel):
    """Counterfactual explanation."""
    change: Optional[str] = Field(None)
    new_score: Optional[int] = Field(None, ge=0, le=100)


class AnalysisReportResponse(BaseModel):
    """Complete analysis report response — v3 contract."""
    call_id: str = Field(..., description="Call UUID")
    status: str = Field(..., description="Processing status")
    analysis_mode: str = Field(..., description="Analysis mode (mock or real)")
    language: Optional[str] = Field(None, description="Detected language")
    transcript: Optional[TranscriptResponse] = Field(None, description="Transcript data")

    # ── v3 primary fields ──────────────────────────────────────────────────────
    level: str = Field(..., description="Risk level: LOW | MEDIUM | HIGH | CRITICAL (uppercase)")
    score: int = Field(..., ge=0, le=100, description="Composite risk score 0-100")
    category_scores: Optional[CategoryScores] = Field(None)
    fired_rules: List[str] = Field(default_factory=list, description="Triggered rule IDs")
    killchain_stage: Optional[str] = Field(None)
    verification: Optional[Verification] = Field(None)
    voice: Optional[VoiceEvidence] = Field(None)
    counterfactuals: List[Counterfactual] = Field(default_factory=list)

    # ── legacy / backward-compat fields ────────────────────────────────────────
    agent_findings: List[AgentFinding] = Field(default_factory=list, description="Agent findings")
    reasons: List[str] = Field(default_factory=list, description="Risk factors")
    recommended_actions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: Optional[datetime] = Field(None)

    @field_validator("level", mode="before")
    @classmethod
    def normalise_level(cls, v: str) -> str:
        """Accept lowercase stored values and normalise to uppercase per v3 contract."""
        return v.upper() if isinstance(v, str) else v


