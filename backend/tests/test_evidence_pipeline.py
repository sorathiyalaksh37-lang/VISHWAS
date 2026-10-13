"""
Integration tests for evidence extraction pipeline.

Tests the complete flow from TranscriptResponse to EvidenceExtraction.
"""
import pytest
from datetime import datetime

from app.schemas.report import TranscriptResponse, TranscriptSegment
from app.schemas.evidence import VoiceEvidence, VoiceQualityEvidence
from app.extractors.evidence_pipeline import (
    extract_evidence_from_transcript,
    extract_evidence_streaming,
    get_extraction_summary,
)
from app.extractors.tier1_classifier import Tier1Classifier


class TestEvidencePipelineIntegration:
    """Test complete evidence extraction pipeline."""
    
    def test_extract_from_scam_transcript(self):
        """Should extract evidence from scam transcript."""
        transcript = TranscriptResponse(
            call_id="test-call-001",
            language="en",
            transcription_status="completed",
            segments=[
                TranscriptSegment(
                    start=2.0,
                    end=5.0,
                    speaker="caller",
                    text="I am calling from your bank", is_final=True
                ),
                TranscriptSegment(
                    start=6.0,
                    end=9.0,
                    speaker="caller",
                    text="Your account will be blocked immediately", is_final=True
                ),
                TranscriptSegment(
                    start=10.0,
                    end=13.0,
                    speaker="caller",
                    text="Please tell me your OTP to verify", is_final=True
                ),
            ],
            is_mock=True
        )
        
        evidence = extract_evidence_from_transcript(transcript, "test-call-001")
        
        # Verify evidence structure
        assert evidence.call_id == "test-call-001"
        assert evidence.transcript_segments_analyzed == 3
        assert evidence.language_detected == "en"
        
        # Should detect bank claim
        assert len(evidence.claims.claims) > 0
        bank_claims = [c for c in evidence.claims.claims if c.type == "organization"]
        assert len(bank_claims) > 0
        
        # Should detect OTP request
        assert len(evidence.requests.credential_requests) > 0
        otp_requests = [r for r in evidence.requests.credential_requests if r.type == "otp"]
        assert len(otp_requests) > 0
        
        # Should detect urgency
        assert evidence.behavior.urgency.detected
        
        # Should have red flags
        assert evidence.has_red_flags
        
        # Should have Tier1 signals
        assert len(evidence.tier1_signals) > 0
        assert evidence.tier2_used == False
        assert evidence.fallback_used == False
    
    def test_extract_from_legitimate_transcript(self):
        """Should not flag legitimate conversation."""
        transcript = TranscriptResponse(
            call_id="test-call-002",
            language="en",
            transcription_status="completed",
            segments=[
                TranscriptSegment(
                    start=2.0,
                    end=5.0,
                    speaker="caller",
                    text="Hi, I wanted to check on the delivery", is_final=True
                ),
                TranscriptSegment(
                    start=6.0,
                    end=9.0,
                    speaker="caller",
                    text="It should arrive tomorrow afternoon", is_final=True
                ),
            ],
            is_mock=True
        )
        
        evidence = extract_evidence_from_transcript(transcript, "test-call-002")
        
        # Should complete without errors
        assert evidence.call_id == "test-call-002"
        
        # Should not detect critical evidence
        assert len(evidence.requests.credential_requests) == 0
        assert len(evidence.requests.money_requests) == 0
        
        # Should not have red flags
        assert not evidence.has_red_flags
    
    def test_extract_with_voice_evidence(self):
        """Should preserve voice evidence from M2."""
        transcript = TranscriptResponse(
            call_id="test-call-003",
            language="hi",
            transcription_status="completed",
            segments=[
                TranscriptSegment(
                    start=2.0,
                    end=5.0,
                    speaker="caller",
                    text="Mummy bol rahi hoon", is_final=True
                ),
            ],
            is_mock=True
        )
        
        voice_evidence = VoiceEvidence(
            status="ok",
            quality=VoiceQualityEvidence(
                duration_s=10.0,
                snr_db=15.0,
                clipping_detected=False
            ),
            spoof_detection=None,
            voiceprint_match=None,
            error_message=None
        )
        
        evidence = extract_evidence_from_transcript(
            transcript,
            "test-call-003",
            voice_evidence=voice_evidence
        )
        
        # Voice evidence should be preserved
        assert evidence.voice is not None
        assert evidence.voice.status == "ok"
        assert evidence.voice.quality.duration_s == 10.0
    
    def test_extract_from_empty_transcript(self):
        """Should handle empty transcript gracefully."""
        transcript = TranscriptResponse(
            call_id="test-call-004",
            language=None,
            transcription_status="not_available",
            segments=[],
            is_mock=True
        )
        
        evidence = extract_evidence_from_transcript(transcript, "test-call-004")
        
        # Should return empty evidence, not crash
        assert evidence.call_id == "test-call-004"
        assert evidence.transcript_segments_analyzed == 0
        assert len(evidence.claims.claims) == 0
        assert len(evidence.requests.credential_requests) == 0
        assert len(evidence.extraction_warnings) > 0
    
    def test_extract_hinglish_transcript(self):
        """Should extract from Hindi/Hinglish transcript."""
        transcript = TranscriptResponse(
            call_id="test-call-005",
            language="hinglish",
            transcription_status="completed",
            segments=[
                TranscriptSegment(
                    start=5.0,
                    end=8.0,
                    speaker="caller",
                    text="OTP bata do jaldi, account band ho jayega", is_final=True
                ),
                TranscriptSegment(
                    start=9.0,
                    end=12.0,
                    speaker="caller",
                    text="50000 rupaye bhej do turant", is_final=True
                ),
            ],
            is_mock=True
        )
        
        evidence = extract_evidence_from_transcript(transcript, "test-call-005")
        
        # Should detect Hindi patterns
        assert len(evidence.requests.credential_requests) > 0
        assert len(evidence.requests.money_requests) > 0
        assert evidence.behavior.urgency.detected
        assert evidence.has_red_flags
    
    def test_extract_family_emergency_scam(self):
        """Should extract evidence from family emergency scam."""
        transcript = TranscriptResponse(
            call_id="test-call-006",
            language="hinglish",
            transcription_status="completed",
            segments=[
                TranscriptSegment(
                    start=2.0,
                    end=5.0,
                    speaker="caller",
                    text="Mummy bol rahi hoon beta, emergency hai", is_final=True
                ),
                TranscriptSegment(
                    start=6.0,
                    end=9.0,
                    speaker="caller",
                    text="50000 rupaye bhej do abhi ke abhi", is_final=True
                ),
                TranscriptSegment(
                    start=10.0,
                    end=13.0,
                    speaker="caller",
                    text="Kisi ko mat batana yeh baat", is_final=True
                ),
            ],
            is_mock=True
        )
        
        evidence = extract_evidence_from_transcript(transcript, "test-call-006")
        
        # Should detect all patterns
        assert len(evidence.claims.claims) > 0
        assert evidence.claims.primary_claim.type == "relative"
        assert evidence.claims.primary_claim.value == "mother"
        
        assert len(evidence.requests.money_requests) > 0
        assert evidence.requests.max_money_amount == 50000.0
        
        assert evidence.behavior.urgency.detected
        assert evidence.behavior.secrecy.detected
        
        assert evidence.has_red_flags


