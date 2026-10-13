"""
Pydantic schemas for evidence extraction.
Used by Tier 2 extractors and the Trust Engine.

These schemas define the structured output from evidence extraction agents.
Each piece of evidence must include:
- The extracted value
- Supporting quote from transcript
- Timestamp (t) in seconds
- Confidence score where applicable
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime


# ============================================================================
# CLAIM EVIDENCE
# ============================================================================

class ClaimEvidence(BaseModel):
    """Evidence of an identity or relationship claim."""
    
    type: Literal[
        "relative",           # Mother, father, son, daughter, etc.
        "organization",       # Bank, government, delivery, telecom
        "authority",          # Police, tax department, legal
        "service_provider",   # Customer service, tech support
        "friend",            # Personal contact
        "unknown"            # No identity claimed
    ] = Field(..., description="Type of claim")
    
    value: str = Field(..., description="Specific identity claimed (e.g., 'mother', 'HDFC Bank')")
    quote: str = Field(..., description="Exact quote supporting this claim")
    t: float = Field(..., ge=0, description="Timestamp in seconds where claim appears")
    confidence: float = Field(..., ge=0, le=1, description="Extraction confidence (0-1)")
    language: Optional[str] = Field(None, description="Language of quote (en, hi, hinglish)")
    
    @field_validator('value')
    @classmethod
    def normalize_value(cls, v: str) -> str:
        """Normalize claim value to lowercase."""
        return v.strip().lower()


class ClaimsEvidence(BaseModel):
    """Collection of all identity claims in a call."""
    claims: List[ClaimEvidence] = Field(default_factory=list, description="All identity claims")
    primary_claim: Optional[ClaimEvidence] = Field(None, description="Most prominent claim")
    claim_changes: int = Field(0, ge=0, description="Number of times identity claim changed")


# ============================================================================
# REQUEST EVIDENCE
# ============================================================================

class MoneyRequest(BaseModel):
    """Evidence of a money transfer request."""
    amount: Optional[float] = Field(None, ge=0, description="Requested amount")
    currency: str = Field("INR", description="Currency code")
    method: Optional[str] = Field(None, description="Transfer method (UPI, bank, cash)")
    quote: str = Field(..., description="Exact quote of the request")
    t: float = Field(..., ge=0, description="Timestamp in seconds")
    confidence: float = Field(..., ge=0, le=1, description="Extraction confidence")


class CredentialRequest(BaseModel):
    """Evidence of credential or sensitive information request."""
    
    type: Literal[
        "otp",              # One-time password
        "pin",              # ATM PIN, UPI PIN
        "password",         # Account password
        "cvv",              # Card CVV
        "card_number",      # Full card number
        "account_number",   # Bank account number
        "aadhar",           # Aadhar number
        "pan",              # PAN card
        "kyc_details"       # KYC information
    ] = Field(..., description="Type of credential requested")
    
    quote: str = Field(..., description="Exact quote of the request")
    t: float = Field(..., ge=0, description="Timestamp in seconds")
    confidence: float = Field(..., ge=0, le=1, description="Extraction confidence")


class ActionRequest(BaseModel):
    """Evidence of action requests (click link, install app, etc.)."""
    
    type: Literal[
        "click_link",
        "install_app",
        "share_screen",
        "enable_remote_access",
        "disable_security",
        "visit_location",
        "other"
    ] = Field(..., description="Type of action requested")
    
    detail: Optional[str] = Field(None, description="Specific detail (URL, app name, etc.)")
    quote: str = Field(..., description="Exact quote of the request")
    t: float = Field(..., ge=0, description="Timestamp in seconds")
    confidence: float = Field(..., ge=0, le=1, description="Extraction confidence")


class RequestEvidence(BaseModel):
    """Collection of all sensitive requests in a call."""
    money_requests: List[MoneyRequest] = Field(default_factory=list)
    credential_requests: List[CredentialRequest] = Field(default_factory=list)
    action_requests: List[ActionRequest] = Field(default_factory=list)
    
    @property
    def has_sensitive_request(self) -> bool:
        """Check if any sensitive request exists."""
        return bool(
            self.money_requests or 
            self.credential_requests or 
            self.action_requests
        )
    
    @property
    def max_money_amount(self) -> float:
        """Get maximum money amount requested."""
        if not self.money_requests:
            return 0.0
        return max(req.amount or 0.0 for req in self.money_requests)


# ============================================================================
# BEHAVIOR EVIDENCE
# ============================================================================

class UrgencyEvidence(BaseModel):
    """Evidence of urgency or time pressure."""
    detected: bool = Field(..., description="Whether urgency was detected")
    quotes: List[str] = Field(default_factory=list, description="Supporting quotes")
    timestamps: List[float] = Field(default_factory=list, description="Timestamps for each quote")
    severity: Literal["low", "medium", "high"] = Field("low", description="Urgency severity")
    
    # Common urgency patterns
    patterns_found: List[str] = Field(
        default_factory=list,
        description="Detected patterns: time_limit, threat, emergency, etc."
    )


class SecrecyEvidence(BaseModel):
    """Evidence of secrecy or isolation requests."""
    detected: bool = Field(..., description="Whether secrecy was detected")
    quotes: List[str] = Field(default_factory=list, description="Supporting quotes")
    timestamps: List[float] = Field(default_factory=list, description="Timestamps for each quote")
    
    # Common secrecy patterns
    patterns_found: List[str] = Field(
        default_factory=list,
        description="Detected patterns: dont_tell, secret, alone, etc."
    )


class EmotionalPressureEvidence(BaseModel):
    """Evidence of emotional manipulation."""
    detected: bool = Field(..., description="Whether emotional pressure was detected")
    quotes: List[str] = Field(default_factory=list, description="Supporting quotes")
    timestamps: List[float] = Field(default_factory=list, description="Timestamps for each quote")
    
    # Types of emotional pressure
    pressure_types: List[Literal[
        "fear",           # Fear of consequences
        "guilt",          # Guilt manipulation
        "authority",      # Authority intimidation
        "sympathy",       # Sympathy exploitation
        "greed",          # Greed exploitation
        "confusion"       # Deliberate confusion
    ]] = Field(default_factory=list)


class CallTimingEvidence(BaseModel):
    """Evidence related to call timing."""
    hour: int = Field(..., ge=0, lt=24, description="Hour of call (0-23)")
    is_unusual: bool = Field(..., description="Whether timing is unusual")
    typical_hours: Optional[List[int]] = Field(
        None, 
        description="Typical call hours for this contact"
    )


class BehaviorEvidence(BaseModel):
    """Collection of all behavioral evidence."""
    urgency: UrgencyEvidence
    secrecy: SecrecyEvidence
    emotional_pressure: EmotionalPressureEvidence
    call_timing: Optional[CallTimingEvidence] = None
    
    @property
    def has_pressure_tactics(self) -> bool:
        """Check if any pressure tactics were used."""
        return (
            self.urgency.detected or 
            self.secrecy.detected or 
            self.emotional_pressure.detected
        )


# ============================================================================
# VOICE EVIDENCE
# ============================================================================

class VoiceSpoofEvidence(BaseModel):
    """Evidence from synthetic speech detection (Check A)."""
    spoof_prob: float = Field(..., ge=0, le=1, description="Probability of synthetic speech")
    windows_analyzed: int = Field(..., ge=0, description="Number of audio windows analyzed")
    model: str = Field(..., description="Model name and version")
    threshold_high: float = Field(0.80, description="Threshold for HIGH risk")
    threshold_medium: float = Field(0.60, description="Threshold for MEDIUM risk")


class VoiceprintMatchEvidence(BaseModel):
    """Evidence from voiceprint matching (Check B)."""
    claimed_contact: str = Field(..., description="Contact name claimed by caller")
    similarity: float = Field(..., ge=0, le=1, description="Cosine similarity score")
    enrolled: bool = Field(..., description="Whether contact has enrolled voiceprint")
    threshold: float = Field(0.70, description="Similarity threshold for match")
    
    @property
    def is_match(self) -> bool:
        """Check if voice matches enrolled voiceprint."""
        return self.enrolled and self.similarity >= self.threshold


class VoiceQualityEvidence(BaseModel):
    """Audio quality metrics."""
    duration_s: float = Field(..., ge=0, description="Total speech duration in seconds")
    snr_db: Optional[float] = Field(None, description="Signal-to-noise ratio in dB")
    clipping_detected: bool = Field(False, description="Whether audio clipping was detected")
    bitrate: Optional[int] = Field(None, description="Audio bitrate in kbps")
    
    @property
    def is_sufficient_quality(self) -> bool:
        """Check if quality is sufficient for analysis."""
        if self.duration_s < 3.0:
            return False
        if self.snr_db is not None and self.snr_db < 5.0:
            return False
        if self.clipping_detected:
            return False
        return True


class VoiceEvidence(BaseModel):
    """Complete voice analysis evidence."""
    
    status: Literal["ok", "inconclusive", "unavailable"] = Field(
        ..., 
        description="Analysis status"
    )
    
    quality: Optional[VoiceQualityEvidence] = Field(
        None, 
        description="Audio quality metrics"
    )
    
    spoof_detection: Optional[VoiceSpoofEvidence] = Field(
        None, 
        description="Synthetic speech detection results (Check A)"
    )
    
    voiceprint_match: Optional[VoiceprintMatchEvidence] = Field(
        None, 
        description="Voiceprint matching results (Check B)"
    )
    
    error_message: Optional[str] = Field(
        None, 
        description="Error message if status is unavailable"
    )
    
    @property
    def suggests_synthetic(self) -> bool:
        """Check if evidence suggests synthetic speech."""
        if self.status != "ok" or not self.spoof_detection:
            return False
        return self.spoof_detection.spoof_prob >= self.spoof_detection.threshold_high
    
    @property
    def suggests_voice_mismatch(self) -> bool:
        """Check if voice doesn't match claimed identity."""
        if self.status != "ok" or not self.voiceprint_match:
            return False
        return not self.voiceprint_match.is_match


