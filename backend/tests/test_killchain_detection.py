"""
Task 2: Tests for killchain stage detection.

Tests ensure killchain stage is correctly detected based on evidence patterns.

Killchain stages:
1. RECONNAISSANCE - Information gathering, early conversation
2. IMPERSONATION - Identity claim established
3. MANIPULATION - Pressure tactics + identity claim
4. REQUEST - Sensitive request (money/credentials/action)

Testing scenarios:
1. No evidence -> RECONNAISSANCE
2. Identity claim only -> IMPERSONATION
3. Identity claim + pressure -> MANIPULATION
4. Identity claim + money request -> REQUEST
5. Credential request -> REQUEST (most dangerous)
"""
import pytest
from app.schemas.evidence import (
    EvidenceExtraction,
    ClaimsEvidence,
    ClaimEvidence,
    RequestEvidence,
    MoneyRequest,
    CredentialRequest,
    ActionRequest,
    BehaviorEvidence,
    UrgencyEvidence,
    SecrecyEvidence,
    EmotionalPressureEvidence,
)
from app.trust_engine.judge import TrustJudge
from app.trust_engine.trust_graph import TrustGraph
from datetime import datetime


def create_minimal_evidence(call_id: str, **kwargs) -> EvidenceExtraction:
    """Helper to create minimal evidence with overrides."""
    defaults = {
        "call_id": call_id,
        "claims": ClaimsEvidence(claims=[], primary_claim=None, claim_changes=0),
        "requests": RequestEvidence(),
        "behavior": BehaviorEvidence(
            urgency=UrgencyEvidence(detected=False, quotes=[], timestamps=[], severity="low", patterns_found=[]),
            secrecy=SecrecyEvidence(detected=False, quotes=[], timestamps=[], patterns_found=[]),
            emotional_pressure=EmotionalPressureEvidence(detected=False, quotes=[], timestamps=[], pressure_types=[]),
        ),
        "voice": None,
        "extraction_timestamp": datetime.utcnow(),
        "extractor_version": "test-1.0",
        "transcript_segments_analyzed": 5,
        "language_detected": "en",
        "tier1_signals": [],
        "tier2_used": False,
        "fallback_used": False,
        "extraction_warnings": [],
    }
    defaults.update(kwargs)
    return EvidenceExtraction(**defaults)


def test_killchain_reconnaissance_stage(test_db):
    """Test RECONNAISSANCE stage: minimal conversation, no claims or requests."""
    evidence = create_minimal_evidence(
        call_id="test-recon",
        transcript_segments_analyzed=3
    )
    
    judge = TrustJudge()
    trust_graph = TrustGraph(test_db)
    
    assessment = judge.evaluate(
        call_id="test-recon",
        evidence=evidence,
        trust_graph=trust_graph,
        caller_number=None
    )
    
    assert assessment.killchain_stage == "RECONNAISSANCE"


def test_killchain_impersonation_stage(test_db):
    """Test IMPERSONATION stage: identity claim without pressure."""
    evidence = create_minimal_evidence(
        call_id="test-impersonate",
        claims=ClaimsEvidence(
            claims=[
                ClaimEvidence(
                    type="relative",
                    value="mother",
                    quote="I am your mother",
                    t=3.0,
                    confidence=0.9,
                    language="en"
                )
            ],
            primary_claim=ClaimEvidence(
                type="relative",
                value="mother",
                quote="I am your mother",
                t=3.0,
                confidence=0.9,
                language="en"
            ),
            claim_changes=0
        )
    )
    
    judge = TrustJudge()
    trust_graph = TrustGraph(test_db)
    
    assessment = judge.evaluate(
        call_id="test-impersonate",
        evidence=evidence,
        trust_graph=trust_graph,
        caller_number=None
    )
    
    assert assessment.killchain_stage == "IMPERSONATION"


def test_killchain_manipulation_stage(test_db):
    """Test MANIPULATION stage: identity claim + pressure tactics."""
    evidence = create_minimal_evidence(
        call_id="test-manipulate",
        claims=ClaimsEvidence(
            claims=[
                ClaimEvidence(
                    type="relative",
                    value="mother",
                    quote="I am your mother",
                    t=3.0,
                    confidence=0.9,
                    language="en"
                )
            ],
            primary_claim=ClaimEvidence(
                type="relative",
                value="mother",
                quote="I am your mother",
                t=3.0,
                confidence=0.9,
                language="en"
            ),
            claim_changes=0
        ),
        behavior=BehaviorEvidence(
            urgency=UrgencyEvidence(
                detected=True,
                quotes=["This is urgent!"],
                timestamps=[5.0],
                severity="high",
                patterns_found=["time_limit"]
            ),
            secrecy=SecrecyEvidence(detected=False, quotes=[], timestamps=[], patterns_found=[]),
            emotional_pressure=EmotionalPressureEvidence(detected=False, quotes=[], timestamps=[], pressure_types=[]),
        )
    )
    
    judge = TrustJudge()
    trust_graph = TrustGraph(test_db)
    
    assessment = judge.evaluate(
        call_id="test-manipulate",
        evidence=evidence,
        trust_graph=trust_graph,
        caller_number=None
    )
    
    assert assessment.killchain_stage == "MANIPULATION"