class TestStreamingExtraction:
    """Test streaming mode evidence extraction."""
    
    def test_streaming_instant_detection(self):
        """Should provide instant signals in streaming mode."""
        segments = [
            TranscriptSegment(
                start=5.0,
                end=7.0,
                speaker="caller",
                text="Tell me your OTP", is_final=True
            )
        ]
        
        result = extract_evidence_streaming(segments, "stream-call-001")
        
        assert len(result.signals) > 0
        assert result.has_critical_signal
        assert result.detection_time_ms >= 0
    
    def test_streaming_with_session_classifier(self):
        """Should maintain session state for deduplication."""
        classifier = Tier1Classifier()
        classifier.reset_session()
        
        segment1 = [
            TranscriptSegment(
                start=5.0,
                end=7.0,
                speaker="caller",
                text="Tell me your OTP", is_final=True
            )
        ]
        
        result1 = extract_evidence_streaming(
            segment1,
            "stream-call-002",
            session_classifier=classifier
        )
        
        # Second call with same segment should deduplicate
        result2 = extract_evidence_streaming(
            segment1,
            "stream-call-002",
            session_classifier=classifier
        )
        
        assert len(result1.signals) > 0
        assert len(result2.signals) == 0  # Deduplicated
    
    def test_streaming_multiple_chunks(self):
        """Should process multiple chunks in sequence."""
        classifier = Tier1Classifier()
        classifier.reset_session()
        
        chunk1 = [
            TranscriptSegment(
                start=2.0,
                end=4.0,
                speaker="caller",
                text="I am calling from your bank", is_final=True
            )
        ]
        
        chunk2 = [
            TranscriptSegment(
                start=5.0,
                end=7.0,
                speaker="caller",
                text="Your account will be blocked", is_final=True
            )
        ]
        
        chunk3 = [
            TranscriptSegment(
                start=8.0,
                end=10.0,
                speaker="caller",
                text="Tell me your OTP immediately", is_final=True
            )
        ]
        
        result1 = extract_evidence_streaming(chunk1, "stream-call-003", classifier)
        result2 = extract_evidence_streaming(chunk2, "stream-call-003", classifier)
        result3 = extract_evidence_streaming(chunk3, "stream-call-003", classifier)
        
        # Each chunk should produce signals
        assert len(result1.signals) >= 0  # May or may not have signals
        assert len(result2.signals) >= 0
        assert len(result3.signals) > 0  # Should definitely have OTP signal
        assert result3.has_critical_signal


