"""
Phase 2: Provisional Evidence Safety Tests

Verify that partial/provisional transcript segments cannot trigger definitive hard floors.
"""
import pytest
from sqlalchemy.orm import Session

from app.schemas.report import TranscriptResponse, TranscriptSegment
from app.extractors.evidence_pipeline import extract_evidence_from_transcript
from app.trust_engine.judge import TrustJudge
from app.trust_engine.trust_graph import TrustGraph
from app.trust_engine.scoring import RiskLevel


class TestProvisionalEvidence:
    """Test provisional (partial/uncommitted) evidence handling."""
    
    def test_partial_otp_does_not_trigger_floor(self, test_db: Session):
        """Partial OTP request must NOT trigger 75-point hard floor."""
        # Create partial transcript with OTP request
        transcript = TranscriptResponse(
            call_id="test-partial-otp",
            segments=[
                TranscriptSegment(
                    text="Please tell me your OTP",
                    start=1.0,
                    end=3.0,
                    speaker="caller",
                    is_final=False  # PARTIAL TEXT
                )
            ],
            full_text="Please tell me your OTP",
            transcription_status="in_progress",
            language="en",
            is_mock=False
        )
        
        # Extract evidence
        evidence = extract_evidence_from_transcript(transcript, "test-partial-otp")
        
        # Verify no credential requests extracted from partial text
        assert len(evidence.requests.credential_requests) == 0, \
            "Partial OTP request should not be extracted as committed credential request"
        
        # Verify provisional signal was generated
        assert any("PROVISIONAL_CREDENTIAL" in sig for sig in evidence.tier1_signals), \
            "Should generate provisional signal for partial text"
        
        # Run through Trust Judge
        graph = TrustGraph(test_db)
        judge = TrustJudge()
        
        assessment = judge.evaluate(
            call_id="test-partial-otp",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Verify OTP floor NOT triggered
        assert assessment.score < 75, \
            f"Partial OTP should NOT trigger 75-point floor (got {assessment.score})"
        assert "HARD_FLOOR_1" not in assessment.applied_floors, \
            "Floor 1 (OTP + unverified) should not be applied for partial text"
    
    def test_committed_otp_does_trigger_floor(self, test_db: Session):
        """Committed OTP request MUST trigger 75-point hard floor."""
        # Create committed transcript with OTP request
        transcript = TranscriptResponse(
            call_id="test-committed-otp",
            segments=[
                TranscriptSegment(
                    text="Please tell me your OTP",
                    start=1.0,
                    end=3.0,
                    speaker="caller",
                    is_final=True  # COMMITTED TEXT
                )
            ],
            full_text="Please tell me your OTP",
            transcription_status="completed",
            language="en",
            is_mock=False
        )
        
        # Extract evidence
        evidence = extract_evidence_from_transcript(transcript, "test-committed-otp")
        
        # Verify credential request extracted from committed text
        assert len(evidence.requests.credential_requests) > 0, \
            "Committed OTP request should be extracted"
        assert any(req.type == "otp" for req in evidence.requests.credential_requests), \
            "Should detect OTP type"
        
        # Run through Trust Judge
        graph = TrustGraph(test_db)
        judge = TrustJudge()
        
        assessment = judge.evaluate(
            call_id="test-committed-otp",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Verify OTP floor IS triggered
        assert assessment.score >= 75, \
            f"Committed OTP should trigger 75-point floor (got {assessment.score})"
        assert assessment.risk_level == RiskLevel.CRITICAL.value
    
    def test_unknown_finality_treated_as_partial(self, test_db: Session):
        """Unknown finality (is_final=None) must be treated as partial (safe default)."""
        # Create transcript with unknown finality
        transcript = TranscriptResponse(
            call_id="test-unknown-finality",
            segments=[
                TranscriptSegment(
                    text="Give me your PIN number now",
                    start=1.0,
                    end=3.0,
                    speaker="caller",
                    is_final=None  # UNKNOWN FINALITY
                )
            ],
            full_text="Give me your PIN number now",
            transcription_status="unknown",
            language="en",
            is_mock=False
        )
        
        # Extract evidence
        evidence = extract_evidence_from_transcript(transcript, "test-unknown-finality")
        
        # Verify no credential requests extracted (treated as partial)
        assert len(evidence.requests.credential_requests) == 0, \
            "Unknown finality should be treated as partial (safe default)"
        
        # Run through Trust Judge
        graph = TrustGraph(test_db)
        judge = TrustJudge()
        
        assessment = judge.evaluate(
            call_id="test-unknown-finality",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Verify floor NOT triggered
        assert assessment.score < 75, \
            f"Unknown finality should NOT trigger floor (got {assessment.score})"
    
    def test_partial_then_committed_no_duplicate(self, test_db: Session):
        """Processing partial then committed version should not double-count."""
        # First call: partial text
        transcript_partial = TranscriptResponse(
            call_id="test-transition",
            segments=[
                TranscriptSegment(
                    text="Tell me your O",
                    start=1.0,
                    end=2.0,
                    speaker="caller",
                    is_final=False
                )
            ],
            full_text="Tell me your O",
            transcription_status="in_progress",
            language="en",
            is_mock=False
        )
        
        evidence_partial = extract_evidence_from_transcript(
            transcript_partial, "test-transition"
        )
        
        # Second call: committed complete text
        transcript_committed = TranscriptResponse(
            call_id="test-transition",
            segments=[
                TranscriptSegment(
                    text="Tell me your OTP",
                    start=1.0,
                    end=3.0,
                    speaker="caller",
                    is_final=True
                )
            ],
            full_text="Tell me your OTP",
            transcription_status="completed",
            language="en",
            is_mock=False
        )
        
        evidence_committed = extract_evidence_from_transcript(
            transcript_committed, "test-transition"
        )
        
        # Verify partial extracted no committed requests
        assert len(evidence_partial.requests.credential_requests) == 0
        
        # Verify committed extracted exactly one request
        assert len(evidence_committed.requests.credential_requests) == 1
        
        # Run both through Trust Judge
        graph = TrustGraph(test_db)
        judge = TrustJudge()
        
        assessment_partial = judge.evaluate(
            call_id="test-transition-1",
            evidence=evidence_partial,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        assessment_committed = judge.evaluate(
            call_id="test-transition-2",
            evidence=evidence_committed,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Verify different scores
        assert assessment_partial.score < 75
        assert assessment_committed.score >= 75
    
    def test_provisional_money_request(self, test_db: Session):
        """Partial money request should not contribute to hard floors."""
        transcript = TranscriptResponse(
            call_id="test-partial-money",
            segments=[
                TranscriptSegment(
                    text="Send me 50000 rupees urgently",
                    start=1.0,
                    end=3.0,
                    speaker="caller",
                    is_final=False  # PARTIAL
                )
            ],
            full_text="Send me 50000 rupees urgently",
            transcription_status="in_progress",
            language="en",
            is_mock=False
        )
        
        evidence = extract_evidence_from_transcript(transcript, "test-partial-money")
        
        # Verify no money requests extracted from partial text
        assert len(evidence.requests.money_requests) == 0, \
            "Partial money request should not be extracted"
        
        # Run through Trust Judge
        graph = TrustGraph(test_db)
        judge = TrustJudge()
        
        assessment = judge.evaluate(
            call_id="test-partial-money",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Should have low score (no committed requests)
        assert assessment.score < 25, \
            f"Partial money request should result in low score (got {assessment.score})"


class TestCommittedEvidence:
    """Verify committed evidence still works correctly."""
    
    def test_all_three_floors_with_committed_evidence(self, test_db: Session):
        """Verify all three hard floors still work with committed evidence."""
        graph = TrustGraph(test_db)
        graph.add_contact("Mother", "mother", ["+918888888888"])
        judge = TrustJudge()
        
        # Floor 1: OTP + unverified
        transcript_f1 = TranscriptResponse(
            call_id="floor1",
            segments=[
                TranscriptSegment(
                    text="Please give me your OTP",
                    start=1.0,
                    end=3.0,
                    speaker="caller",
                    is_final=True
                )
            ],
            full_text="Please give me your OTP",
            transcription_status="completed",
            language="en",
            is_mock=False
        )
        
        evidence_f1 = extract_evidence_from_transcript(transcript_f1, "floor1")
        assessment_f1 = judge.evaluate(
            call_id="floor1",
            evidence=evidence_f1,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        assert assessment_f1.score >= 75, "Floor 1 should trigger"
        
        # Floor 2: Money + secrecy + mismatch
        transcript_f2 = TranscriptResponse(
            call_id="floor2",
            segments=[
                TranscriptSegment(
                    text="I am your Mother. Send 50000 rupees. Don't tell anyone.",
                    start=1.0,
                    end=5.0,
                    speaker="caller",
                    is_final=True
                )
            ],
            full_text="I am your Mother. Send 50000 rupees. Don't tell anyone.",
            transcription_status="completed",
            language="en",
            is_mock=False
        )
        
        evidence_f2 = extract_evidence_from_transcript(transcript_f2, "floor2")
        assessment_f2 = judge.evaluate(
            call_id="floor2",
            evidence=evidence_f2,
            trust_graph=graph,
            caller_number="+917777777777"  # Wrong number for Mother
        )
        
        assert assessment_f2.score >= 50, f"Floor 2 should trigger (got {assessment_f2.score})"


class TestMissingDataSafety:
    """Test that missing/uncertain evidence doesn't silently lower scores."""
    
    def test_missing_voice_no_score_reduction(self, test_db: Session):
        """Missing voice evidence should not reduce justified risk score."""
        # Create evidence with OTP request but no voice data
        transcript = TranscriptResponse(
            call_id="test-no-voice",
            segments=[
                TranscriptSegment(
                    text="Tell me your OTP immediately",
                    start=1.0,
                    end=3.0,
                    speaker="caller",
                    is_final=True
                )
            ],
            full_text="Tell me your OTP immediately",
            transcription_status="completed",
            language="en",
            is_mock=False
        )
        
        evidence = extract_evidence_from_transcript(transcript, "test-no-voice", voice_evidence=None)
        
        graph = TrustGraph(test_db)
        judge = TrustJudge()
        
        assessment = judge.evaluate(
            call_id="test-no-voice",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Missing voice should not prevent OTP floor
        assert assessment.score >= 75, \
            f"Missing voice should not reduce OTP floor (got {assessment.score})"
        assert assessment.category_scores["voice"] == 0, \
            "Voice category should contribute 0 when missing"
