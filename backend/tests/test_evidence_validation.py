"""
Tests for Phase 1 Feature 2: Evidence Validation Against Committed Text

Tests that evidence is properly validated:
- Evidence quotes match actual transcript segments
- Timestamps correspond to correct segments
- Partial-only evidence is not promoted to definitive
- Missing or invalid evidence is marked appropriately
- Source references are preserved
"""
import pytest
from app.extractors.tier1_classifier import Tier1Classifier
from app.schemas.report import TranscriptSegment


class TestEvidenceQuoteValidation:
    """Test that evidence quotes match transcript text."""
    
    def setup_method(self):
        """Create fresh classifier for each test."""
        self.classifier = Tier1Classifier()
    
    def test_valid_quote_extraction(self):
        """Evidence quote should match actual transcript text."""
        segments = [
            TranscriptSegment(
                text="Please tell me your OTP number",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        result = self.classifier.classify(segments)
        
        assert len(result.signals) >= 1
        signal = result.signals[0]
        # Quote should be substring of original text
        assert signal.quote in segments[0].text
    
    def test_timestamp_preservation(self):
        """Evidence should preserve correct timestamps."""
        segments = [
            TranscriptSegment(
                text="Send 50000 rupees now",
                start=20.5,
                end=23.2,
                speaker="caller",
                is_final=True
            )
        ]
        
        result = self.classifier.classify(segments)
        
        money_signals = [s for s in result.signals if "MONEY" in s.signal_type]
        assert len(money_signals) >= 1
        signal = money_signals[0]
        # Timestamp should match segment start
        assert signal.t == 20.5
    
    def test_multiple_segments_correct_attribution(self):
        """Evidence from different segments should have correct timestamps."""
        segments = [
            TranscriptSegment(
                text="I am calling from HDFC bank",
                start=5.0,
                end=7.0,
                speaker="caller",
                is_final=True
            ),
            TranscriptSegment(
                text="Please share your ATM PIN",
                start=15.0,
                end=17.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        # Extract claims
        claims = self.classifier.extract_claims(segments)
        assert len(claims.claims) >= 1
        claim = claims.claims[0]
        assert claim.t == 5.0  # First segment
        
        # Extract requests
        requests = self.classifier.extract_requests(segments)
        assert len(requests.credential_requests) >= 1
        req = requests.credential_requests[0]
        assert req.t == 15.0  # Second segment


class TestPartialEvidenceHandling:
    """Test that partial evidence is not promoted to definitive."""
    
    def setup_method(self):
        """Create fresh classifier for each test."""
        self.classifier = Tier1Classifier()
    
    def test_partial_only_not_in_claims(self):
        """Claims from partial text should not appear in extract_claims."""
        segments = [
            TranscriptSegment(
                text="I am calling from your bank",
                start=5.0,
                end=7.0,
                speaker="caller",
                is_final=False  # Partial only
            )
        ]
        
        claims = self.classifier.extract_claims(segments)
        
        # No claims from partial text
        assert len(claims.claims) == 0
    
    def test_partial_only_not_in_requests(self):
        """Requests from partial text should not appear in extract_requests."""
        segments = [
            TranscriptSegment(
                text="Tell me your OTP",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=False  # Partial only
            )
        ]
        
        requests = self.classifier.extract_requests(segments)
        
        # No requests from partial text
        assert len(requests.credential_requests) == 0
    
    def test_provisional_signals_clearly_marked(self):
        """Partial text should generate provisional signals, not definitive."""
        segments = [
            TranscriptSegment(
                text="Send 10000 rupees",
                start=20.0,
                end=22.0,
                speaker="caller",
                is_final=False
            )
        ]
        
        result = self.classifier.classify(segments)
        
        # Should have provisional signal
        provisional = [s for s in result.signals if "PROVISIONAL" in s.signal_type]
        assert len(provisional) >= 1
        
        # Should not have definitive signal
        definitive_money = [s for s in result.signals 
                          if "MONEY" in s.signal_type and "PROVISIONAL" not in s.signal_type]
        assert len(definitive_money) == 0


class TestMissingOrInvalidData:
    """Test handling of missing or invalid evidence data."""
    
    def setup_method(self):
        """Create fresh classifier for each test."""
        self.classifier = Tier1Classifier()
    
    def test_empty_text_no_evidence(self):
        """Empty text should not generate evidence."""
        segments = [
            TranscriptSegment(
                text="",
                start=5.0,
                end=7.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        result = self.classifier.classify(segments)
        assert len(result.signals) == 0
        
        claims = self.classifier.extract_claims(segments)
        assert len(claims.claims) == 0
    
    def test_whitespace_only_no_evidence(self):
        """Whitespace-only text should not generate evidence."""
        segments = [
            TranscriptSegment(
                text="   \t\n  ",
                start=5.0,
                end=7.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        result = self.classifier.classify(segments)
        assert len(result.signals) == 0
    
    def test_unknown_finality_treated_as_partial(self):
        """None/unknown finality should be treated conservatively (as partial)."""
        segments = [
            TranscriptSegment(
                text="I am from police station",
                start=5.0,
                end=7.0,
                speaker="caller",
                is_final=None  # Unknown
            )
        ]
        
        # Should not extract claims (treated as partial)
        claims = self.classifier.extract_claims(segments)
        assert len(claims.claims) == 0
        
        # But may generate provisional signals
        result = self.classifier.classify(segments)
        # If any signals, they should be provisional or low-severity
        for signal in result.signals:
            assert "PROVISIONAL" in signal.signal_type or signal.severity in ["low", "medium"]


class TestSessionAndSourceTracking:
    """Test that session IDs and source information are preserved."""
    
    def setup_method(self):
        """Create fresh classifier for each test."""
        self.classifier = Tier1Classifier()
    
    def test_session_id_in_segment(self):
        """Session ID should be available in transcript segment."""
        segment = TranscriptSegment(
            text="Tell me your OTP",
            start=10.0,
            end=12.0,
            speaker="caller",
            is_final=True,
            session_id="session_abc123"
        )
        
        # Verify session_id is preserved in segment
        assert segment.session_id == "session_abc123"
    
    def test_confidence_score_preservation(self):
        """ASR confidence should be preserved in segment."""
        segment = TranscriptSegment(
            text="Send money now",
            start=10.0,
            end=12.0,
            speaker="caller",
            is_final=True,
            confidence=0.87
        )
        
        # Verify confidence is preserved
        assert segment.confidence == 0.87


class TestNormalizationInValidation:
    """Test that normalization doesn't break validation."""
    
    def setup_method(self):
        """Create fresh classifier for each test."""
        self.classifier = Tier1Classifier()
    
    def test_case_insensitive_matching(self):
        """Patterns should match regardless of case."""
        segments_lower = [
            TranscriptSegment(
                text="tell me your otp",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        segments_upper = [
            TranscriptSegment(
                text="TELL ME YOUR OTP",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        result_lower = self.classifier.classify(segments_lower)
        self.classifier.reset_session()
        result_upper = self.classifier.classify(segments_upper)
        
        # Both should detect the credential request
        assert len(result_lower.signals) >= 1
        assert len(result_upper.signals) >= 1
        
        # Signal types should match
        assert result_lower.signals[0].signal_type == result_upper.signals[0].signal_type
    
    def test_original_text_preserved_in_quote(self):
        """Original text case should be preserved in evidence quote."""
        segments = [
            TranscriptSegment(
                text="Tell Me Your OTP Number",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        result = self.classifier.classify(segments)
        
        assert len(result.signals) >= 1
        signal = result.signals[0]
        # Quote should preserve original mixed case
        assert signal.quote in segments[0].text
        # Should not be all lowercase or all uppercase
        assert signal.quote != signal.quote.lower()
        assert signal.quote != signal.quote.upper()


class TestEvidenceQualityIndicators:
    """Test that evidence includes quality indicators."""
    
    def setup_method(self):
        """Create fresh classifier for each test."""
        self.classifier = Tier1Classifier()
    
    def test_high_confidence_committed_text(self):
        """Committed text with high ASR confidence should produce high-confidence signals."""
        segments = [
            TranscriptSegment(
                text="Tell me your card CVV",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=True,
                confidence=0.95
            )
        ]
        
        result = self.classifier.classify(segments)
        
        assert len(result.signals) >= 1
        signal = result.signals[0]
        # Should have high pattern confidence (not reduced for partial)
        assert signal.confidence >= 0.8
    
    def test_partial_text_lower_confidence(self):
        """Partial text should have reduced confidence."""
        segments = [
            TranscriptSegment(
                text="Tell me your card CVV",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=False,
                confidence=0.95  # ASR confidence high, but text not final
            )
        ]
        
        result = self.classifier.classify(segments)
        
        assert len(result.signals) >= 1
        signal = result.signals[0]
        # Should have reduced pattern confidence due to partial status
        assert signal.confidence < 0.8
        assert signal.confidence >= 0.5  # But not too low
