"""
Deterministic Trust Judge for VISHWAS.

Final risk assessment component that:
- Validates input
- Coordinates scoring
- Generates explainable reports
- Recommends verification actions

Design Principle: Judge decides deterministically. Humans verify.
"""
import logging
import hashlib
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from app.schemas.evidence import EvidenceExtraction
from app.trust_engine.trust_graph import TrustGraph, ChannelStatus
from app.trust_engine.scoring import TrustScorer, ScoreBreakdown, RiskLevel

logger = logging.getLogger(__name__)


@dataclass
class RiskAssessment:
    """Complete risk assessment result."""
    call_id: str
    score: int
    risk_level: str
    category_scores: Dict[str, int]
    reasons: List[str]
    fired_rules: List[str]
    applied_floors: List[str]
    
    # Context
    channel_status: str
    evidence_quality: float
    transcript_segments_analyzed: int
    
    # Recommendations
    verification_method: Optional[str] = None
    verification_details: Optional[Dict[str, Any]] = None
    killchain_stage: Optional[str] = None  # Phase 5: Added killchain detection
    
    # Metadata
    assessment_timestamp: datetime = field(default_factory=datetime.utcnow)
    extractor_version: str = "1.0"
    scorer_version: str = "1.0"
    judge_version: str = "1.0"
    
    # Audit
    audit_hash: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "call_id": self.call_id,
            "score": self.score,
            "risk_level": self.risk_level,
            "category_scores": self.category_scores,
            "reasons": self.reasons,
            "fired_rules": self.fired_rules,
            "applied_floors": self.applied_floors,
            "channel_status": self.channel_status,
            "evidence_quality": self.evidence_quality,
            "transcript_segments_analyzed": self.transcript_segments_analyzed,
            "verification_method": self.verification_method,
            "verification_details": self.verification_details,
            "killchain_stage": self.killchain_stage,  # Phase 5
            "assessment_timestamp": self.assessment_timestamp.isoformat(),
            "extractor_version": self.extractor_version,
            "scorer_version": self.scorer_version,
            "judge_version": self.judge_version,
            "audit_hash": self.audit_hash,
            "warnings": self.warnings,
        }