# ============================================================================
# COMPLETE EVIDENCE EXTRACTION
# ============================================================================

class EvidenceExtraction(BaseModel):
    """Complete evidence extraction for a call."""
    
    call_id: str = Field(..., description="Call UUID")
    
    # Core evidence types
    claims: ClaimsEvidence = Field(..., description="Identity and relationship claims")
    requests: RequestEvidence = Field(..., description="Sensitive requests")
    behavior: BehaviorEvidence = Field(..., description="Behavioral evidence")
    voice: Optional[VoiceEvidence] = Field(None, description="Voice analysis evidence")
    
    # Metadata
    extraction_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When extraction was performed"
    )
    
    extractor_version: str = Field(
        "1.0",
        description="Version of extraction pipeline"
    )
    
    # Source information
    transcript_segments_analyzed: int = Field(
        0, 
        ge=0, 
        description="Number of transcript segments analyzed"
    )
    
    language_detected: Optional[str] = Field(
        None,
        description="Primary language detected"
    )
    
    # Tier information
    tier1_signals: List[str] = Field(
        default_factory=list,
        description="Signals detected by Tier 1 (regex/classifier)"
    )
    
    tier2_used: bool = Field(
        False,
        description="Whether Tier 2 (LLM) extractors were used"
    )
    
    fallback_used: bool = Field(
        False,
        description="Whether fallback (regex) was used due to LLM failure"
    )
    
    # Warnings
    extraction_warnings: List[str] = Field(
        default_factory=list,
        description="Warnings or limitations in extraction"
    )
    
    @property
    def has_red_flags(self) -> bool:
        """Check if evidence contains major red flags."""
        return (
            self.requests.has_sensitive_request or
            self.behavior.has_pressure_tactics or
            (self.voice and (self.voice.suggests_synthetic or self.voice.suggests_voice_mismatch))
        )
    
    @property
    def evidence_quality_score(self) -> float:
        """Calculate overall evidence quality (0-1)."""
        score = 0.0
        total = 0.0
        
        # Claims quality
        if self.claims.claims:
            avg_conf = sum(c.confidence for c in self.claims.claims) / len(self.claims.claims)
            score += avg_conf * 0.3
        total += 0.3
        
        # Requests quality
        all_requests = (
            self.requests.money_requests +
            self.requests.credential_requests +
            self.requests.action_requests
        )
        if all_requests:
            avg_conf = sum(r.confidence for r in all_requests) / len(all_requests)
            score += avg_conf * 0.3
        total += 0.3
        
        # Voice quality
        if self.voice and self.voice.status == "ok":
            score += 0.2
        total += 0.2
        
        # Tier 2 usage (LLM more reliable than regex)
        if self.tier2_used and not self.fallback_used:
            score += 0.2
        total += 0.2
        
        return score / total if total > 0 else 0.0


