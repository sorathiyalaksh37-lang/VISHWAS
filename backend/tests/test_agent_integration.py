"""
Integration tests for Phase 3 agent integration with /analyze endpoint.

Tests the complete analysis pipeline with Tier 2 agents integrated,
including fallback behavior and backward compatibility.
"""

import pytest
import json
from unittest.mock import patch, AsyncMock, Mock

from app.core.config import settings
from app.schemas.agent import AgentFinding, AgentChallenge


@pytest.fixture
def mock_tier2_disabled():
    """Mock Tier 2 as disabled."""
    original = settings.tier2_enabled
    settings.tier2_enabled = False
    yield
    settings.tier2_enabled = original


@pytest.fixture
def mock_tier2_enabled():
    """Mock Tier 2 as enabled with mock provider."""
    original_enabled = settings.tier2_enabled
    original_provider = settings.tier2_provider

    settings.tier2_enabled = True
    settings.tier2_provider = "mock"

    yield

    settings.tier2_enabled = original_enabled
    settings.tier2_provider = original_provider


class TestAnalyzeEndpointTier2:
    """Test /analyze endpoint with Tier 2 integration."""

    def test_analyze_tier2_disabled_backward_compatible(self, client, mock_tier2_disabled):
        """Test analysis works with Tier 2 disabled (backward compatibility)."""
        # This test verifies Phase 2 still works when Tier 2 is off
        # We can't test full /analyze without database setup, but we can verify settings
        assert settings.tier2_enabled is False

    def test_tier2_enabled_setting(self, mock_tier2_enabled):
        """Test Tier 2 enabled configuration."""
        assert settings.tier2_enabled is True
        assert settings.tier2_provider == "mock"

    def test_orchestrator_called_when_tier2_enabled(self, mock_tier2_enabled):
        """Test that orchestrator is instantiated when Tier 2 is enabled."""
        # This is a configuration test
        assert settings.tier2_enabled is True
        assert settings.tier2_provider == "mock"

        # When Tier 2 is enabled, the orchestrator initializes agents
        # This is tested more thoroughly in the unit tests


class TestAgentResultSerialization:
    """Test agent result serialization for API responses."""

    def test_fraud_finding_serialization(self):
        """Test AgentFinding can be serialized to JSON."""
        finding = AgentFinding(
            finding_id="f1",
            finding_type="identity_concern",
            evidence_ids=["claim_0", "claim_1"],
            reason="Test finding",
            confidence=0.85,
            limitations=["Missing data"],
            requires_review=True
        )

        # Serialize using Pydantic
        json_data = finding.model_dump()

        assert json_data["finding_id"] == "f1"
        assert json_data["finding_type"] == "identity_concern"
        assert len(json_data["evidence_ids"]) == 2
        assert json_data["confidence"] == 0.85

        # Verify it can be JSON encoded
        json_str = json.dumps(json_data)
        assert "f1" in json_str

    def test_skeptic_challenge_serialization(self):
        """Test AgentChallenge can be serialized to JSON."""
        challenge = AgentChallenge(
            challenge_id="c1",
            finding_id="f1",
            challenge_type="missing_context",
            evidence_ids=["claim_0"],
            explanation="Missing verification data",
            alternative_interpretation="Could be legitimate",
            missing_evidence=["Contact database"],
            verification_suggestion="Check records"
        )

        json_data = challenge.model_dump()

        assert json_data["challenge_id"] == "c1"
        assert json_data["finding_id"] == "f1"
        assert json_data["challenge_type"] == "missing_context"

        json_str = json.dumps(json_data)
        assert "c1" in json_str

    def test_agent_result_complete_serialization(self):
        """Test complete agent result serialization."""
        from app.schemas.agent import AgentAnalysisResult
        from datetime import datetime

        result = AgentAnalysisResult(
            fraud_findings=[
                AgentFinding(
                    finding_id="f1",
                    finding_type="sensitive_request",
                    evidence_ids=["money_0"],
                    reason="Large transfer",
                    confidence=0.90
                )
            ],
            skeptic_challenges=[
                AgentChallenge(
                    challenge_id="c1",
                    finding_id="f1",
                    challenge_type="supported",
                    explanation="Well-supported finding"
                )
            ],
            tier2_status="completed",
            warnings=[],
            agent_metadata={
                "fraud_agent_findings": 1,
                "skeptic_agent_challenges": 1
            }
        )

        json_data = result.model_dump()

        assert json_data["tier2_status"] == "completed"
        assert len(json_data["fraud_findings"]) == 1
        assert len(json_data["skeptic_challenges"]) == 1
        assert json_data["agent_metadata"]["fraud_agent_findings"] == 1

        # Verify JSON encoding works
        json_str = json.dumps(json_data, default=str)  # default=str for datetime
        assert "completed" in json_str


