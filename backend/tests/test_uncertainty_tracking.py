"""
Tests for Phase 1 Feature 6: Uncertainty Tracking

Tests that uncertainty is properly represented:
- Low-confidence ASR transcripts
- Incomplete utterances (partial text)
- Missing finality information
- Mixed certain/uncertain evidence
- Uncertainty preserved in signals
"""
import pytest
from app.extractors.tier1_classifier import Tier1Classifier
from app.schemas.report import TranscriptSegment


class TestLowConfidenceHandling:
    """Test handling of low-confidence ASR output."""
    
    def setup_method(self):
        """Create fresh classifier for each test."""
        self.classifier = Tier1Classifier()
    
    def test_low_asr_confidence_preserved(self):
        """Low ASR confidence should be preserved in segment."""
        segment = TranscriptSegment(
            text="Tell me your OTP",
            start=10.0,
            end=12.0,
            speaker="caller",
            is_final=True,
            confidence=0.45  # Low ASR confidence
        )
        
        # Verify low confidence is preserved
        assert segment.confidence == 0.45
    
    def test_missing_confidence_allowed(self):
        """Missing confidence should be None (not 0 or 1)."""
        segment = TranscriptSegment(
            text="Send money",
            start=10.0,
            end=12.0,
            speaker="caller",
            is_final=True,
            confidence=None  # No confidence available
        )
        
        # None is valid and distinct from 0.0 or 1.0
        assert segment.confidence is None


class TestPartialTextUncertainty:
    """Test that partial text maintains uncertainty."""
    
    def setup_method(self):
        """Create fresh classifier for each test."""
        self.classifier = Tier1Classifier()
    
    def test_partial_text_marked_provisional(self):
        """Partial text generates provisional signals with lower confidence."""
        segments = [
            TranscriptSegment(
                text="Tell me your OTP",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=False  # Partial/uncertain
            )
        ]
        
        result = self.classifier.classify(segments)
        
        assert len(result.signals) >= 1
        signal = result.signals[0]
        # Should be marked as provisional
        assert "PROVISIONAL" in signal.signal_type
        # Should have reduced confidence
        assert signal.confidence < 0.8
    
    def test_unknown_finality_treated_as_uncertain(self):
        """Unknown finality (None) should be treated as uncertain."""
        segments = [
            TranscriptSegment(
                text="Send 10000 rupees",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=None  # Unknown finality
            )
        ]
        
        result = self.classifier.classify(segments)
        
        # Should generate provisional signals (treated as uncertain)
        signals = [s for s in result.signals if "MONEY" in s.signal_type]
        if len(signals) > 0:
            assert "PROVISIONAL" in signals[0].signal_type


class TestMixedCertainUncertain:
    """Test calls with both certain and uncertain evidence."""
    
    def setup_method(self):
        """Create fresh classifier for each test."""
        self.classifier = Tier1Classifier()
    
    def test_mix_of_final_and_partial(self):
        """Mix of final and partial segments should produce both signal types."""
        segments = [
            TranscriptSegment(
                text="Send 5000 rupees",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=False  # Partial
            ),
            TranscriptSegment(
                text="Transfer 8000 rupees",  # Different request
                start=20.0,
                end=22.0,
                speaker="caller",
                is_final=True  # Committed
            ),
        ]
        
        result = self.classifier.classify(segments)
        
        # Should have both provisional and definitive signals
        provisional = [s for s in result.signals if "PROVISIONAL" in s.signal_type]
        definitive = [s for s in result.signals if "PROVISIONAL" not in s.signal_type and "MONEY" in s.signal_type]
        
        assert len(provisional) >= 1  # From partial
        assert len(definitive) >= 1  # From committed
    
    def test_highest_severity_from_committed_only(self):
        """Highest severity should reflect committed evidence."""
        segments = [
            TranscriptSegment(
                text="Tell me your OTP",  # Would be critical if committed
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=False  # But it's partial -> medium
            ),
            TranscriptSegment(
                text="Send money",  # High severity when committed
                start=20.0,
                end=22.0,
                speaker="caller",
                is_final=True  # Committed
            ),
        ]
        
        result = self.classifier.classify(segments)
        
        # Highest severity should be from committed evidence (high or medium from partial)
        assert result.highest_severity in ["high", "medium"]


