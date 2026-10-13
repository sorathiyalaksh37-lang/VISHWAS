"""
Comprehensive test suite for Phase 2 Trust Engine components.
Tests Trust Graph, Scoring Engine, and Trust Judge.

**LEGACY TESTS - These tests use an outdated API and are skipped.**
**See test_trust_engine_simple.py for current API coverage.**

Original API (no longer supported):
- add_contact(phone_number, verified_name, relationship, verified)
- Fields: phone_number, verified_name, relationship, verified, verification_date

Current API (in use):
- add_contact(name, relation, phone_numbers, typical_amount)  
- Fields: name, relation, saved_numbers (JSON), typical_amount
- Case-insensitive name lookup

These tests document historical API design but are not maintained.
Full coverage is provided by:
- test_trust_engine_simple.py (8 tests, current API)
- test_agent_integration.py (Phase 3 integration)
- test_tier1_classifier.py (evidence extraction)
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Optional

from app.trust_engine.trust_graph import TrustGraph, ChannelStatus
from app.trust_engine.scoring import TrustScorer, ScoreBreakdown, RiskLevel
from app.trust_engine.judge import TrustJudge, RiskAssessment
from app.models.call import Contact
from app.schemas.evidence import (
    EvidenceExtraction, ClaimsEvidence, RequestEvidence, BehaviorEvidence, 
    ClaimEvidence, MoneyRequest, CredentialRequest, UrgencyEvidence,
    SecrecyEvidence, EmotionalPressureEvidence
)


def create_minimal_evidence(
    money_amount: Optional[float] = None,
    credential_type: Optional[str] = None,
    urgency: bool = False,
    secrecy: bool = False,
    claimed_name: Optional[str] = None,
    claimed_type: str = "relative"
) -> EvidenceExtraction:
    """Helper to create evidence for testing."""
    evidence = EvidenceExtraction(
        claims=ClaimsEvidence(claims=[], primary_claim=None, primary_claim_type=None),
        requests=RequestEvidence(
            money_requests=[],
            credential_requests=[],
            action_requests=[],
            max_money_amount=money_amount,
            has_money=bool(money_amount),
            has_credential=bool(credential_type),
            has_action=False
        ),
        behavior=BehaviorEvidence(
            urgency=UrgencyEvidence(detected=urgency, severity="high" if urgency else "low", indicators=[]),
            secrecy=SecrecyEvidence(detected=secrecy, indicators=[]),
            emotional_pressure=EmotionalPressureEvidence(detected=False, pressure_types=[], indicators=[]),
            call_timing=None
        ),
        voice=None,
        evidence_quality_score=0.8,
        transcript_segments_analyzed=5,
        extractor_version="1.0",
        extraction_warnings=[]
    )
    
    if claimed_name:
        evidence.claims.claims = [ClaimEvidence(type=claimed_type, value=claimed_name, confidence=0.95)]
        evidence.claims.primary_claim = evidence.claims.claims[0]
        evidence.claims.primary_claim_type = claimed_type
    
    if money_amount:
        evidence.requests.money_requests = [
            MoneyRequest(amount=money_amount, urgency_level="high" if urgency else "normal")
        ]
    
    if credential_type:
        evidence.requests.credential_requests = [
            CredentialRequest(type=credential_type, details=credential_type.upper())
        ]
    
    return evidence


@pytest.mark.skip(reason="Legacy tests for outdated API - see test_trust_engine_simple.py for current coverage")
class TestTrustGraph:
    """Test Trust Graph contact and channel management."""
    
    def test_add_verified_contact(self, test_db: Session):
        """Test adding a verified contact."""
        graph = TrustGraph(test_db)
        
        contact = graph.add_contact(
            phone_number="+919876543210",
            verified_name="Rajesh Kumar",
            relationship="father",
            verified=True
        )
        
        assert contact.phone_number == "+919876543210"
        assert contact.verified_name == "Rajesh Kumar"
        assert contact.relationship == "father"
        assert contact.verified is True
        assert contact.verification_date is not None
    
    def test_add_unverified_contact(self, test_db: Session):
        """Test adding an unverified contact."""
        graph = TrustGraph(test_db)
        
        contact = graph.add_contact(
            phone_number="+919123456789",
            verified_name="Unknown Caller",
            verified=False
        )
        
        assert contact.verified is False
        assert contact.verification_date is None
        assert contact.relationship is None
    
    def test_get_trust_context_verified(self, test_db: Session):
        """Test getting trust context for verified contact."""
        graph = TrustGraph(test_db)
        
        # Add verified contact
        graph.add_contact(
            phone_number="+919876543210",
            verified_name="Rajesh Kumar",
            relationship="father",
            verified=True
        )
        
        # Get trust context
        context = graph.get_trust_context(
            phone_number="+919876543210",
            claimed_identity="Rajesh Kumar",
            claimed_relationship="father"
        )
        
        assert context["channel_status"] == ChannelStatus.VERIFIED.value
        assert context["contact_found"] is True
        assert context["verified"] is True
    
    def test_get_trust_context_unknown(self, test_db: Session):
        """Test getting trust context for unknown number."""
        graph = TrustGraph(test_db)
        
        context = graph.get_trust_context(
            phone_number="+919999999999",
            claimed_identity="Unknown Person",
            claimed_relationship=None
        )
        
        assert context["channel_status"] == ChannelStatus.UNKNOWN.value
        assert context["contact_found"] is False
    
    def test_get_trust_context_mismatch(self, test_db: Session):
        """Test getting trust context with identity mismatch."""
        graph = TrustGraph(test_db)
        
        # Add verified contact
        graph.add_contact(
            phone_number="+919876543210",
            verified_name="Rajesh Kumar",
            relationship="father",
            verified=True
        )
        
        # Get context with mismatched name
        context = graph.get_trust_context(
            phone_number="+919876543210",
            claimed_identity="Suresh Sharma",
            claimed_relationship="father"
        )
        
        assert context["channel_status"] == ChannelStatus.MISMATCH.value
        assert context["contact_found"] is True

@pytest.mark.skip(reason="Legacy tests for outdated API - see test_trust_engine_simple.py for current coverage")
class TestTrustScorer:
    """Test Trust Scoring Engine."""
    
    def test_minimal_evidence_low_score(self, test_db: Session):
        """Test that minimal evidence with verified channel returns low score."""
        scorer = TrustScorer()
        graph = TrustGraph(test_db)
        
        # Add verified contact
        graph.add_contact("+919876543210", "Test User", "friend", True)
        
        evidence = create_minimal_evidence()
        context = graph.get_trust_context("+919876543210", None, None)
        
        breakdown = scorer.calculate_score(
            evidence=evidence,
            channel_status=context["channel_status"],
            trust_context=context
        )
        
        assert breakdown.final_score < 25
        assert breakdown.risk_level == RiskLevel.LOW
    
    def test_otp_request_triggers_critical(self, test_db: Session):
        """Test that OTP request on unverified channel triggers CRITICAL risk."""
        scorer = TrustScorer()
        graph = TrustGraph(test_db)
        
        evidence = create_minimal_evidence(credential_type="otp")
        context = graph.get_trust_context("+919999999999", None, None)
        
        breakdown = scorer.calculate_score(
            evidence=evidence,
            channel_status=context["channel_status"],
            trust_context=context
        )
        
        assert breakdown.final_score >= 75
        assert breakdown.risk_level == RiskLevel.CRITICAL
        assert len(breakdown.applied_floors) > 0
    
    def test_money_request_increases_score(self, test_db: Session):
        """Test that money request increases score."""
        scorer = TrustScorer()
        graph = TrustGraph(test_db)
        
        evidence = create_minimal_evidence(money_amount=150000.0)
        context = graph.get_trust_context("+919999999999", None, None)
        
        breakdown = scorer.calculate_score(
            evidence=evidence,
            channel_status=context["channel_status"],
            trust_context=context
        )
        
        assert breakdown.request > 0
        assert breakdown.final_score >= 15
    
    def test_category_caps_enforced(self, test_db: Session):
        """Test that category score caps are enforced."""
        scorer = TrustScorer()
        graph = TrustGraph(test_db)
        
        # High-risk evidence
        evidence = create_minimal_evidence(
            money_amount=1000000.0,
            credential_type="password",
            urgency=True,
            secrecy=True,
            claimed_name="Suspicious Caller"
        )
        context = graph.get_trust_context("+919999999999", "Different Name", "relative")
        
        breakdown = scorer.calculate_score(
            evidence=evidence,
            channel_status=context["channel_status"],
            trust_context=context
        )
        
        # Verify caps
        assert breakdown.identity <= 25
        assert breakdown.request <= 30
        assert breakdown.behavior <= 20
        assert breakdown.channel <= 15
        assert breakdown.voice <= 10
        assert breakdown.final_score <= 100


@pytest.mark.skip(reason="Legacy tests for outdated API - see test_trust_engine_simple.py for current coverage")
class TestTrustJudge:
    """Test Trust Judge final assessment."""
    
    def test_verified_contact_low_risk(self, test_db: Session):
        """Test that verified contact with normal call is LOW risk."""
        judge = TrustJudge()
        graph = TrustGraph(test_db)
        
        # Add verified contact
        graph.add_contact("+919876543210", "Rajesh Kumar", "father", True)
        
        evidence = create_minimal_evidence(claimed_name="Rajesh Kumar")
        
        assessment = judge.evaluate(
            call_id="test-001",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919876543210"
        )
        
        assert assessment.risk_level == RiskLevel.LOW.value
        assert assessment.score < 25
        assert assessment.channel_status == ChannelStatus.VERIFIED.value
    
    def test_otp_request_critical_risk(self, test_db: Session):
        """Test that OTP request triggers CRITICAL risk."""
        judge = TrustJudge()
        graph = TrustGraph(test_db)
        
        evidence = create_minimal_evidence(
            credential_type="otp",
            urgency=True,
            claimed_name="Bank Officer",
            claimed_type="organization"
        )
        
        assessment = judge.evaluate(
            call_id="test-002",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        assert assessment.risk_level == RiskLevel.CRITICAL.value
        assert assessment.score >= 75
        assert len(assessment.applied_floors) > 0
    
    def test_contact_mismatch_high_risk(self, test_db: Session):
        """Test that contact mismatch with money request is HIGH/CRITICAL risk."""
        judge = TrustJudge()
        graph = TrustGraph(test_db)
        
        # Add verified contact
        graph.add_contact("+919876543210", "Rajesh Kumar", "father", True)
        
        # Evidence claims different name (mismatch)
        evidence = create_minimal_evidence(
            money_amount=150000.0,
            urgency=True,
            secrecy=True,
            claimed_name="Suresh Sharma"  # Mismatch
        )
        
        assessment = judge.evaluate(
            call_id="test-003",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919876543210"
        )
        
        assert assessment.risk_level in [RiskLevel.HIGH.value, RiskLevel.CRITICAL.value]
        assert assessment.score >= 50
        assert assessment.channel_status == ChannelStatus.MISMATCH.value
    
    def test_assessment_includes_verification(self, test_db: Session):
        """Test that assessment includes verification recommendations."""
        judge = TrustJudge()
        graph = TrustGraph(test_db)
        
        evidence = create_minimal_evidence(money_amount=50000.0)
        
        assessment = judge.evaluate(
            call_id="test-004",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        assert assessment.verification_method is not None
        assert assessment.verification_details is not None
        assert "action" in assessment.verification_details
        assert "recommendation" in assessment.verification_details
    
    def test_assessment_includes_audit_hash(self, test_db: Session):
        """Test that audit hash is generated."""
        judge = TrustJudge()
        graph = TrustGraph(test_db)
        
        evidence = create_minimal_evidence()
        
        assessment = judge.evaluate(
            call_id="test-005",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919876543210"
        )
        
        assert assessment.audit_hash is not None
        assert len(assessment.audit_hash) == 64  # SHA-256


@pytest.mark.skip(reason="Legacy tests for outdated API - see test_trust_engine_simple.py for current coverage")
class TestEndToEndIntegration:
    """Test complete flow from evidence to final assessment."""
    
    def test_complete_flow_verified_contact(self, test_db: Session):
        """Test complete flow for verified contact."""
        # Setup
        graph = TrustGraph(test_db)
        graph.add_contact("+919876543210", "Rajesh Kumar", "father", True)
        
        judge = TrustJudge()
        evidence = create_minimal_evidence(claimed_name="Rajesh Kumar")
        
        # Execute
        assessment = judge.evaluate(
            call_id="integration-001",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919876543210"
        )
        
        # Verify
        assert assessment.risk_level == RiskLevel.LOW.value
        assert assessment.score < 25
        assert assessment.channel_status == ChannelStatus.VERIFIED.value
        assert assessment.verification_method == "normal_caution"
    
    def test_complete_flow_otp_scam(self, test_db: Session):
        """Test complete flow for OTP scam scenario."""
        # Setup
        graph = TrustGraph(test_db)
        judge = TrustJudge()
        
        evidence = create_minimal_evidence(
            credential_type="otp",
            urgency=True,
            claimed_name="Bank Representative",
            claimed_type="organization"
        )
        
        # Execute
        assessment = judge.evaluate(
            call_id="integration-002",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Verify
        assert assessment.risk_level == RiskLevel.CRITICAL.value
        assert assessment.score >= 75
        assert assessment.channel_status == ChannelStatus.UNKNOWN.value
        assert len(assessment.applied_floors) > 0
        assert "Do not proceed" in assessment.verification_details.get("action", "")
    
    def test_complete_flow_impersonation_scam(self, test_db: Session):
        """Test complete flow for impersonation scam."""
        # Setup - add real contact
        graph = TrustGraph(test_db)
        graph.add_contact("+919876543210", "Rajesh Kumar", "father", True)
        
        judge = TrustJudge()
        
        # Evidence claims to be father but with different name (impersonation)
        evidence = create_minimal_evidence(
            money_amount=150000.0,
            urgency=True,
            secrecy=True,
            claimed_name="Suresh Sharma"
        )
        
        # Execute
        assessment = judge.evaluate(
            call_id="integration-003",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919876543210"
        )
        
        # Verify
        assert assessment.risk_level in [RiskLevel.HIGH.value, RiskLevel.CRITICAL.value]
        assert assessment.score >= 50
        assert assessment.channel_status == ChannelStatus.MISMATCH.value
        assert len(assessment.reasons) > 0
        assert any("mismatch" in reason.lower() for reason in assessment.reasons)