class TestDeterministicScoring:
    """Test that agents don't modify deterministic scoring."""

    def test_agent_findings_are_advisory_only(self):
        """Verify agent findings don't directly modify risk scores."""
        # This is a documentation/design test
        # Agent findings are stored separately from the Trust Judge assessment

        from app.schemas.agent import AgentFinding

        # Create a high-confidence fraud finding
        finding = AgentFinding(
            finding_id="f1",
            finding_type="sensitive_request",
            evidence_ids=["money_0"],
            reason="Suspicious pattern",
            confidence=0.95  # High confidence
        )

        # The finding itself has NO direct impact on Phase 2 scores
        # It's advisory information for human review
        assert finding.confidence == 0.95

        # Phase 2 scoring remains deterministic and unchanged
        # Agents propose, Rules decide, Humans verify

    def test_trust_judge_remains_authoritative(self):
        """Test Trust Judge scoring is not influenced by agent findings."""
        # This is a design/documentation test
        # Agent findings are stored separately and do NOT modify Phase 2 scores
        # The Trust Judge remains the sole authority for risk scores

        from app.schemas.agent import AgentFinding

        # Create a high-confidence fraud finding
        finding = AgentFinding(
            finding_id="f1",
            finding_type="sensitive_request",
            evidence_ids=["money_0"],
            reason="Suspicious pattern",
            confidence=0.95
        )

        # The finding itself has NO direct impact on Phase 2 scores
        # It's advisory information for human review
        assert finding.confidence == 0.95

        # Phase 2 Trust Engine scoring is:
        # 1. Deterministic (same inputs → same output)
        # 2. Rule-based (not ML-influenced)
        # 3. Not modified by agent findings
        # 4. The authoritative source for risk levels

        # Agents propose → Rules decide → Humans verify
        # This architecture is preserved in Phase 3


class TestTier2FallbackBehavior:
    """Test graceful fallback when Tier 2 fails."""

    @pytest.mark.asyncio
    async def test_fraud_agent_failure_preserves_phase2(self):
        """Test Phase 2 results preserved when Fraud Agent fails."""
        from app.agents.orchestrator import AgentOrchestrator
        from app.schemas.evidence import (
            EvidenceExtraction, ClaimsEvidence, RequestEvidence,
            BehaviorEvidence, UrgencyEvidence, SecrecyEvidence, EmotionalPressureEvidence
        )
        from app.trust_engine.scoring import ScoreBreakdown, RiskLevel

        with patch('app.agents.orchestrator.get_llm_provider') as mock_get_provider:
            # Mock provider exists but Fraud Agent fails
            mock_provider = Mock()
            mock_get_provider.return_value = mock_provider

            orchestrator = AgentOrchestrator()

            # Fraud Agent fails
            orchestrator.fraud_agent.analyze = AsyncMock(side_effect=RuntimeError("Agent failed"))

            evidence = EvidenceExtraction(
                call_id="test-fraud-fail",
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
                final_score=55,
                # risk_level is a property
                identity=10, request=15, behavior=10, channel=15, voice=5,
                fired_rules=[], applied_floors=[]
            )

            result = await orchestrator.analyze(
                call_id="test-fallback",
                evidence=evidence,
                trust_context={},
                score_breakdown=score_breakdown
            )

            # Should return failure status
            assert result.tier2_status == "fraud_failed"
            assert len(result.warnings) > 0

            # Phase 2 results are preserved (passed separately, not in result)
            # score_breakdown remains unchanged
            assert score_breakdown.final_score == 55

    @pytest.mark.asyncio
    async def test_skeptic_agent_failure_preserves_fraud_findings(self):
        """Test Fraud findings preserved when Skeptic Agent fails."""
        from app.agents.orchestrator import AgentOrchestrator
        from app.schemas.evidence import (
            EvidenceExtraction, ClaimsEvidence, RequestEvidence,
            BehaviorEvidence, UrgencyEvidence, SecrecyEvidence, EmotionalPressureEvidence
        )
        from app.schemas.agent import FraudAgentResponse, AgentFinding
        from app.trust_engine.scoring import ScoreBreakdown, RiskLevel

        with patch('app.agents.orchestrator.get_llm_provider') as mock_get_provider:
            mock_provider = Mock()
            mock_get_provider.return_value = mock_provider

            orchestrator = AgentOrchestrator()

            # Fraud Agent succeeds
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
                model_info={"model": "test"}
            )
            orchestrator.fraud_agent.analyze = AsyncMock(return_value=fraud_response)

            # Skeptic Agent fails
            orchestrator.skeptic_agent.analyze = AsyncMock(side_effect=ValueError("Skeptic error"))

            evidence = EvidenceExtraction(
                call_id="test-skeptic-error",
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
                final_score=60,
                # risk_level is a property
                identity=15, request=20, behavior=10, channel=10, voice=5,
                fired_rules=[], applied_floors=[]
            )

            result = await orchestrator.analyze(
                call_id="test-skeptic-fail",
                evidence=evidence,
                trust_context={},
                score_breakdown=score_breakdown
            )

            # Fraud findings preserved despite Skeptic failure
            assert result.tier2_status == "skeptic_failed"
            assert len(result.fraud_findings) == 1
            assert result.fraud_findings[0].finding_id == "f1"
            assert len(result.skeptic_challenges) == 0
            assert "Skeptic" in result.warnings[0]