class TestUncertaintyPreservation:
    """Test that uncertainty doesn't become certainty."""
    
    def setup_method(self):
        """Create fresh classifier for each test."""
        self.classifier = Tier1Classifier()
    
    def test_partial_not_in_definitive_extraction(self):
        """Partial text should not appear in definitive claim extraction."""
        segments = [
            TranscriptSegment(
                text="I am calling from your bank",
                start=5.0,
                end=7.0,
                speaker="caller",
                is_final=False  # Uncertain
            )
        ]
        
        claims = self.classifier.extract_claims(segments)
        
        # Uncertain text should not create definitive claims
        assert len(claims.claims) == 0
    
    def test_provisional_signal_does_not_escalate(self):
        """Provisional signals should maintain reduced severity."""
        segments = [
            TranscriptSegment(
                text="Tell me your ATM PIN",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=False  # Partial
            )
        ]
        
        result = self.classifier.classify(segments)
        
        pin_signals = [s for s in result.signals if "PIN" in s.signal_type]
        assert len(pin_signals) >= 1
        
        signal = pin_signals[0]
        # Should not be critical severity (downgraded due to uncertainty)
        assert signal.severity != "critical"
        assert signal.severity in ["low", "medium"]


class TestIncompleteUtterances:
    """Test handling of incomplete or ambiguous speech."""
    
    def setup_method(self):
        """Create fresh classifier for each test."""
        self.classifier = Tier1Classifier()
    
    def test_incomplete_sentence_no_false_positive(self):
        """Incomplete sentences should not trigger false positives."""
        segments = [
            TranscriptSegment(
                text="Tell me",  # Incomplete
                start=10.0,
                end=11.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        result = self.classifier.classify(segments)
        
        # Should not detect credential or money request from incomplete fragment
        cred_signals = [s for s in result.signals if "CREDENTIAL" in s.signal_type]
        money_signals = [s for s in result.signals if "MONEY" in s.signal_type]
        assert len(cred_signals) == 0
        assert len(money_signals) == 0
    
    def test_ambiguous_context_handled(self):
        """Ambiguous context should not generate high-confidence signals."""
        segments = [
            TranscriptSegment(
                text="The OTP is important for security",  # Mentions OTP but not a request
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        result = self.classifier.classify(segments)
        
        # Should not detect credential request (no imperative, just statement)
        cred_request_signals = [s for s in result.signals 
                                if "CREDENTIAL_REQUEST" in s.signal_type]
        assert len(cred_request_signals) == 0


class TestConfidenceScoreIntegrity:
    """Test that confidence scores remain meaningful."""
    
    def setup_method(self):
        """Create fresh classifier for each test."""
        self.classifier = Tier1Classifier()
    
    def test_committed_text_high_confidence(self):
        """Committed text should have pattern-level confidence (not artificially reduced)."""
        segments = [
            TranscriptSegment(
                text="Tell me your OTP",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=True,
                confidence=0.95  # High ASR confidence
            )
        ]
        
        result = self.classifier.classify(segments)
        
        assert len(result.signals) >= 1
        signal = result.signals[0]
        # Should have high pattern confidence (≥ 0.8 for this pattern)
        assert signal.confidence >= 0.8
    
    def test_partial_text_reduced_confidence(self):
        """Partial text should have meaningfully reduced confidence."""
        segments = [
            TranscriptSegment(
                text="Tell me your OTP",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=False,  # Partial
                confidence=0.95  # ASR confidence high, but text not final
            )
        ]
        
        result = self.classifier.classify(segments)
        
        assert len(result.signals) >= 1
        signal = result.signals[0]
        # Should have reduced confidence (< 0.8 for partial)
        assert signal.confidence < 0.8
        # But not too low (should still be meaningful)
        assert signal.confidence >= 0.5
    
    def test_confidence_never_exceeds_one(self):
        """Confidence scores should never exceed 1.0."""
        segments = [
            TranscriptSegment(
                text="Tell me your ATM PIN and OTP",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        result = self.classifier.classify(segments)
        
        for signal in result.signals:
            assert signal.confidence <= 1.0
            assert signal.confidence >= 0.0
