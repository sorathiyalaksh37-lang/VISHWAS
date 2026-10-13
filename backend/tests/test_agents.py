"""
Comprehensive test suite for Phase 3 Agentic AI components.

Tests Fraud Agent, Skeptic Agent, and Agent Orchestrator with mocked LLM calls.
All tests use mock providers - no real API calls or charges.
"""

import pytest
import asyncio
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock, patch

from app.llm.provider import MockLLMProvider, LLMProvider
from app.agents.fraud_agent import FraudAgent
from app.agents.skeptic_agent import SkepticAgent
from app.agents.orchestrator import AgentOrchestrator
from app.schemas.agent import (
    AgentEvidencePackage,
    AgentFinding,
    AgentChallenge,
    FraudAgentResponse,
    SkepticAgentResponse,
    AgentAnalysisResult
)
from app.schemas.evidence import EvidenceExtraction, ClaimsEvidence, RequestEvidence, BehaviorEvidence


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_llm():
    """Mock LLM provider for testing."""
    return MockLLMProvider()


@pytest.fixture
def fraud_agent(mock_llm):
    """Create Fraud Agent with mock LLM."""
    return FraudAgent(mock_llm)


@pytest.fixture
def skeptic_agent(mock_llm):
    """Create Skeptic Agent with mock LLM."""
    return SkepticAgent(mock_llm)


@pytest.fixture
def minimal_evidence_package() -> AgentEvidencePackage:
    """Create minimal evidence package for testing."""
    return AgentEvidencePackage(
        call_id="test-call-001",
        evidence_summary={
            "claims": {
                "claims": [
                    {
                        "id": "claim_0",
                        "type": "relative",
                        "value": "grandson",
                        "confidence": 0.85,
                        "quote": "This is your grandson"
                    }
                ]
            },
            "requests": {
                "money_requests": [
                    {
                        "id": "money_0",
                        "amount": 50000.0,
                        "currency": "INR",
                        "confidence": 0.90
                    }
                ]
            },
            "behavior": {
                "urgency": {"detected": True, "severity": "high"}
            }
        },
        trust_context={
            "channel_status": "unverified",
            "contact_found": False
        },
        phase2_signals={
            "risk_score": 75,
            "risk_level": "high",
            "category_scores": {
                "identity": 20,
                "request": 25,
                "behavior": 15,
                "channel": 10,
                "voice": 5
            },
            "fired_rules": ["money_request_unverified", "urgency_detected"],
            "applied_floors": []
        },
        evidence_quality=0.85,
        warnings=[]
    )


@pytest.fixture
def benign_evidence_package() -> AgentEvidencePackage:
    """Evidence package for benign conversation."""
    return AgentEvidencePackage(
        call_id="test-call-benign",
        evidence_summary={
            "claims": {
                "claims": [
                    {
                        "id": "claim_0",
                        "type": "relative",
                        "value": "son",
                        "confidence": 0.90,
                        "quote": "Hi Mom, it's me"
                    }
                ]
            }
        },
        trust_context={
            "channel_status": "verified",
            "contact_found": True,
            "verified_name": "Raj Kumar",
            "verified_relationship": "son"
        },
        phase2_signals={
            "risk_score": 15,
            "risk_level": "minimal",
            "category_scores": {
                "identity": 0,
                "request": 0,
                "behavior": 0,
                "channel": 0,
                "voice": 0
            },
            "fired_rules": [],
            "applied_floors": []
        },
        evidence_quality=0.95,
        warnings=[]
    )


# ============================================================================
# Fraud Agent Tests
# ============================================================================