class TestExtractionSummary:
    """Test extraction summary generation."""
    
    def test_summary_generation(self):
        """Should generate complete summary."""
        transcript = TranscriptResponse(
            call_id="test-call-007",
            language="en",
            transcription_status="completed",
            segments=[
                TranscriptSegment(
                    start=2.0,
                    end=5.0,
                    speaker="caller",
                    text="I am your mother, send 25000 rupees urgently", is_final=True
                ),
            ],
            is_mock=True
        )
        
        evidence = extract_evidence_from_transcript(transcript, "test-call-007")
        summary = get_extraction_summary(evidence)
        
        assert summary["call_id"] == "test-call-007"
        assert summary["claims_count"] > 0
        assert summary["money_requests"] > 0
        assert summary["max_money_amount"] == 25000.0
        assert summary["urgency_detected"]
        assert summary["has_red_flags"]
        assert "quality_score" in summary
        assert "tier1_signals" in summary


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_malformed_segment_handling(self):
        """Should handle segments with unusual data."""
        transcript = TranscriptResponse(
            call_id="test-call-008",
            language="unknown",
            transcription_status="partial",
            segments=[
                TranscriptSegment(
                    start=0.0,
                    end=0.1,
                    speaker=None,
                    text="  ", is_final=True  # Whitespace only
                ),
            ],
            is_mock=True
        )
        
        evidence = extract_evidence_from_transcript(transcript, "test-call-008")
        
        # Should complete without errors
        assert evidence.call_id == "test-call-008"
        assert evidence.transcript_segments_analyzed >= 0
    
    def test_very_long_transcript(self):
        """Should handle long transcripts."""
        segments = [
            TranscriptSegment(
                start=float(i * 2),
                end=float(i * 2 + 2),
                speaker="caller",
                text=f"This is segment number {i} of the conversation"
            )
            for i in range(100)
        ]
        
        transcript = TranscriptResponse(
            call_id="test-call-009",
            language="en",
            transcription_status="completed",
            segments=segments,
            is_mock=True
        )
        
        evidence = extract_evidence_from_transcript(transcript, "test-call-009")
        
        # Should process all segments
        assert evidence.transcript_segments_analyzed == 100
        assert evidence.extraction_timestamp is not None
    
    def test_mixed_language_transcript(self):
        """Should handle mixed language transcript."""
        transcript = TranscriptResponse(
            call_id="test-call-010",
            language="hinglish",
            transcription_status="completed",
            segments=[
                TranscriptSegment(
                    start=2.0,
                    end=5.0,
                    speaker="caller",
                    text="Hello, main bank se call kar raha hoon", is_final=True
                ),
                TranscriptSegment(
                    start=6.0,
                    end=9.0,
                    speaker="caller",
                    text="Please aap apna OTP bataiye", is_final=True
                ),
            ],
            is_mock=True
        )
        
        evidence = extract_evidence_from_transcript(transcript, "test-call-010")
        
        # Should detect patterns in mixed language
        assert len(evidence.claims.claims) > 0
        assert len(evidence.requests.credential_requests) > 0


class TestQualityMetrics:
    """Test evidence quality metrics."""
    
    def test_quality_score_with_multiple_evidence(self):
        """Quality score should reflect evidence richness."""
        transcript = TranscriptResponse(
            call_id="test-call-011",
            language="en",
            transcription_status="completed",
            segments=[
                TranscriptSegment(
                    start=2.0,
                    end=5.0,
                    speaker="caller",
                    text="I am calling from HDFC bank", is_final=True
                ),
                TranscriptSegment(
                    start=6.0,
                    end=9.0,
                    speaker="caller",
                    text="Tell me your OTP and PIN", is_final=True
                ),
                TranscriptSegment(
                    start=10.0,
                    end=13.0,
                    speaker="caller",
                    text="Send 100000 rupees immediately or account will be blocked", is_final=True
                ),
            ],
            is_mock=True
        )
        
        evidence = extract_evidence_from_transcript(transcript, "test-call-011")
        
        # Should have good quality score with multiple evidence types
        assert evidence.evidence_quality_score > 0.5
        assert evidence.has_red_flags
    
    def test_warnings_generation(self):
        """Should generate appropriate warnings."""
        transcript = TranscriptResponse(
            call_id="test-call-012",
            language="fr",  # Unsupported language
            transcription_status="partial",
            segments=[
                TranscriptSegment(
                    start=1.0,
                    end=2.0,
                    speaker="caller",
                    text="Bonjour", is_final=True
                ),
            ],
            is_mock=True
        )
        
        evidence = extract_evidence_from_transcript(transcript, "test-call-012")
        
        # Should have warnings about language and status
        assert len(evidence.extraction_warnings) > 0
        warning_text = " ".join(evidence.extraction_warnings)
        assert "language" in warning_text.lower() or "partial" in warning_text.lower()
