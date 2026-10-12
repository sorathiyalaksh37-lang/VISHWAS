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


class AnalysisReportResponse(BaseModel):
    """Complete analysis report response."""
    call_id: str = Field(..., description="Call UUID")
    status: str = Field(..., description="Processing status")
    analysis_mode: str = Field(..., description="Analysis mode (mock or real)")
    language: Optional[str] = Field(None, description="Detected language")
    transcript: Optional[TranscriptResponse] = Field(None, description="Transcript data")
    agent_findings: List[AgentFinding] = Field(default_factory=list, description="Agent findings")
    risk_level: str = Field(..., description="Overall risk level")
    risk_score: Optional[float] = Field(None, ge=0, le=100, description="Numeric risk score")
    reasons: List[str] = Field(default_factory=list, description="Risk factors")
    recommended_actions: List[str] = Field(default_factory=list, description="Recommended actions")
    warnings: List[str] = Field(default_factory=list, description="Warnings and limitations")
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    is_mock: bool = Field(..., description="Whether this is mock data")