class TestFraudAgent:
    """Test Fraud Agent functionality."""

    @pytest.mark.asyncio
    async def test_fraud_agent_initialization(self, mock_llm):
        """Test Fraud Agent initializes correctly."""
        agent = FraudAgent(mock_llm)
        assert agent.llm == mock_llm

    @pytest.mark.asyncio
    async def test_fraud_agent_valid_findings(self, fraud_agent, minimal_evidence_package):
        """Test Fraud Agent returns valid structured findings."""
        # Mock LLM to return valid findings
        mock_response = FraudAgentResponse(
            findings=[
                AgentFinding(
                    finding_id="finding_1",
                    finding_type="identity_concern",
                    evidence_ids=["claim_0"],
                    reason="Unverified caller claiming family relationship",
                    confidence=0.75,
                    limitations=["No verified contact data"],
                    requires_review=True
                ),
                AgentFinding(
                    finding_id="finding_2",
                    finding_type="sensitive_request",
                    evidence_ids=["money_0"],
                    reason="Large money request combined with urgency",
                    confidence=0.85,
                    limitations=[],
                    requires_review=True
                )
            ],
            processing_time_seconds=1.0,
            model_info={"model": "mock"}
        )

        fraud_agent.llm.generate_structured = AsyncMock(return_value=mock_response)

        result = await fraud_agent.analyze(minimal_evidence_package)

        assert isinstance(result, FraudAgentResponse)
        assert len(result.findings) == 2
        assert result.findings[0].finding_id == "finding_1"
        assert result.findings[0].finding_type == "identity_concern"
        assert "claim_0" in result.findings[0].evidence_ids

    @pytest.mark.asyncio
    async def test_fraud_agent_benign_conversation(self, fraud_agent, benign_evidence_package):
        """Test Fraud Agent handles benign conversations (no findings)."""
        mock_response = FraudAgentResponse(
            findings=[],
            processing_time_seconds=0.8,
            model_info={"model": "mock"}
        )

        fraud_agent.llm.generate_structured = AsyncMock(return_value=mock_response)

        result = await fraud_agent.analyze(benign_evidence_package)

        assert isinstance(result, FraudAgentResponse)
        assert len(result.findings) == 0

    @pytest.mark.asyncio
    async def test_fraud_agent_invalid_evidence_ids(self, fraud_agent, minimal_evidence_package):
        """Test Fraud Agent rejects findings with invalid evidence IDs."""
        # Mock LLM returns finding with fabricated evidence ID
        mock_response = FraudAgentResponse(
            findings=[
                AgentFinding(
                    finding_id="finding_1",
                    finding_type="identity_concern",
                    evidence_ids=["claim_0"],  # Valid
                    reason="Valid finding",
                    confidence=0.75
                ),
                AgentFinding(
                    finding_id="finding_2",
                    finding_type="voice_indicator",
                    evidence_ids=["voice_999"],  # INVALID - does not exist
                    reason="Fabricated evidence",
                    confidence=0.60
                )
            ],
            processing_time_seconds=1.0,
            model_info={"model": "mock"}
        )

        fraud_agent.llm.generate_structured = AsyncMock(return_value=mock_response)

        result = await fraud_agent.analyze(minimal_evidence_package)

        # Should only have 1 valid finding, invalid one rejected
        assert len(result.findings) == 1
        assert result.findings[0].finding_id == "finding_1"

    @pytest.mark.asyncio
    async def test_fraud_agent_duplicate_findings(self, fraud_agent, minimal_evidence_package):
        """Test Fraud Agent deduplicates identical findings."""
        mock_response = FraudAgentResponse(
            findings=[
                AgentFinding(
                    finding_id="finding_1",
                    finding_type="identity_concern",
                    evidence_ids=["claim_0"],
                    reason="First version",
                    confidence=0.75
                ),
                AgentFinding(
                    finding_id="finding_2",
                    finding_type="identity_concern",
                    evidence_ids=["claim_0"],  # Same type + evidence = duplicate
                    reason="Second version (duplicate)",
                    confidence=0.80
                )
            ],
            processing_time_seconds=1.0,
            model_info={"model": "mock"}
        )

        fraud_agent.llm.generate_structured = AsyncMock(return_value=mock_response)

        result = await fraud_agent.analyze(minimal_evidence_package)

        # Should deduplicate to 1 finding
        assert len(result.findings) == 1

    @pytest.mark.asyncio
    async def test_fraud_agent_timeout(self, fraud_agent, minimal_evidence_package):
        """Test Fraud Agent handles timeout gracefully."""
        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(10)
            return FraudAgentResponse(findings=[], processing_time_seconds=10.0, model_info={})

        fraud_agent.llm.generate_structured = slow_generate

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                fraud_agent.analyze(minimal_evidence_package, timeout=0.1),
                timeout=0.2
            )

    @pytest.mark.asyncio
    async def test_fraud_agent_provider_error(self, fraud_agent, minimal_evidence_package):
        """Test Fraud Agent propagates provider errors."""
        fraud_agent.llm.generate_structured = AsyncMock(
            side_effect=RuntimeError("Provider connection failed")
        )

        with pytest.raises(RuntimeError, match="Provider connection failed"):
            await fraud_agent.analyze(minimal_evidence_package)

    @pytest.mark.asyncio
    async def test_fraud_agent_missing_voice_evidence(self, fraud_agent):
        """Test Fraud Agent handles missing voice evidence correctly."""
        package = AgentEvidencePackage(
            call_id="test-no-voice",
            evidence_summary={
                "claims": {
                    "claims": [{"id": "claim_0", "type": "relative", "value": "son", "confidence": 0.8, "quote": "Hi"}]
                }
            },
            trust_context={"channel_status": "unverified", "contact_found": False},
            phase2_signals={"risk_score": 50, "risk_level": "medium", "category_scores": {}, "fired_rules": [], "applied_floors": []},
            evidence_quality=0.7,
            warnings=["Voice analysis unavailable"]
        )

        # Should not crash, should include warning about missing voice
        mock_response = FraudAgentResponse(
            findings=[],
            processing_time_seconds=0.5,
            model_info={"model": "mock"}
        )

        fraud_agent.llm.generate_structured = AsyncMock(return_value=mock_response)

        result = await fraud_agent.analyze(package)
        assert isinstance(result, FraudAgentResponse)


