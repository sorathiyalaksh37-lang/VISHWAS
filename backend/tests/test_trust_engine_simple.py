"""
Simplified test suite for Phase 2 Trust Engine - verifies core functionality works.
"""

import pytest
from sqlalchemy.orm import Session

from app.trust_engine.trust_graph import TrustGraph, ChannelStatus
from app.trust_engine.scoring import TrustScorer, RiskLevel
from app.trust_engine.judge import TrustJudge
from app.schemas.evidence import (
    EvidenceExtraction, ClaimsEvidence, RequestEvidence, BehaviorEvidence, 
    ClaimEvidence, MoneyRequest, CredentialRequest, UrgencyEvidence,
    SecrecyEvidence, EmotionalPressureEvidence
)


def create_test_evidence(
    money_amount=None,
    credential_type=None, 
    claimed_name=None
):
    """Create minimal evidence for testing."""
    evidence = EvidenceExtraction(
        call_id="test-call",
        claims=ClaimsEvidence(claims=[], primary_claim=None),
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
            urgency=UrgencyEvidence(detected=False, severity="low", indicators=[]),
            secrecy=SecrecyEvidence(detected=False, indicators=[]),
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
        evidence.claims.claims = [ClaimEvidence(
            type="relative",
            value=claimed_name,
            quote=f"This is {claimed_name} calling",
            t=1.0,
            confidence=0.95
        )]
        evidence.claims.primary_claim = evidence.claims.claims[0]
    
    if money_amount:
        evidence.requests.money_requests = [MoneyRequest(
            amount=money_amount, 
            urgency_level="normal",
            quote="Please send money",
            t=1.0,
            confidence=0.95
        )]
    
    if credential_type:
        evidence.requests.credential_requests = [CredentialRequest(
            type=credential_type, 
            quote=f"Please provide your {credential_type.upper()}",
            t=1.5,
            confidence=0.95
        )]
    
    return evidence


class TestTrustGraphBasic:
    """Basic Trust Graph tests."""
    
    def test_add_and_retrieve_contact(self, test_db: Session):
        """Test adding a contact and retrieving it."""
        graph = TrustGraph(test_db)
        
        contact = graph.add_contact(
            name="Rajesh Kumar",
            relation="father",
            phone_numbers=["+919876543210"]
        )
        
        assert contact.name == "Rajesh Kumar"
        assert contact.relation == "father"
        
        # Retrieve by name
        retrieved = graph.get_contact_by_name("Rajesh Kumar")
        assert retrieved is not None
        assert retrieved.name == "Rajesh Kumar"
    
    def test_channel_status_verified(self, test_db: Session):
        """Test verified channel status."""
        graph = TrustGraph(test_db)
        
        graph.add_contact(
            name="Rajesh Kumar",
            relation="father",
            phone_numbers=["+919876543210"]
        )
        
        status, context = graph.check_channel_status(
            caller_number="+919876543210",
            claimed_identity="Rajesh Kumar"
        )
        
        assert status == ChannelStatus.VERIFIED
        assert context["contact_found"] is True
        assert context["number_matches"] is True
    
    def test_channel_status_unknown(self, test_db: Session):
        """Test unknown channel status."""
        graph = TrustGraph(test_db)
        
        status, context = graph.check_channel_status(
            caller_number="+919999999999",
            claimed_identity="Unknown Person"
        )
        
        assert status == ChannelStatus.UNKNOWN
        assert context["contact_found"] is False


class TestEndToEndFlow:
    """Test complete end-to-end flow."""
    
    def test_verified_contact_low_risk(self, test_db: Session):
        """Test verified contact returns LOW risk."""
        # Setup
        graph = TrustGraph(test_db)
        graph.add_contact("Rajesh Kumar", "father", ["+919876543210"])
        
        judge = TrustJudge()
        evidence = create_test_evidence(claimed_name="Rajesh Kumar")
        
        # Execute
        assessment = judge.evaluate(
            call_id="test-001",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919876543210"
        )
        
        # Verify
        assert assessment.risk_level == RiskLevel.LOW.value
        assert assessment.score < 25
        assert assessment.channel_status == ChannelStatus.VERIFIED.value
        print(f"✓ Verified contact → LOW risk (score={assessment.score})")
    
    def test_otp_request_critical_risk(self, test_db: Session):
        """Test OTP request triggers CRITICAL risk."""
        # Setup
        graph = TrustGraph(test_db)
        judge = TrustJudge()
        evidence = create_test_evidence(credential_type="otp")
        
        # Execute
        assessment = judge.evaluate(
            call_id="test-002",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Verify
        assert assessment.risk_level == RiskLevel.CRITICAL.value
        assert assessment.score >= 75
        assert len(assessment.applied_floors) > 0
        print(f"✓ OTP request → CRITICAL risk (score={assessment.score}, floors={assessment.applied_floors})")
    
    def test_money_request_increases_risk(self, test_db: Session):
        """Test money request increases risk score."""
        # Setup
        graph = TrustGraph(test_db)
        judge = TrustJudge()
        evidence = create_test_evidence(money_amount=150000.0)
        
        # Execute
        assessment = judge.evaluate(
            call_id="test-003",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Verify
        assert assessment.score > 15  # Money request should increase score
        assert assessment.category_scores["request"] > 0
        print(f"✓ Money request → elevated risk (score={assessment.score})")
    
    def test_assessment_includes_verification(self, test_db: Session):
        """Test assessment includes verification recommendations."""
        # Setup
        graph = TrustGraph(test_db)
        judge = TrustJudge()
        evidence = create_test_evidence(money_amount=50000.0)
        
        # Execute
        assessment = judge.evaluate(
            call_id="test-004",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Verify
        assert assessment.verification_method is not None
        assert assessment.verification_details is not None
        assert "action" in assessment.verification_details
        print(f"✓ Assessment includes verification: {assessment.verification_method}")
    
    def test_deterministic_scoring(self, test_db: Session):
        """Test that same inputs produce same scores."""
        # Setup
        graph = TrustGraph(test_db)
        graph.add_contact("Test User", "friend", ["+919876543210"])
        
        judge = TrustJudge()
        evidence = create_test_evidence(claimed_name="Test User")
        
        # Execute twice
        assessment1 = judge.evaluate(
            call_id="test-005a",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919876543210"
        )
        
        assessment2 = judge.evaluate(
            call_id="test-005b",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919876543210"
        )
        
        # Verify determinism
        assert assessment1.score == assessment2.score
        assert assessment1.risk_level == assessment2.risk_level
        assert assessment1.category_scores == assessment2.category_scores
        print(f"✓ Deterministic scoring verified (score={assessment1.score})")
