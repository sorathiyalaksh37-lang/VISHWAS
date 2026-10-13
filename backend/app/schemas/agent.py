"""
Agent schemas for Phase 3 Agentic AI (Fraud Agent + Skeptic Agent).

These schemas define structured inputs and outputs for LLM-based agents
that provide additional reasoning alongside the deterministic Trust Engine.

Design Principle: Agents propose. Rules decide. Humans verify.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AgentFinding(BaseModel):
    """
    Structured finding from the Fraud Agent.
    
    The Fraud Agent examines evidence and identifies suspicious patterns.
    All findings must reference actual evidence IDs from the validated evidence package.
    """
    finding_id: str = Field(..., description="Unique identifier for this finding")
    finding_type: str = Field(
        ...,
        description="Category: identity_concern, sensitive_request, behavioral_pressure, channel_inconsistency, voice_indicator"
    )
    evidence_ids: List[str] = Field(
        ...,
        min_length=1,
        description="Evidence IDs that support this finding (must exist in evidence package)"
    )
    reason: str = Field(
        ...,
        max_length=500,
        description="Concise explanation of why this evidence combination is suspicious"
    )
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Model-reported confidence (NOT calibrated probability of fraud)"
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="Missing information or uncertainty that weakens this finding"
    )
    requires_review: bool = Field(
        default=False,
        description="Whether human verification is strongly recommended"
    )


class AgentChallenge(BaseModel):
    """
    Structured challenge from the Skeptic Agent.
    
    The Skeptic Agent evaluates Fraud Agent findings and identifies:
    - Unsupported conclusions
    - Alternative interpretations
    - Missing context
    - Negated or educational phrases
    - Unreliable identity mismatches
    """
    challenge_id: str = Field(..., description="Unique identifier for this challenge")
    finding_id: str = Field(..., description="ID of the finding being challenged")
    challenge_type: str = Field(
        ...,
        description="Type: unsupported_evidence, alternative_interpretation, missing_context, negation, supported"
    )
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="Additional evidence IDs relevant to this challenge"
    )
    explanation: str = Field(
        ...,
        max_length=500,
        description="Explanation of the challenge or support"
    )
    alternative_interpretation: Optional[str] = Field(
        None,
        max_length=300,
        description="Alternative benign interpretation of the evidence"
    )
    missing_evidence: List[str] = Field(
        default_factory=list,
        description="What additional evidence would clarify this finding"
    )
    verification_suggestion: Optional[str] = Field(
        None,
        max_length=200,
        description="Suggested verification action to resolve uncertainty"
    )


class AgentAnalysisResult(BaseModel):
    """
    Combined result from both Fraud and Skeptic agents.
    
    Contains validated findings, challenges, and metadata.
    Preserves disagreements and uncertainty for human review.
    """
    fraud_findings: List[AgentFinding] = Field(
        default_factory=list,
        description="Validated findings from Fraud Agent"
    )
    skeptic_challenges: List[AgentChallenge] = Field(
        default_factory=list,
        description="Validated challenges from Skeptic Agent"
    )
    agent_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Execution metadata (timings, model info, etc.)"
    )
    analysis_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When agent analysis was performed"
    )
    tier2_status: str = Field(
        ...,
        description="Status: completed, partial_failure, fraud_failed, skeptic_failed, unavailable, disabled"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings about agent execution or validation issues"
    )


class AgentEvidencePackage(BaseModel):
    """
    Bounded evidence package sent to agents.
    
    Contains only validated, necessary information to minimize
    personal data sent to external LLM providers.
    """
    call_id: str
    evidence_summary: Dict[str, Any] = Field(
        ...,
        description="Structured evidence (claims, requests, behavior, voice)"
    )
    trust_context: Dict[str, Any] = Field(
        ...,
        description="Trust Graph context (channel status, verified contacts)"
    )
    phase2_signals: Dict[str, Any] = Field(
        ...,
        description="Existing Phase 2 risk signals and scores"
    )
    evidence_quality: float = Field(..., ge=0.0, le=1.0)
    warnings: List[str] = Field(default_factory=list)


class FraudAgentRequest(BaseModel):
    """Request to Fraud Agent."""
    evidence_package: AgentEvidencePackage
    request_id: str
    timeout_seconds: float = 30.0


class SkepticAgentRequest(BaseModel):
    """Request to Skeptic Agent."""
    evidence_package: AgentEvidencePackage
    fraud_findings: List[AgentFinding]
    request_id: str
    timeout_seconds: float = 30.0


class FraudAgentResponse(BaseModel):
    """Response from Fraud Agent."""
    findings: List[AgentFinding]
    processing_time_seconds: float
    model_info: Dict[str, str]


class SkepticAgentResponse(BaseModel):
    """Response from Skeptic Agent."""
    challenges: List[AgentChallenge]
    processing_time_seconds: float
    model_info: Dict[str, str]