class TrustJudge:
    """
    Deterministic Trust Judge.
    
    Responsibilities:
    - Coordinate evidence extraction, trust context, and scoring
    - Apply final decision rules
    - Generate explainable risk assessments
    - Recommend appropriate verification actions
    - Maintain determinism and auditability
    """
    
    def __init__(self):
        """Initialize Trust Judge."""
        self.scorer = TrustScorer()
        logger.info("TrustJudge initialized")
    
    def evaluate(
        self,
        call_id: str,
        evidence: EvidenceExtraction,
        trust_graph: TrustGraph,
        caller_number: Optional[str] = None,
    ) -> RiskAssessment:
        """
        Evaluate call and produce risk assessment.
        
        Args:
            call_id: Unique call identifier
            evidence: Validated evidence extraction
            trust_graph: Trust Graph instance
            caller_number: Caller's phone number
            
        Returns:
            Complete RiskAssessment
        """
        logger.info(f"Evaluating call {call_id}")
        
        # Get trust context
        claimed_identity = evidence.claims.primary_claim.value if evidence.claims.primary_claim else None
        claimed_relation = evidence.claims.primary_claim.type if evidence.claims.primary_claim else None
        
        trust_context = trust_graph.get_trust_context(
            caller_number,
            claimed_identity,
            claimed_relation
        )
        
        channel_status = trust_context["channel_status"]
        
        # Calculate score
        score_breakdown = self.scorer.calculate_score(
            evidence,
            channel_status,
            trust_context
        )
        
        # Generate verification recommendations
        verification_method, verification_details = self._generate_verification(
            score_breakdown.risk_level,
            trust_context,
            evidence
        )
        
        # Collect warnings
        warnings = self._collect_warnings(evidence, trust_context)
        
        # Detect killchain stage (Phase 5: Task 2)
        killchain_stage = self._detect_killchain_stage(evidence, trust_context)
        
        # Build assessment
        assessment = RiskAssessment(
            call_id=call_id,
            score=score_breakdown.final_score,
            risk_level=score_breakdown.risk_level.value,
            category_scores={
                "identity": score_breakdown.identity,
                "request": score_breakdown.request,
                "behavior": score_breakdown.behavior,
                "channel": score_breakdown.channel,
                "voice": score_breakdown.voice,
            },
            reasons=score_breakdown.reasons,
            fired_rules=score_breakdown.fired_rules,
            applied_floors=score_breakdown.applied_floors,
            channel_status=channel_status,
            evidence_quality=evidence.evidence_quality_score,
            transcript_segments_analyzed=evidence.transcript_segments_analyzed,
            verification_method=verification_method,
            verification_details=verification_details,
            killchain_stage=killchain_stage,  # Phase 5: Added
            extractor_version=evidence.extractor_version,
            warnings=warnings,
        )
        
        # Generate audit hash
        assessment.audit_hash = self._generate_audit_hash(assessment, evidence)
        
        logger.info(
            f"Assessment complete: {assessment.risk_level} "
            f"(score={assessment.score}, hash={assessment.audit_hash[:8]}...)"
        )
        
        return assessment
    
    def _generate_verification(
        self,
        risk_level: RiskLevel,
        trust_context: Dict,
        evidence: EvidenceExtraction,
    ) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Generate appropriate verification recommendations.
        
        Returns:
            Tuple of (method, details)
        """
        details = {}
        
        if risk_level == RiskLevel.CRITICAL:
            # CRITICAL: Strongly recommend stopping and verifying
            if trust_context.get("contact_found") and trust_context.get("verified_numbers"):
                method = "callback_saved_number"
                details = {
                    "action": "Do not proceed with any sensitive action",
                    "recommendation": "End this call and contact the person using a previously verified number",
                    "safe_numbers": trust_context.get("verified_numbers", []),
                    "contact_name": trust_context.get("contact_name"),
                }
            else:
                method = "independent_verification"
                details = {
                    "action": "Do not proceed with any sensitive action",
                    "recommendation": "Verify this request through an independent, trusted channel",
                }
        
        elif risk_level == RiskLevel.HIGH:
            # HIGH: Verify before proceeding
            if trust_context.get("contact_found"):
                method = "callback_verification"
                details = {
                    "action": "Do not share sensitive information yet",
                    "recommendation": "Verify the caller's identity through a known contact method",
                    "contact_name": trust_context.get("contact_name"),
                }
            else:
                method = "independent_verification"
                details = {
                    "action": "Be cautious",
                    "recommendation": "Independently verify any requests before taking action",
                }
        
        elif risk_level == RiskLevel.MEDIUM:
            # MEDIUM: Proceed with caution
            method = "careful_validation"
            details = {
                "action": "Proceed with caution",
                "recommendation": "Validate any unexpected requests independently",
            }
        
        else:  # LOW
            # LOW: Normal caution
            method = "normal_caution"
            details = {
                "action": "Normal conversation",
                "recommendation": "Exercise standard caution with sensitive information",
            }
        
        return method, details
    
    def _collect_warnings(
        self,
        evidence: EvidenceExtraction,
        trust_context: Dict,
    ) -> List[str]:
        """Collect warnings about assessment limitations."""
        warnings = list(evidence.extraction_warnings)
        
        # Voice availability - be specific about what's missing
        if not evidence.voice:
            warnings.append("Voice analysis not performed")
        elif evidence.voice.status == "unavailable":
            warnings.append("Voice analysis unavailable (model not loaded)")
        elif evidence.voice.status == "error":
            warnings.append("Voice analysis failed during processing")
        elif evidence.voice.status == "inconclusive":
            warnings.append("Voice analysis inconclusive (insufficient audio quality or duration)")
        # Note: If status == "ok", no warning needed
        
        # Limited trust context
        if not trust_context.get("contact_found"):
            warnings.append("No relationship context available for this caller")
        
        # Short transcript
        if evidence.transcript_segments_analyzed < 3:
            warnings.append("Very short conversation - limited evidence available")
        
        # Evidence quality
        if evidence.evidence_quality_score < 0.5:
            warnings.append("Evidence quality below optimal threshold")
        
        return warnings
    
    def _detect_killchain_stage(
        self,
        evidence: EvidenceExtraction,
        trust_context: Dict,
    ) -> Optional[str]:
        """
        Detect the current stage in the cyber killchain for scam calls.
        
        Standard scam killchain stages:
        1. RECONNAISSANCE - Information gathering
        2. IMPERSONATION - Establishing fake identity
        3. MANIPULATION - Building trust/urgency/pressure
        4. REQUEST - Requesting sensitive data or money
        5. EXFILTRATION - Obtaining the target resource
        
        Returns:
            Killchain stage name or None if indeterminate
        """
        # Stage detection based on evidence patterns
        has_claims = evidence.claims and evidence.claims.claims
        has_money_request = evidence.requests and evidence.requests.money_requests
        has_credential_request = evidence.requests and evidence.requests.credential_requests
        has_action_request = evidence.requests and evidence.requests.action_requests
        has_pressure = evidence.behavior and evidence.behavior.has_pressure_tactics
        
        # Stage 4: REQUEST - Direct request for sensitive data
        if has_credential_request or has_money_request or has_action_request:
            return "REQUEST"
        
        # Stage 3: MANIPULATION - Pressure tactics without request yet
        if has_pressure and has_claims:
            return "MANIPULATION"
        
        # Stage 2: IMPERSONATION - Identity claim without pressure or requests
        if has_claims:
            return "IMPERSONATION"
        
        # Stage 1: RECONNAISSANCE - No clear identity claim or request
        if evidence.transcript_segments_analyzed > 0:
            return "RECONNAISSANCE"
        
        return None
    
    def _generate_audit_hash(
        self,
        assessment: RiskAssessment,
        evidence: EvidenceExtraction,
    ) -> str:
        """
        Generate audit hash for reproducibility verification.
        
        Hash includes:
        - Evidence content (claims, requests, behavior)
        - Trust context (channel status)
        - Scoring rules version
        - Final score and risk level
        """
        audit_data = {
            "evidence_version": evidence.extractor_version,
            "scorer_version": assessment.scorer_version,
            "judge_version": assessment.judge_version,
            "category_scores": assessment.category_scores,
            "final_score": assessment.score,
            "risk_level": assessment.risk_level,
            "fired_rules": sorted(assessment.fired_rules),
            "applied_floors": sorted(assessment.applied_floors),
        }
        
        audit_json = json.dumps(audit_data, sort_keys=True)
        return hashlib.sha256(audit_json.encode()).hexdigest()
    
    def explain_decision(self, assessment: RiskAssessment) -> Dict[str, Any]:
        """
        Generate detailed explanation of decision.
        
        Returns:
            Dictionary with human-readable explanation
        """
        explanation = {
            "summary": f"Risk Level: {assessment.risk_level} (Score: {assessment.score}/100)",
            "reasoning": assessment.reasons,
            "category_breakdown": {
                "identity_inconsistency": f"{assessment.category_scores['identity']}/25 points",
                "sensitive_requests": f"{assessment.category_scores['request']}/30 points",
                "behavioral_pressure": f"{assessment.category_scores['behavior']}/20 points",
                "channel_mismatch": f"{assessment.category_scores['channel']}/15 points",
                "voice_indicators": f"{assessment.category_scores['voice']}/10 points",
            },
            "hard_rules_applied": assessment.applied_floors,
            "verification": {
                "method": assessment.verification_method,
                "details": assessment.verification_details,
            },
            "limitations": assessment.warnings,
        }
        
        return explanation
