"""
Phase 2: Database Persistence and API Consistency Tests

Verify that Trust Judge results remain consistent across:
- In-memory assessment
- Database persistence
- API response serialization
- Retrieved analysis
"""
import pytest
import json
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.models.call import CallRecord, AnalysisReport
from app.schemas.report import TranscriptResponse, TranscriptSegment
from app.extractors.evidence_pipeline import extract_evidence_from_transcript
from app.trust_engine.judge import TrustJudge
from app.trust_engine.trust_graph import TrustGraph
from app.trust_engine.scoring import RiskLevel


class TestDatabasePersistence:
    """Test that Trust Judge results are correctly persisted."""
    
    def test_assessment_persisted_to_database(self, test_db: Session):
        """Verify Trust Judge assessment is correctly saved to database."""
        # Create committed transcript with OTP request
        transcript = TranscriptResponse(
            call_id="test-persist",
            segments=[
                TranscriptSegment(
                    text="Please tell me your OTP number",
                    start=1.0,
                    end=3.0,
                    speaker="caller",
                    is_final=True
                )
            ],
            full_text="Please tell me your OTP number",
            transcription_status="completed",
            language="en",
            is_mock=False
        )
        
        # Extract evidence and run through Trust Judge
        evidence = extract_evidence_from_transcript(transcript, "test-persist")
        graph = TrustGraph(test_db)
        judge = TrustJudge()
        
        assessment = judge.evaluate(
            call_id="test-persist",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Simulate persistence (as done in real_analysis_service.py)
        call = CallRecord(
            id="test-persist",
            original_filename="test.wav",
            stored_filename="test_stored.wav",
            storage_reference="/tmp/test.wav",
            status="completed"
        )
        test_db.add(call)
        test_db.commit()
        
        report = AnalysisReport(
            call_id="test-persist",
            analysis_mode="real",
            risk_score=assessment.score,
            risk_level=assessment.risk_level,
            reasons_json=json.dumps(assessment.reasons, ensure_ascii=False),
            category_scores_json=json.dumps(assessment.category_scores, ensure_ascii=False),
            fired_rules_json=json.dumps(assessment.fired_rules, ensure_ascii=False),
            killchain_stage=assessment.killchain_stage,
            verification_json=json.dumps(
                {
                    "method": assessment.verification_method,
                    "details": assessment.verification_details
                },
                ensure_ascii=False
            ) if assessment.verification_method else None,
            transcript_json=None,
            agent_findings_json=json.dumps([], ensure_ascii=False),
            recommended_actions_json=json.dumps([], ensure_ascii=False),
            warnings_json=json.dumps([], ensure_ascii=False)
        )
        test_db.add(report)
        test_db.commit()
        test_db.refresh(report)
        
        # Verify persisted data matches assessment
        assert report.risk_score == assessment.score
        assert report.risk_level == assessment.risk_level
        assert report.killchain_stage == assessment.killchain_stage
        
        # Verify JSON fields can be deserialized
        persisted_category_scores = json.loads(report.category_scores_json)
        assert persisted_category_scores == assessment.category_scores
        
        persisted_fired_rules = json.loads(report.fired_rules_json)
        assert set(persisted_fired_rules) == set(assessment.fired_rules)
        
        persisted_reasons = json.loads(report.reasons_json)
        assert set(persisted_reasons) == set(assessment.reasons)
    
    def test_category_scores_preserved(self, test_db: Session):
        """Verify all category scores are preserved in persistence."""
        transcript = TranscriptResponse(
            call_id="test-categories",
            segments=[
                TranscriptSegment(
                    text="I am your mother. Send 50000 rupees via UPI. Tell me your PIN. Do it now. Don't tell anyone.",
                    start=1.0,
                    end=10.0,
                    speaker="caller",
                    is_final=True
                )
            ],
            full_text="I am your mother. Send 50000 rupees via UPI. Tell me your PIN. Do it now. Don't tell anyone.",
            transcription_status="completed",
            language="en",
            is_mock=False
        )
        
        evidence = extract_evidence_from_transcript(transcript, "test-categories")
        graph = TrustGraph(test_db)
        judge = TrustJudge()
        
        assessment = judge.evaluate(
            call_id="test-categories",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Persist
        category_scores_json = json.dumps(assessment.category_scores, ensure_ascii=False)
        
        # Deserialize and verify all categories
        persisted_scores = json.loads(category_scores_json)
        
        expected_categories = ["identity", "request", "behavior", "channel", "voice"]
        for category in expected_categories:
            assert category in persisted_scores, f"Missing category: {category}"
            assert isinstance(persisted_scores[category], (int, float))
            assert 0 <= persisted_scores[category] <= 100
        
        # Verify category caps respected
        assert persisted_scores["identity"] <= 25
        assert persisted_scores["request"] <= 30
        assert persisted_scores["behavior"] <= 20
        assert persisted_scores["channel"] <= 15
        assert persisted_scores["voice"] <= 10


class TestAPIResponseConsistency:
    """Test API response matches database state."""
    
    def test_api_response_matches_persisted_data(self, test_db: Session):
        """Verify API response deserializes database state correctly."""
        from app.api.routes.analyze import _build_report_response
        from app.schemas.report import AnalysisReportResponse
        
        # Create test data
        call = CallRecord(
            id="test-api-consistency",
            original_filename="test.wav",
            stored_filename="test_stored.wav",
            storage_reference="/tmp/test.wav",
            status="completed"
        )
        test_db.add(call)
        test_db.commit()
        
        # Create report with known values
        test_score = 75
        test_level = "CRITICAL"
        test_category_scores = {
            "identity": 15,
            "request": 30,
            "behavior": 15,
            "channel": 10,
            "voice": 0
        }
        test_fired_rules = ["REQ_OTP_PIN", "IDENTITY_UNKNOWN", "HARD_FLOOR_1"]
        test_reasons = ["Request for OTP or PIN detected", "Caller claims identity from unknown number"]
        
        report = AnalysisReport(
            call_id="test-api-consistency",
            analysis_mode="real",
            risk_score=test_score,
            risk_level=test_level,
            category_scores_json=json.dumps(test_category_scores),
            fired_rules_json=json.dumps(test_fired_rules),
            reasons_json=json.dumps(test_reasons),
            killchain_stage="request",
            verification_json=json.dumps({"action": "callback_saved_number", "target": "Saved Contact"}),
            transcript_json=None,
            agent_findings_json=json.dumps([]),
            recommended_actions_json=json.dumps([]),
            warnings_json=json.dumps([])
        )
        test_db.add(report)
        test_db.commit()
        test_db.refresh(report)
        
        # Build API response
        response = _build_report_response(call, report)
        
        # Verify consistency
        assert response.score == test_score
        assert response.level == test_level
        assert response.category_scores.identity == test_category_scores["identity"]
        assert response.category_scores.request == test_category_scores["request"]
        assert response.category_scores.behavior == test_category_scores["behavior"]
        assert response.category_scores.channel == test_category_scores["channel"]
        assert response.category_scores.voice == test_category_scores["voice"]
        assert set(response.fired_rules) == set(test_fired_rules)
        assert set(response.reasons) == set(test_reasons)
        assert response.killchain_stage == "request"
        assert response.verification.action == "callback_saved_number"


class TestIdempotency:
    """Test that repeated processing produces consistent results."""
    
    def test_same_evidence_same_assessment(self, test_db: Session):
        """Processing same evidence twice should produce identical assessments."""
        transcript = TranscriptResponse(
            call_id="test-idempotent",
            segments=[
                TranscriptSegment(
                    text="Send me your account password",
                    start=1.0,
                    end=3.0,
                    speaker="caller",
                    is_final=True
                )
            ],
            full_text="Send me your account password",
            transcription_status="completed",
            language="en",
            is_mock=False
        )
        
        # Extract evidence twice
        evidence1 = extract_evidence_from_transcript(transcript, "test-idempotent-1")
        evidence2 = extract_evidence_from_transcript(transcript, "test-idempotent-2")
        
        # Run through Trust Judge twice
        graph = TrustGraph(test_db)
        judge = TrustJudge()
        
        assessment1 = judge.evaluate(
            call_id="test-idempotent-1",
            evidence=evidence1,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Reset deduplication for second run
        judge.scorer.reset_session()
        
        assessment2 = judge.evaluate(
            call_id="test-idempotent-2",
            evidence=evidence2,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Verify identical results
        assert assessment1.score == assessment2.score
        assert assessment1.risk_level == assessment2.risk_level
        assert assessment1.category_scores == assessment2.category_scores
        assert set(assessment1.fired_rules) == set(assessment2.fired_rules)
        assert assessment1.channel_status == assessment2.channel_status
    
    def test_no_duplicate_counting_on_retry(self, test_db: Session):
        """Reprocessing same call should not inflate score."""
        from app.extractors.tier1_classifier import Tier1Classifier
        
        segments = [
            TranscriptSegment(
                text="Give me your PIN",
                start=1.0,
                end=2.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        # Process once
        classifier1 = Tier1Classifier()
        result1 = classifier1.classify(segments)
        
        # Process again (simulating retry)
        classifier2 = Tier1Classifier()
        result2 = classifier2.classify(segments)
        
        # Should detect same signals (with deduplication)
        assert len(result1.signals) == len(result2.signals)
        assert result1.has_critical_signal == result2.has_critical_signal


class TestProcessingFailureSafety:
    """Test that failures don't silently produce LOW-risk assessments."""
    
    def test_empty_transcript_warning(self, test_db: Session):
        """Empty transcript should produce warnings, not fake LOW-risk."""
        transcript = TranscriptResponse(
            call_id="test-empty",
            segments=[],
            full_text="",
            transcription_status="failed",
            language=None,
            is_mock=False
        )
        
        evidence = extract_evidence_from_transcript(transcript, "test-empty")
        
        # Should have warnings
        assert len(evidence.extraction_warnings) > 0
        assert any("empty" in w.lower() for w in evidence.extraction_warnings)
        
        # Run through Trust Judge
        graph = TrustGraph(test_db)
        judge = TrustJudge()
        
        assessment = judge.evaluate(
            call_id="test-empty",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Should have LOW score due to no evidence, but with warnings
        assert assessment.score == 0
        assert assessment.risk_level == RiskLevel.LOW.value
        assert len(assessment.warnings) > 0
    
    def test_extraction_failure_preserved(self, test_db: Session):
        """Extraction failures should be preserved in warnings."""
        # Create evidence with explicit warnings
        transcript = TranscriptResponse(
            call_id="test-warnings",
            segments=[
                TranscriptSegment(
                    text="Test",
                    start=0,
                    end=1,
                    speaker="caller",
                    is_final=True
                )
            ],
            full_text="Test",
            transcription_status="completed",
            language="unknown_language",
            is_mock=False
        )
        
        evidence = extract_evidence_from_transcript(transcript, "test-warnings")
        
        # Should have language warning
        assert any("language" in w.lower() for w in evidence.extraction_warnings)


class TestRiskBandBoundaries:
    """Test risk band edge cases."""
    
    def test_boundary_24_is_low(self, test_db: Session):
        """Score of 24 should be LOW."""
        from app.trust_engine.scoring import ScoreBreakdown
        
        # Test via ScoreBreakdown.risk_level property
        breakdown = ScoreBreakdown(final_score=24)
        assert breakdown.risk_level == RiskLevel.LOW
        
        breakdown2 = ScoreBreakdown(final_score=24.9)
        assert breakdown2.risk_level == RiskLevel.LOW
    
    def test_boundary_25_is_medium(self, test_db: Session):
        """Score of 25 should be MEDIUM."""
        from app.trust_engine.scoring import ScoreBreakdown
        
        breakdown = ScoreBreakdown(final_score=25)
        assert breakdown.risk_level == RiskLevel.MEDIUM
        
        breakdown2 = ScoreBreakdown(final_score=49)
        assert breakdown2.risk_level == RiskLevel.MEDIUM
        
        breakdown3 = ScoreBreakdown(final_score=49.9)
        assert breakdown3.risk_level == RiskLevel.MEDIUM
    
    def test_boundary_50_is_high(self, test_db: Session):
        """Score of 50 should be HIGH."""
        from app.trust_engine.scoring import ScoreBreakdown
        
        breakdown = ScoreBreakdown(final_score=50)
        assert breakdown.risk_level == RiskLevel.HIGH
        
        breakdown2 = ScoreBreakdown(final_score=74)
        assert breakdown2.risk_level == RiskLevel.HIGH
        
        breakdown3 = ScoreBreakdown(final_score=74.9)
        assert breakdown3.risk_level == RiskLevel.HIGH
    
    def test_boundary_75_is_critical(self, test_db: Session):
        """Score of 75 should be CRITICAL."""
        from app.trust_engine.scoring import ScoreBreakdown
        
        breakdown = ScoreBreakdown(final_score=75)
        assert breakdown.risk_level == RiskLevel.CRITICAL
        
        breakdown2 = ScoreBreakdown(final_score=100)
        assert breakdown2.risk_level == RiskLevel.CRITICAL