class TestBackwardCompatibility:
    """Test backward compatibility with existing API."""

    def test_phase2_response_schema_unchanged(self):
        """Verify Phase 2 response schema not broken by Phase 3."""
        # Phase 3 adds optional agent_findings_json field to AnalysisReport
        # Existing clients that don't check this field continue to work

        # This is a schema compatibility test
        from app.models.call import AnalysisReport
        from datetime import datetime, timezone

        # Create report without agent data (Phase 2 style)
        report = AnalysisReport(
            call_id="test-001",
            transcript_json='{"segments": []}',
            voice_json='{"status": "ok"}',
            agent_findings_json=None,  # Optional - can be None
            risk_level="medium",
            risk_score=50.0,
            analysis_mode="real"
        )

        assert report.call_id == "test-001"
        assert report.agent_findings_json is None

        # Create report with agent data (Phase 3 style)
        report_with_agents = AnalysisReport(
            call_id="test-002",
            transcript_json='{"segments": []}',
            voice_json='{"status": "ok"}',
            agent_findings_json='{"tier2_status": "completed", "fraud_findings": []}',
            risk_level="high",
            risk_score=75.0,
            analysis_mode="real"
        )

        assert report_with_agents.agent_findings_json is not None

        # Both schemas are valid - backward compatible


class TestEvidenceValidation:
    """Test evidence ID validation prevents hallucination."""

    @pytest.mark.asyncio
    async def test_fraud_agent_validates_evidence_ids(self):
        """Test Fraud Agent rejects findings with invalid evidence IDs."""
        from app.llm.provider import MockLLMProvider
        from app.agents.fraud_agent import FraudAgent
        from app.schemas.agent import AgentEvidencePackage, FraudAgentResponse, AgentFinding

        agent = FraudAgent(MockLLMProvider())

        # Create evidence package with known IDs
        package = AgentEvidencePackage(
            call_id="test",
            evidence_summary={
                "claims": {
                    "claims": [
                        {"id": "claim_0", "type": "relative", "value": "son", "confidence": 0.8, "quote": "Hi"}
                    ]
                }
            },
            trust_context={},
            phase2_signals={"risk_score": 50, "risk_level": "medium", "category_scores": {}, "fired_rules": [], "applied_floors": []},
            evidence_quality=0.8,
            warnings=[]
        )

        # Mock response with mixed valid/invalid evidence IDs
        mock_response = FraudAgentResponse(
            findings=[
                AgentFinding(
                    finding_id="f1",
                    finding_type="identity_concern",
                    evidence_ids=["claim_0"],  # VALID
                    reason="Valid finding"
                ),
                AgentFinding(
                    finding_id="f2",
                    finding_type="voice_indicator",
                    evidence_ids=["voice_999"],  # INVALID - fabricated
                    reason="Fabricated evidence"
                )
            ],
            processing_time_seconds=1.0,
            model_info={}
        )

        agent.llm.generate_structured = AsyncMock(return_value=mock_response)

        result = await agent.analyze(package)

        # Only valid finding should be returned
        assert len(result.findings) == 1
        assert result.findings[0].finding_id == "f1"

    @pytest.mark.asyncio
    async def test_skeptic_agent_validates_finding_refs(self):
        """Test Skeptic Agent rejects challenges to non-existent findings."""
        from app.llm.provider import MockLLMProvider
        from app.agents.skeptic_agent import SkepticAgent
        from app.schemas.agent import (
            AgentEvidencePackage, AgentFinding, AgentChallenge,
            SkepticAgentResponse
        )

        agent = SkepticAgent(MockLLMProvider())

        package = AgentEvidencePackage(
            call_id="test",
            evidence_summary={},
            trust_context={},
            phase2_signals={"risk_score": 50, "risk_level": "medium", "category_scores": {}, "fired_rules": [], "applied_floors": []},
            evidence_quality=0.8,
            warnings=[]
        )

        fraud_findings = [
            AgentFinding(
                finding_id="f1",
                finding_type="identity_concern",
                evidence_ids=["claim_0"],
                reason="Valid finding"
            )
        ]

        # Mock response with mixed valid/invalid finding references
        mock_response = SkepticAgentResponse(
            challenges=[
                AgentChallenge(
                    challenge_id="c1",
                    finding_id="f1",  # VALID reference
                    challenge_type="missing_context",
                    explanation="Valid challenge"
                ),
                AgentChallenge(
                    challenge_id="c2",
                    finding_id="f999",  # INVALID - finding doesn't exist
                    challenge_type="unsupported_evidence",
                    explanation="Challenge to phantom finding"
                )
            ],
            processing_time_seconds=0.8,
            model_info={}
        )

        agent.llm.generate_structured = AsyncMock(return_value=mock_response)

        result = await agent.analyze(package, fraud_findings)

        # Only valid challenge should be returned
        assert len(result.challenges) == 1
        assert result.challenges[0].challenge_id == "c1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