# ============================================================================
# Skeptic Agent Tests
# ============================================================================

class TestSkepticAgent:
    """Test Skeptic Agent functionality."""

    @pytest.mark.asyncio
    async def test_skeptic_agent_initialization(self, mock_llm):
        """Test Skeptic Agent initializes correctly."""
        agent = SkepticAgent(mock_llm)
        assert agent.llm == mock_llm

    @pytest.mark.asyncio
    async def test_skeptic_agent_valid_challenges(self, skeptic_agent, minimal_evidence_package):
        """Test Skeptic Agent returns valid challenges."""
        fraud_findings = [
            AgentFinding(
                finding_id="finding_1",
                finding_type="identity_concern",
                evidence_ids=["claim_0"],
                reason="Unknown caller claiming relationship",
                confidence=0.75
            )
        ]

        mock_response = SkepticAgentResponse(
            challenges=[
                AgentChallenge(
                    challenge_id="challenge_1",
                    finding_id="finding_1",
                    challenge_type="missing_context",
                    explanation="Unknown caller is not proof of fraud",
                    missing_evidence=["Verified contact database"],
                    verification_suggestion="Check contact records"
                )
            ],
            processing_time_seconds=0.9,
            model_info={"model": "mock"}
        )

        skeptic_agent.llm.generate_structured = AsyncMock(return_value=mock_response)

        result = await skeptic_agent.analyze(minimal_evidence_package, fraud_findings)

        assert isinstance(result, SkepticAgentResponse)
        assert len(result.challenges) == 1
        assert result.challenges[0].challenge_type == "missing_context"

    @pytest.mark.asyncio
    async def test_skeptic_agent_supported_finding(self, skeptic_agent, minimal_evidence_package):
        """Test Skeptic Agent can mark findings as supported."""
        fraud_findings = [
            AgentFinding(
                finding_id="finding_1",
                finding_type="sensitive_request",
                evidence_ids=["money_0"],
                reason="Money request with urgency and unverified channel",
                confidence=0.90
            )
        ]

        mock_response = SkepticAgentResponse(
            challenges=[
                AgentChallenge(
                    challenge_id="challenge_1",
                    finding_id="finding_1",
                    challenge_type="supported",
                    explanation="Evidence strongly supports this finding",
                    missing_evidence=[],
                    verification_suggestion=None
                )
            ],
            processing_time_seconds=0.7,
            model_info={"model": "mock"}
        )

        skeptic_agent.llm.generate_structured = AsyncMock(return_value=mock_response)

        result = await skeptic_agent.analyze(minimal_evidence_package, fraud_findings)

        assert len(result.challenges) == 1
        assert result.challenges[0].challenge_type == "supported"

    @pytest.mark.asyncio
    async def test_skeptic_agent_invalid_finding_reference(self, skeptic_agent, minimal_evidence_package):
        """Test Skeptic Agent rejects challenges referencing non-existent findings."""
        fraud_findings = [
            AgentFinding(
                finding_id="finding_1",
                finding_type="identity_concern",
                evidence_ids=["claim_0"],
                reason="Valid finding",
                confidence=0.75
            )
        ]

        mock_response = SkepticAgentResponse(
            challenges=[
                AgentChallenge(
                    challenge_id="challenge_1",
                    finding_id="finding_1",  # Valid reference
                    challenge_type="missing_context",
                    explanation="Valid challenge"
                ),
                AgentChallenge(
                    challenge_id="challenge_2",
                    finding_id="finding_999",  # INVALID - finding does not exist
                    challenge_type="unsupported_evidence",
                    explanation="Challenge to non-existent finding"
                )
            ],
            processing_time_seconds=0.8,
            model_info={"model": "mock"}
        )

        skeptic_agent.llm.generate_structured = AsyncMock(return_value=mock_response)

        result = await skeptic_agent.analyze(minimal_evidence_package, fraud_findings)

        # Should only have 1 valid challenge
        assert len(result.challenges) == 1
        assert result.challenges[0].finding_id == "finding_1"

    @pytest.mark.asyncio
    async def test_skeptic_agent_no_findings_to_challenge(self, skeptic_agent, minimal_evidence_package):
        """Test Skeptic Agent handles empty findings list."""
        mock_response = SkepticAgentResponse(
            challenges=[],
            processing_time_seconds=0.3,
            model_info={"model": "mock"}
        )

        skeptic_agent.llm.generate_structured = AsyncMock(return_value=mock_response)

        result = await skeptic_agent.analyze(minimal_evidence_package, [])

        assert len(result.challenges) == 0

    @pytest.mark.asyncio
    async def test_skeptic_agent_timeout(self, skeptic_agent, minimal_evidence_package):
        """Test Skeptic Agent handles timeout gracefully."""
        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(10)
            return SkepticAgentResponse(challenges=[], processing_time_seconds=10.0, model_info={})

        skeptic_agent.llm.generate_structured = slow_generate

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                skeptic_agent.analyze(minimal_evidence_package, [], timeout=0.1),
                timeout=0.2
            )

    @pytest.mark.asyncio
    async def test_skeptic_agent_provider_error(self, skeptic_agent, minimal_evidence_package):
        """Test Skeptic Agent propagates provider errors."""
        skeptic_agent.llm.generate_structured = AsyncMock(
            side_effect=ValueError("Invalid schema")
        )

        with pytest.raises(ValueError, match="Invalid schema"):
            await skeptic_agent.analyze(minimal_evidence_package, [])