def test_killchain_request_stage_money(test_db):
    """Test REQUEST stage: money request present."""
    evidence = create_minimal_evidence(
        call_id="test-request-money",
        claims=ClaimsEvidence(
            claims=[
                ClaimEvidence(
                    type="relative",
                    value="mother",
                    quote="I am your mother",
                    t=3.0,
                    confidence=0.9,
                    language="en"
                )
            ],
            primary_claim=ClaimEvidence(
                type="relative",
                value="mother",
                quote="I am your mother",
                t=3.0,
                confidence=0.9,
                language="en"
            ),
            claim_changes=0
        ),
        requests=RequestEvidence(
            money_requests=[
                MoneyRequest(
                    amount=50000.0,
                    currency="INR",
                    method="UPI",
                    quote="Send me 50,000 rupees",
                    t=10.0,
                    confidence=0.95
                )
            ]
        )
    )
    
    judge = TrustJudge()
    trust_graph = TrustGraph(test_db)
    
    assessment = judge.evaluate(
        call_id="test-request-money",
        evidence=evidence,
        trust_graph=trust_graph,
        caller_number=None
    )
    
    assert assessment.killchain_stage == "REQUEST"


def test_killchain_request_stage_credential(test_db):
    """Test REQUEST stage: credential request (most dangerous)."""
    evidence = create_minimal_evidence(
        call_id="test-request-cred",
        requests=RequestEvidence(
            credential_requests=[
                CredentialRequest(
                    type="otp",
                    quote="Tell me the OTP",
                    t=8.0,
                    confidence=0.98
                )
            ]
        )
    )
    
    judge = TrustJudge()
    trust_graph = TrustGraph(test_db)
    
    assessment = judge.evaluate(
        call_id="test-request-cred",
        evidence=evidence,
        trust_graph=trust_graph,
        caller_number=None
    )
    
    assert assessment.killchain_stage == "REQUEST"


def test_killchain_request_stage_action(test_db):
    """Test REQUEST stage: action request present."""
    evidence = create_minimal_evidence(
        call_id="test-request-action",
        requests=RequestEvidence(
            action_requests=[
                ActionRequest(
                    type="click_link",
                    detail="https://fake-bank.com",
                    quote="Click this link now",
                    t=12.0,
                    confidence=0.90
                )
            ]
        )
    )
    
    judge = TrustJudge()
    trust_graph = TrustGraph(test_db)
    
    assessment = judge.evaluate(
        call_id="test-request-action",
        evidence=evidence,
        trust_graph=trust_graph,
        caller_number=None
    )
    
    assert assessment.killchain_stage == "REQUEST"


def test_killchain_request_priority(test_db):
    """Test that REQUEST stage takes priority over MANIPULATION."""
    evidence = create_minimal_evidence(
        call_id="test-request-priority",
        claims=ClaimsEvidence(
            claims=[
                ClaimEvidence(
                    type="relative",
                    value="mother",
                    quote="I am your mother",
                    t=3.0,
                    confidence=0.9,
                    language="en"
                )
            ],
            primary_claim=ClaimEvidence(
                type="relative",
                value="mother",
                quote="I am your mother",
                t=3.0,
                confidence=0.9,
                language="en"
            ),
            claim_changes=0
        ),
        requests=RequestEvidence(
            money_requests=[
                MoneyRequest(
                    amount=10000.0,
                    currency="INR",
                    method="UPI",
                    quote="Send 10,000 urgently",
                    t=10.0,
                    confidence=0.95
                )
            ]
        ),
        behavior=BehaviorEvidence(
            urgency=UrgencyEvidence(
                detected=True,
                quotes=["Urgent!"],
                timestamps=[5.0],
                severity="high",
                patterns_found=["time_limit"]
            ),
            secrecy=SecrecyEvidence(detected=False, quotes=[], timestamps=[], patterns_found=[]),
            emotional_pressure=EmotionalPressureEvidence(detected=False, quotes=[], timestamps=[], pressure_types=[]),
        )
    )
    
    judge = TrustJudge()
    trust_graph = TrustGraph(test_db)
    
    assessment = judge.evaluate(
        call_id="test-request-priority",
        evidence=evidence,
        trust_graph=trust_graph,
        caller_number=None
    )
    
    # REQUEST should take priority over MANIPULATION even though both conditions are present
    assert assessment.killchain_stage == "REQUEST"


def test_killchain_empty_transcript(test_db):
    """Test killchain with empty transcript (no segments analyzed)."""
    evidence = create_minimal_evidence(
        call_id="test-empty",
        transcript_segments_analyzed=0
    )
    
    judge = TrustJudge()
    trust_graph = TrustGraph(test_db)
    
    assessment = judge.evaluate(
        call_id="test-empty",
        evidence=evidence,
        trust_graph=trust_graph,
        caller_number=None
    )
    
    # Empty transcript should return None
    assert assessment.killchain_stage is None