# ============================================================================
# TIER 1 SIGNALS (Instant Detection)
# ============================================================================

class Tier1Signal(BaseModel):
    """A signal detected by Tier 1 instant detection."""
    signal_type: str = Field(..., description="Type of signal (OTP_REQUEST, MONEY_REQUEST, etc.)")
    severity: Literal["low", "medium", "high", "critical"] = Field(..., description="Signal severity")
    quote: str = Field(..., description="Text that triggered the signal")
    t: float = Field(..., ge=0, description="Timestamp in seconds")
    pattern_matched: str = Field(..., description="Pattern or rule that matched")
    confidence: float = Field(..., ge=0, le=1, description="Detection confidence")


class Tier1DetectionResult(BaseModel):
    """Result from Tier 1 instant detection."""
    signals: List[Tier1Signal] = Field(default_factory=list, description="Detected signals")
    highest_severity: Optional[Literal["low", "medium", "high", "critical"]] = None
    detection_time_ms: float = Field(..., ge=0, description="Detection time in milliseconds")
    
    @property
    def has_critical_signal(self) -> bool:
        """Check if any critical signal was detected."""
        return any(s.severity == "critical" for s in self.signals)
    
    @property
    def has_high_or_critical_signal(self) -> bool:
        """Check if any high or critical signal was detected."""
        return any(s.severity in ["high", "critical"] for s in self.signals)


# ============================================================================
# EXPORT FOR TRUST ENGINE
# ============================================================================

class TrustEngineInput(BaseModel):
    """Input to the Trust Engine (Judge)."""
    call_id: str
    evidence: EvidenceExtraction
    channel_status: Literal["VERIFIED", "UNKNOWN", "MISMATCH"]
    trust_graph_context: dict  # From Trust Graph
    call_timestamp: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "call_id": "550e8400-e29b-41d4-a716-446655440000",
                "evidence": {
                    "claims": {"claims": [{"type": "relative", "value": "mother", "quote": "Mummy bol rahi hoon", "t": 3.2, "confidence": 0.9}]},
                    "requests": {"money_requests": [{"amount": 50000, "quote": "50,000 rupaye bhej do", "t": 11.0, "confidence": 0.95}]},
                    "behavior": {"urgency": {"detected": True}, "secrecy": {"detected": True}}
                },
                "channel_status": "MISMATCH",
                "call_timestamp": "2026-10-13T02:30:00Z"
            }
        }