# ============================================================================
# Agent Orchestrator Tests
# ============================================================================

class TestAgentOrchestrator:
    """Test Agent Orchestrator functionality."""

    @pytest.mark.asyncio
    async def test_orchestrator_tier2_disabled(self):
        """Test orchestrator returns disabled status when Tier 2 disabled."""
        with patch('app.llm.provider.get_llm_provider', return_value=None):
            orchestrator = AgentOrchestrator()

            result = await orchestrator.analyze(
                call_id="test-001",
                evidence=Mock(),
                trust_context={},
                score_breakdown=Mock(
                    final_score=50,
                    risk_level=Mock(value="medium"),
                    identity=10,
                    request=15,
                    behavior=10,
                    channel=10,
                    voice=5,
                    fired_rules=[],
                    applied_floors=[]
                )
            )

            assert result.tier2_status == "disabled"
            assert len(result.warnings) > 0
            assert len(result.fraud_findings) == 0
            assert len(result.skeptic_challenges) == 0

    @pytest.mark.asyncio
    async def test_orchestrator_successful_execution(self, minimal_evidence_package):
        """Test orchestrator successfully coordinates both agents."""
        # Patch at the module where it's used, not where it's defined
        with patch('app.agents.orchestrator.get_llm_provider') as mock_get_provider:
            mock_provider = MockLLMProvider()
            mock_get_provider.return_value = mock_provider

            orchestrator = AgentOrchestrator()

            # Verify agents were created
            assert orchestrator.fraud_agent is not None
            assert orchestrator.skeptic_agent is not None

            # Mock agent responses
            fraud_response = FraudAgentResponse(
                findings=[
                    AgentFinding(
                        finding_id="f1",
                        finding_type="identity_concern",
                        evidence_ids=["claim_0"],
                        reason="Test finding"
                    )
                ],
                processing_time_seconds=1.0,
                model_info={"model": "mock"}
            )

            skeptic_response = SkepticAgentResponse(
                challenges=[
                    AgentChallenge(
                        challenge_id="c1",
                        finding_id="f1",
                        challenge_type="missing_context",
                        explanation="Test challenge"
                    )
                ],
                processing_time_seconds=0.8,
                model_info={"model": "mock"}
            )

            # Mock agent analyze methods
            orchestrator.fraud_agent.analyze = AsyncMock(return_value=fraud_response)
            orchestrator.skeptic_agent.analyze = AsyncMock(return_value=skeptic_response)

            # Create minimal evidence extraction
            from app.schemas.evidence import (
                EvidenceExtraction, ClaimsEvidence, RequestEvidence,
                BehaviorEvidence, UrgencyEvidence, SecrecyEvidence, EmotionalPressureEvidence
            )

            evidence = EvidenceExtraction(
                call_id="test-001",
                claims=ClaimsEvidence(claims=[], primary_claim=None, primary_claim_type=None),
                requests=RequestEvidence(
                    money_requests=[],
                    credential_requests=[],
                    action_requests=[],
                    max_money_amount=None,
                    has_money=False,
                    has_credential=False,
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
                extraction_warnings=[]
            )

            from app.trust_engine.scoring import ScoreBreakdown, RiskLevel
            score_breakdown = ScoreBreakdown(
                final_score=50,
                # risk_level is a property
                identity=10,
                request=15,
                behavior=10,
                channel=10,
                voice=5,
                fired_rules=[],
                applied_floors=[]
            )

            result = await orchestrator.analyze(
                call_id="test-001",
                evidence=evidence,
                trust_context={"channel_status": "unverified", "contact_found": False},
                score_breakdown=score_breakdown
            )

            assert result.tier2_status == "completed"
            assert len(result.fraud_findings) == 1
            assert len(result.skeptic_challenges) == 1
            assert len(result.warnings) == 0

    @pytest.mark.asyncio
    async def test_orchestrator_fraud_agent_timeout(self):
        """Test orchestrator handles Fraud Agent timeout."""
        with patch('app.agents.orchestrator.get_llm_provider') as mock_get_provider:
            mock_provider = MockLLMProvider()
            mock_get_provider.return_value = mock_provider

            orchestrator = AgentOrchestrator()

            # Mock Fraud Agent to timeout
            async def timeout_fraud(*args, **kwargs):
                await asyncio.sleep(100)

            orchestrator.fraud_agent.analyze = timeout_fraud

            from app.schemas.evidence import (
                EvidenceExtraction, ClaimsEvidence, RequestEvidence,
                BehaviorEvidence, UrgencyEvidence, SecrecyEvidence, EmotionalPressureEvidence
            )
            from app.trust_engine.scoring import ScoreBreakdown, RiskLevel

            evidence = EvidenceExtraction(
                call_id="test-timeout",
                claims=ClaimsEvidence(claims=[], primary_claim=None, primary_claim_type=None),
                requests=RequestEvidence(
                    money_requests=[], credential_requests=[], action_requests=[],
                    max_money_amount=None, has_money=False, has_credential=False, has_action=False
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
                extraction_warnings=[]
            )

            score_breakdown = ScoreBreakdown(
                final_score=50, # risk_level is a property
                identity=10, request=15, behavior=10, channel=10, voice=5,
                fired_rules=[], applied_floors=[]
            )

            result = await orchestrator.analyze(
                call_id="test-timeout",
                evidence=evidence,
                trust_context={},
                score_breakdown=score_breakdown,
                timeout_per_agent=0.1
            )

            assert result.tier2_status == "fraud_failed"
            assert "failed" in result.warnings[0].lower() or "timed out" in result.warnings[0].lower()

    @pytest.mark.asyncio
    async def test_orchestrator_skeptic_agent_failure(self):
        """Test orchestrator handles Skeptic Agent failure gracefully."""
        with patch('app.agents.orchestrator.get_llm_provider') as mock_get_provider:
            mock_provider = MockLLMProvider()
            mock_get_provider.return_value = mock_provider

            orchestrator = AgentOrchestrator()

            # Mock Fraud Agent succeeds
            fraud_response = FraudAgentResponse(
                findings=[],
                processing_time_seconds=0.5,
                model_info={"model": "mock"}
            )
            orchestrator.fraud_agent.analyze = AsyncMock(return_value=fraud_response)

            # Mock Skeptic Agent fails
            orchestrator.skeptic_agent.analyze = AsyncMock(
                side_effect=RuntimeError("Skeptic failed")
            )

            from app.schemas.evidence import (
                EvidenceExtraction, ClaimsEvidence, RequestEvidence,
                BehaviorEvidence, UrgencyEvidence, SecrecyEvidence, EmotionalPressureEvidence
            )
            from app.trust_engine.scoring import ScoreBreakdown, RiskLevel

            evidence = EvidenceExtraction(
                call_id="test-skeptic-fail-2",
                claims=ClaimsEvidence(claims=[], primary_claim=None, primary_claim_type=None),
                requests=RequestEvidence(
                    money_requests=[], credential_requests=[], action_requests=[],
                    max_money_amount=None, has_money=False, has_credential=False, has_action=False
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
                extraction_warnings=[]
            )

            score_breakdown = ScoreBreakdown(
                final_score=50, # risk_level is a property
                identity=10, request=15, behavior=10, channel=10, voice=5,
                fired_rules=[], applied_floors=[]
            )

            result = await orchestrator.analyze(
                call_id="test-skeptic-fail",
                evidence=evidence,
                trust_context={},
                score_breakdown=score_breakdown
            )

            assert result.tier2_status == "skeptic_failed"
            assert len(result.fraud_findings) == 0  # Fraud succeeded
            assert len(result.skeptic_challenges) == 0  # Skeptic failed
            assert "Skeptic" in result.warnings[0]


# ============================================================================
# Integration Tests
# ============================================================================

class TestAgentIntegration:
    """Integration tests for agent pipeline."""

    @pytest.mark.asyncio
    async def test_end_to_end_agent_pipeline(self):
        """Test complete agent pipeline from evidence to final result."""
        with patch('app.agents.orchestrator.get_llm_provider') as mock_get_provider:
            mock_provider = MockLLMProvider()
            mock_get_provider.return_value = mock_provider

            orchestrator = AgentOrchestrator()

            # Create complete evidence package
            from app.schemas.evidence import (
                EvidenceExtraction, ClaimsEvidence, RequestEvidence, BehaviorEvidence,
                ClaimEvidence, MoneyRequest, UrgencyEvidence, SecrecyEvidence, EmotionalPressureEvidence
            )
            from app.trust_engine.scoring import ScoreBreakdown, RiskLevel

            claim = ClaimEvidence(
                type="relative",
                value="son",
                confidence=0.85,
                quote="This is your son calling",
                t=1.5
            )

            money_req = MoneyRequest(
                amount=100000.0,
                currency="INR",
                confidence=0.90,
                quote="Please send 1 lakh rupees",
                t=5.2
            )

            evidence = EvidenceExtraction(
                call_id="test-e2e-complete",
                claims=ClaimsEvidence(
                    claims=[claim],
                    primary_claim=claim,
                    primary_claim_type="relative"
                ),
                requests=RequestEvidence(
                    money_requests=[money_req],
                    credential_requests=[],
                    action_requests=[],
                    max_money_amount=100000.0,
                    has_money=True,
                    has_credential=False,
                    has_action=False
                ),
                behavior=BehaviorEvidence(
                    urgency=UrgencyEvidence(detected=True, severity="high", indicators=["immediately", "right now"]),
                    secrecy=SecrecyEvidence(detected=True, indicators=["don't tell anyone"]),
                    emotional_pressure=EmotionalPressureEvidence(detected=False, pressure_types=[], indicators=[]),
                    call_timing=None
                ),
                voice=None,
                evidence_quality_score=0.88,
                transcript_segments_analyzed=10,
                extraction_warnings=[]
            )

            score_breakdown = ScoreBreakdown(
                final_score=85,
                # risk_level is a property
                identity=25,
                request=30,
                behavior=20,
                channel=10,
                voice=0,
                fired_rules=["money_request_unverified", "urgency_detected", "secrecy_detected"],
                applied_floors=[]
            )

            # Mock responses
            fraud_response = FraudAgentResponse(
                findings=[
                    AgentFinding(
                        finding_id="f1",
                        finding_type="sensitive_request",
                        evidence_ids=["money_0"],
                        reason="Large money request with urgency and secrecy",
                        confidence=0.90,
                        requires_review=True
                    )
                ],
                processing_time_seconds=1.2,
                model_info={"model": "mock"}
            )

            skeptic_response = SkepticAgentResponse(
                challenges=[
                    AgentChallenge(
                        challenge_id="c1",
                        finding_id="f1",
                        challenge_type="supported",
                        explanation="Strong evidence supports this finding"
                    )
                ],
                processing_time_seconds=0.9,
                model_info={"model": "mock"}
            )

            orchestrator.fraud_agent.analyze = AsyncMock(return_value=fraud_response)
            orchestrator.skeptic_agent.analyze = AsyncMock(return_value=skeptic_response)

            result = await orchestrator.analyze(
                call_id="test-e2e",
                evidence=evidence,
                trust_context={
                    "channel_status": "unverified",
                    "contact_found": False
                },
                score_breakdown=score_breakdown
            )

            # Verify complete result
            assert result.tier2_status == "completed"
            assert len(result.fraud_findings) == 1
            assert len(result.skeptic_challenges) == 1
            assert result.fraud_findings[0].requires_review is True
            assert result.skeptic_challenges[0].challenge_type == "supported"
            assert "fraud_agent_findings" in result.agent_metadata
            assert "skeptic_agent_challenges" in result.agent_metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
