"""Pydantic schemas for request/response validation."""

# Report schemas
from app.schemas.report import (
    TranscriptSegment,
    TranscriptResponse,
    AgentFinding,
    AnalysisReportResponse
)

# Evidence schemas
from app.schemas.evidence import (
    # Claim evidence
    ClaimEvidence,
    ClaimsEvidence,
    
    # Request evidence
    MoneyRequest,
    CredentialRequest,
    ActionRequest,
    RequestEvidence,
    
    # Behavior evidence
    UrgencyEvidence,
    SecrecyEvidence,
    EmotionalPressureEvidence,
    CallTimingEvidence,
    BehaviorEvidence,
    
    # Voice evidence
    VoiceSpoofEvidence,
    VoiceprintMatchEvidence,
    VoiceQualityEvidence,
    VoiceEvidence,
    
    # Complete extraction
    EvidenceExtraction,
    
    # Tier 1 detection
    Tier1Signal,
    Tier1DetectionResult,
    
    # Trust engine input
    TrustEngineInput
)

__all__ = [
    # Report schemas
    "TranscriptSegment",
    "TranscriptResponse",
    "AgentFinding",
    "AnalysisReportResponse",
    
    # Claim evidence
    "ClaimEvidence",
    "ClaimsEvidence",
    
    # Request evidence
    "MoneyRequest",
    "CredentialRequest",
    "ActionRequest",
    "RequestEvidence",
    
    # Behavior evidence
    "UrgencyEvidence",
    "SecrecyEvidence",
    "EmotionalPressureEvidence",
    "CallTimingEvidence",
    "BehaviorEvidence",
    
    # Voice evidence
    "VoiceSpoofEvidence",
    "VoiceprintMatchEvidence",
    "VoiceQualityEvidence",
    "VoiceEvidence",
    
    # Complete extraction
    "EvidenceExtraction",
    
    # Tier 1 detection
    "Tier1Signal",
    "Tier1DetectionResult",
    
    # Trust engine input
    "TrustEngineInput",
]
