"""
Deterministic Risk Scoring Engine for VISHWAS.

Implements evidence-based scoring with:
- Category-based scoring with caps
- Hard-rule floors for high-risk combinations
- Evidence deduplication
- Explainable score breakdown

Design Principle: Scoring proposes. Judge decides.
"""
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

from app.schemas.evidence import EvidenceExtraction
from app.trust_engine.trust_graph import ChannelStatus

logger = logging.getLogger(__name__)


# Scoring Configuration
SCORING_CATEGORIES = {
    "identity": 25,        # Identity/relationship inconsistency
    "request": 30,         # Sensitive requests (financial, credentials)
    "behavior": 20,        # Urgency, secrecy, pressure tactics
    "channel": 15,         # Communication channel inconsistency
    "voice": 10,           # Voice-clone signal (soft signal)
}

RISK_BANDS = {
    "LOW": (0, 24),
    "MEDIUM": (25, 49),
    "HIGH": (50, 74),
    "CRITICAL": (75, 100),
}


class RiskLevel(str, Enum):
    """Risk level enumeration."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class ScoreBreakdown:
    """Detailed score breakdown by category."""
    identity: int = 0
    request: int = 0
    behavior: int = 0
    channel: int = 0
    voice: int = 0
    
    total: int = 0
    capped_total: int = 0
    final_score: int = 0
    
    reasons: List[str] = field(default_factory=list)
    fired_rules: List[str] = field(default_factory=list)
    applied_floors: List[str] = field(default_factory=list)
    
    @property
    def risk_level(self) -> RiskLevel:
        """Determine risk level from final score."""
        if self.final_score >= 75:
            return RiskLevel.CRITICAL
        elif self.final_score >= 50:
            return RiskLevel.HIGH
        elif self.final_score >= 25:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW


@dataclass
class HardRuleFloor:
    """Hard-rule floor definition."""
    rule_id: str
    name: str
    floor_score: int
    conditions: List[str]
    explanation: str


class TrustScorer:
    """
    Deterministic scoring engine.
    
    Calculates risk score from validated evidence and trust context.
    Applies category caps, hard-rule floors, and deduplication.
    """
    
    # Define hard-rule floors
    HARD_FLOORS = [
        HardRuleFloor(
            rule_id="FLOOR_OTP_NONVERIFIED",
            name="OTP request on non-verified channel",
            floor_score=75,
            conditions=["credential_request_otp_or_pin", "channel_not_verified"],
            explanation="OTP/PIN request on unverified channel triggers minimum CRITICAL risk"
        ),
        HardRuleFloor(
            rule_id="FLOOR_MONEY_SECRECY_MISMATCH",
            name="Money request with secrecy and channel mismatch",
            floor_score=50,
            conditions=["money_request", "secrecy_detected", "channel_mismatch"],
            explanation="Money request combined with secrecy and identity mismatch"
        ),
        HardRuleFloor(
            rule_id="FLOOR_VOICE_RELATIVE_NONVERIFIED",
            name="Relative claim with voice clone and unverified channel",
            floor_score=50,
            conditions=["relative_claim", "voice_spoof_high", "channel_not_verified"],
            explanation="Family member claim with synthetic voice on unverified number"
        ),
    ]
    
    def __init__(self):
        """Initialize scorer with category caps."""
        self.category_caps = SCORING_CATEGORIES
        self._seen_evidence: Set[str] = set()
        logger.info("TrustScorer initialized with category caps")
    
    def calculate_score(
        self,
        evidence: EvidenceExtraction,
        channel_status: str,
        trust_context: Dict,
    ) -> ScoreBreakdown:
        """
        Calculate risk score from evidence and context.
        
        Args:
            evidence: Validated evidence extraction
            channel_status: Channel verification status
            trust_context: Trust Graph context
            
        Returns:
            ScoreBreakdown with category scores and explanations
        """
        breakdown = ScoreBreakdown()
        self._seen_evidence.clear()
        
        # Score each category
        breakdown.identity = self._score_identity(evidence, channel_status, trust_context, breakdown)
        breakdown.request = self._score_requests(evidence, breakdown)
        breakdown.behavior = self._score_behavior(evidence, breakdown)
        breakdown.channel = self._score_channel(channel_status, evidence, breakdown)
        breakdown.voice = self._score_voice(evidence, breakdown)
        
        # Calculate total with caps
        breakdown.total = (
            breakdown.identity +
            breakdown.request +
            breakdown.behavior +
            breakdown.channel +
            breakdown.voice
        )
        breakdown.capped_total = min(100, breakdown.total)
        
        # Apply hard-rule floors
        breakdown.final_score = self._apply_hard_floors(
            breakdown.capped_total,
            evidence,
            channel_status,
            trust_context,
            breakdown
        )
        
        # Ensure final score is in valid range
        breakdown.final_score = max(0, min(100, breakdown.final_score))
        
        logger.info(f"Score calculated: {breakdown.final_score} ({breakdown.risk_level.value})")
        return breakdown
    
    def _score_identity(
        self,
        evidence: EvidenceExtraction,
        channel_status: str,
        trust_context: Dict,
        breakdown: ScoreBreakdown,
    ) -> int:
        """Score identity/relationship inconsistencies (max 25)."""
        score = 0
        cap = self.category_caps["identity"]
        
        # Unsaved number claims trusted relationship
        if evidence.claims.claims:
            for claim in evidence.claims.claims:
                if claim.type in ["relative", "organization", "authority"]:
                    if channel_status == ChannelStatus.MISMATCH.value:
                        score += 20
                        breakdown.reasons.append(
                            f"Caller claims to be {claim.value} but number doesn't match verified records"
                        )
                        breakdown.fired_rules.append("IDENTITY_MISMATCH")
                    elif channel_status == ChannelStatus.UNKNOWN.value:
                        score += 15
                        breakdown.reasons.append(
                            f"Caller claims to be {claim.value} from unknown number"
                        )
                        breakdown.fired_rules.append("IDENTITY_UNKNOWN")
                    break  # Score primary claim only
        
        # Safe word check (if implemented)
        # score += 5 if safe_word_failed else 0
        
        return min(score, cap)
    
    def _score_requests(self, evidence: EvidenceExtraction, breakdown: ScoreBreakdown) -> int:
        """Score sensitive requests (max 30)."""
        score = 0
        cap = self.category_caps["request"]
        
        # Credential requests (highest risk)
        if evidence.requests.credential_requests:
            cred_types = {req.type for req in evidence.requests.credential_requests}
            
            if "otp" in cred_types or "pin" in cred_types:
                score += 30
                breakdown.reasons.append("Request for OTP or PIN detected")
                breakdown.fired_rules.append("REQ_OTP_PIN")
            elif "password" in cred_types:
                score += 25
                breakdown.reasons.append("Request for password detected")
                breakdown.fired_rules.append("REQ_PASSWORD")
            elif any(ct in cred_types for ct in ["cvv", "card_number", "account_number"]):
                score += 20
                breakdown.reasons.append("Request for sensitive financial information")
                breakdown.fired_rules.append("REQ_FINANCIAL")
            else:
                score += 15
                breakdown.reasons.append("Request for confidential information")
                breakdown.fired_rules.append("REQ_CONFIDENTIAL")
        
        # Money requests
        elif evidence.requests.money_requests:
            max_amount = evidence.requests.max_money_amount
            if max_amount and max_amount >= 50000:
                score += 20
                breakdown.reasons.append(f"Request to transfer ₹{max_amount:,.0f}")
                breakdown.fired_rules.append("REQ_MONEY_HIGH")
            elif max_amount:
                score += 15
                breakdown.reasons.append(f"Request to transfer ₹{max_amount:,.0f}")
                breakdown.fired_rules.append("REQ_MONEY")
            else:
                score += 15
                breakdown.reasons.append("Money transfer request detected")
                breakdown.fired_rules.append("REQ_MONEY")
        
        # Action requests
        elif evidence.requests.action_requests:
            score += 10
            breakdown.reasons.append("Suspicious action request detected")
            breakdown.fired_rules.append("REQ_ACTION")
        
        return min(score, cap)
    
    def _score_behavior(self, evidence: EvidenceExtraction, breakdown: ScoreBreakdown) -> int:
        """Score behavioral pressure tactics (max 20)."""
        score = 0
        cap = self.category_caps["behavior"]
        
        # Urgency/threats
        if evidence.behavior.urgency.detected:
            if evidence.behavior.urgency.severity == "high":
                score += 15
                breakdown.reasons.append("High urgency or threats detected")
                breakdown.fired_rules.append("BEHAVIOR_URGENCY_HIGH")
            elif evidence.behavior.urgency.severity == "medium":
                score += 10
                breakdown.reasons.append("Urgency pressure detected")
                breakdown.fired_rules.append("BEHAVIOR_URGENCY_MED")
            else:
                score += 5
                breakdown.reasons.append("Time pressure indicators")
                breakdown.fired_rules.append("BEHAVIOR_URGENCY_LOW")
        
        # Secrecy
        if evidence.behavior.secrecy.detected:
            score += 5
            breakdown.reasons.append("Secrecy or isolation tactics detected")
            breakdown.fired_rules.append("BEHAVIOR_SECRECY")
        
        # Emotional pressure
        if evidence.behavior.emotional_pressure.detected:
            score += 5
            pressure_types = ", ".join(evidence.behavior.emotional_pressure.pressure_types)
            breakdown.reasons.append(f"Emotional manipulation detected: {pressure_types}")
            breakdown.fired_rules.append("BEHAVIOR_EMOTION")
        
        return min(score, cap)
    
    def _score_channel(
        self,
        channel_status: str,
        evidence: EvidenceExtraction,
        breakdown: ScoreBreakdown,
    ) -> int:
        """Score channel inconsistencies (max 15)."""
        score = 0
        cap = self.category_caps["channel"]
        
        if channel_status == ChannelStatus.MISMATCH.value:
            score += 15
            breakdown.reasons.append("Communication channel mismatch with verified records")
            breakdown.fired_rules.append("CHANNEL_MISMATCH")
        elif channel_status == ChannelStatus.UNKNOWN.value:
            # Only score if there's also a claim
            if evidence.claims.claims:
                score += 10
                breakdown.reasons.append("Identity claimed from unknown number")
                breakdown.fired_rules.append("CHANNEL_UNKNOWN")
        
        return min(score, cap)
    
    def _score_voice(self, evidence: EvidenceExtraction, breakdown: ScoreBreakdown) -> int:
        """Score voice-clone indicators (max 10, soft signal)."""
        score = 0
        cap = self.category_caps["voice"]
        
        if not evidence.voice or evidence.voice.status != "ok":
            return 0  # Voice unavailable or inconclusive
        
        # Check A: Spoof detection
        if evidence.voice.spoof_detection:
            spoof_prob = evidence.voice.spoof_detection.spoof_prob
            
            if spoof_prob >= 0.80:
                score += 10
                breakdown.reasons.append("Voice analysis indicates synthetic speech (experimental)")
                breakdown.fired_rules.append("VOICE_SPOOF_HIGH")
            elif spoof_prob >= 0.60:
                score += 5
                breakdown.reasons.append("Possible synthetic voice indicators (experimental)")
                breakdown.fired_rules.append("VOICE_SPOOF_MED")
        
        # Check B: Voiceprint mismatch (within cap)
        if evidence.voice.voiceprint_match:
            if evidence.voice.voiceprint_match.enrolled and not evidence.voice.voiceprint_match.is_match:
                score = min(score + 5, cap)
                breakdown.reasons.append("Voice doesn't match enrolled voiceprint (experimental)")
                breakdown.fired_rules.append("VOICE_MISMATCH")
        
        return min(score, cap)
    
    def _apply_hard_floors(
        self,
        preliminary_score: int,
        evidence: EvidenceExtraction,
        channel_status: str,
        trust_context: Dict,
        breakdown: ScoreBreakdown,
    ) -> int:
        """Apply hard-rule floors based on risk combinations."""
        max_floor = preliminary_score
        
        for floor in self.HARD_FLOORS:
            if self._check_floor_conditions(floor, evidence, channel_status, trust_context):
                if floor.floor_score > max_floor:
                    max_floor = floor.floor_score
                    breakdown.applied_floors.append(floor.name)
                    breakdown.reasons.append(floor.explanation)
                    logger.info(f"Applied floor: {floor.name} (score → {floor.floor_score})")
        
        return max_floor
    
    def _check_floor_conditions(
        self,
        floor: HardRuleFloor,
        evidence: EvidenceExtraction,
        channel_status: str,
        trust_context: Dict,
    ) -> bool:
        """Check if floor conditions are met."""
        conditions_met = []
        
        for condition in floor.conditions:
            if condition == "credential_request_otp_or_pin":
                has_otp_pin = any(
                    req.type in ["otp", "pin"]
                    for req in evidence.requests.credential_requests
                )
                conditions_met.append(has_otp_pin)
            
            elif condition == "channel_not_verified":
                conditions_met.append(channel_status != ChannelStatus.VERIFIED.value)
            
            elif condition == "money_request":
                conditions_met.append(len(evidence.requests.money_requests) > 0)
            
            elif condition == "secrecy_detected":
                conditions_met.append(evidence.behavior.secrecy.detected)
            
            elif condition == "channel_mismatch":
                conditions_met.append(channel_status == ChannelStatus.MISMATCH.value)
            
            elif condition == "relative_claim":
                has_relative = any(
                    claim.type == "relative"
                    for claim in evidence.claims.claims
                )
                conditions_met.append(has_relative)
            
            elif condition == "voice_spoof_high":
                if evidence.voice and evidence.voice.status == "ok" and evidence.voice.spoof_detection:
                    conditions_met.append(evidence.voice.spoof_detection.spoof_prob >= 0.80)
                else:
                    conditions_met.append(False)
            
            else:
                conditions_met.append(False)
        
        return all(conditions_met)
    
    def reset_session(self):
        """Reset evidence deduplication for new assessment."""
        self._seen_evidence.clear()
