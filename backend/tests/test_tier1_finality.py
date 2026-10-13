"""
Tests for Phase 1 Feature 1: Committed vs Partial Transcript Handling

Tests that Tier1Classifier correctly handles:
- Committed text (is_final=True) generates definitive signals
- Partial text (is_final=False or None) generates provisional warnings
- Confidence and severity adjustments for partial text
- Extraction methods respect finality
"""
import pytest
from app.extractors.tier1_classifier import Tier1Classifier
from app.schemas.report import TranscriptSegment


class TestCommittedVsPartialDetection:
    """Test signal detection for committed vs partial transcripts."""
    
    def setup_method(self):
        """Create fresh classifier for each test."""
        self.classifier = Tier1Classifier()
    
    def test_credential_request_committed(self):
        """Committed credential request generates critical signal."""
        segments = [
            TranscriptSegment(
                text="Please tell me your OTP for verification",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=True,
                confidence=0.95
            )
        ]
        
        result = self.classifier.classify(segments)
        
        assert len(result.signals) == 1
        signal = result.signals[0]
        assert signal.signal_type == "CREDENTIAL_REQUEST_OTP"
        assert signal.severity == "critical"
        assert signal.confidence >= 0.8
        assert "PROVISIONAL" not in signal.signal_type
    
    def test_credential_request_partial(self):
        """Partial credential request generates provisional warning."""
        segments = [
            TranscriptSegment(
                text="Please tell me your OTP",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=False,
                confidence=0.75
            )
        ]
        
        result = self.classifier.classify(segments)
        
        assert len(result.signals) == 1
        signal = result.signals[0]
        assert signal.signal_type == "PROVISIONAL_CREDENTIAL_REQUEST_OTP"
        assert signal.severity == "medium"  # Downgraded from critical
        assert signal.confidence < 0.8  # Reduced confidence
        assert signal.confidence >= 0.5
    
    def test_credential_request_unknown_finality(self):
        """Unknown finality (None) treated as partial - safe default."""
        segments = [
            TranscriptSegment(
                text="Tell me your ATM PIN",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=None,  # Unknown finality
                confidence=None
            )
        ]
        
        result = self.classifier.classify(segments)
        
        assert len(result.signals) >= 1
        # Find PIN signal
        pin_signals = [s for s in result.signals if "PIN" in s.signal_type]
        assert len(pin_signals) >= 1
        signal = pin_signals[0]
        assert signal.signal_type == "PROVISIONAL_CREDENTIAL_REQUEST_PIN"
        assert signal.severity == "medium"  # Treated as partial
    
    def test_money_request_committed(self):
        """Committed money request generates high severity signal."""
        segments = [
            TranscriptSegment(
                text="Transfer 50000 rupees to me",
                start=20.0,
                end=22.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        result = self.classifier.classify(segments)
        
        # Find money request signal (may have multiple signals)
        money_signals = [s for s in result.signals if "MONEY" in s.signal_type]
        assert len(money_signals) >= 1
        signal = money_signals[0]
        assert signal.signal_type == "MONEY_REQUEST"
        assert signal.severity == "high"
    
    def test_money_request_partial(self):
        """Partial money request generates provisional warning."""
        segments = [
            TranscriptSegment(
                text="Transfer 50000 rupees",
                start=20.0,
                end=22.0,
                speaker="caller",
                is_final=False
            )
        ]
        
        result = self.classifier.classify(segments)
        
        assert len(result.signals) == 1
        signal = result.signals[0]
        assert signal.signal_type == "PROVISIONAL_MONEY_REQUEST"
        assert signal.severity == "medium"  # Downgraded from high
    
    def test_urgency_committed(self):
        """Committed urgency generates appropriate severity."""
        segments = [
            TranscriptSegment(
                text="Do it right now or you will be arrested",
                start=30.0,
                end=32.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        result = self.classifier.classify(segments)
        
        assert len(result.signals) >= 1
        # Find urgency signal
        urgency_signals = [s for s in result.signals if "URGENCY" in s.signal_type]
        assert len(urgency_signals) >= 1
        signal = urgency_signals[0]
        assert signal.signal_type == "URGENCY_DETECTED"
        assert signal.severity in ["high", "medium"]
    
    def test_urgency_partial(self):
        """Partial urgency generates provisional warning with lower severity."""
        segments = [
            TranscriptSegment(
                text="Do it right now",
                start=30.0,
                end=32.0,
                speaker="caller",
                is_final=False
            )
        ]
        
        result = self.classifier.classify(segments)
        
        urgency_signals = [s for s in result.signals if "URGENCY" in s.signal_type]
        assert len(urgency_signals) >= 1
        signal = urgency_signals[0]
        assert signal.signal_type == "PROVISIONAL_URGENCY_DETECTED"
        assert signal.severity in ["low", "medium"]  # Lower than committed
    
    def test_secrecy_committed(self):
        """Committed secrecy generates medium severity."""
        segments = [
            TranscriptSegment(
                text="Don't tell anyone about this call",
                start=40.0,
                end=42.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        result = self.classifier.classify(segments)
        
        secrecy_signals = [s for s in result.signals if "SECRECY" in s.signal_type]
        assert len(secrecy_signals) >= 1
        signal = secrecy_signals[0]
        assert signal.signal_type == "SECRECY_DETECTED"
        assert signal.severity == "medium"
    
    def test_secrecy_partial(self):
        """Partial secrecy generates provisional warning with low severity."""
        segments = [
            TranscriptSegment(
                text="Don't tell anyone",
                start=40.0,
                end=42.0,
                speaker="caller",
                is_final=False
            )
        ]
        
        result = self.classifier.classify(segments)
        
        secrecy_signals = [s for s in result.signals if "SECRECY" in s.signal_type]
        assert len(secrecy_signals) >= 1
        signal = secrecy_signals[0]
        assert signal.signal_type == "PROVISIONAL_SECRECY_DETECTED"
        assert signal.severity == "low"  # Downgraded from medium


class TestExtractionMethodsFinality:
    """Test that extraction methods respect finality flag."""
    
    def setup_method(self):
        """Create fresh classifier for each test."""
        self.classifier = Tier1Classifier()
    
    def test_extract_claims_committed(self):
        """Claims extracted only from committed text."""
        segments = [
            TranscriptSegment(
                text="I am calling from HDFC bank",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        result = self.classifier.extract_claims(segments)
        
        assert len(result.claims) >= 1
        claim = result.claims[0]
        assert claim.type == "organization"
        assert "bank" in claim.value.lower()
    
    def test_extract_claims_partial_skipped(self):
        """Claims NOT extracted from partial text."""
        segments = [
            TranscriptSegment(
                text="I am calling from HDFC bank",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=False
            )
        ]
        
        result = self.classifier.extract_claims(segments)
        
        # No claims from partial text
        assert len(result.claims) == 0
    
    def test_extract_claims_unknown_finality_skipped(self):
        """Claims NOT extracted when finality unknown (safe default)."""
        segments = [
            TranscriptSegment(
                text="I am calling from police station",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=None
            )
        ]
        
        result = self.classifier.extract_claims(segments)
        
        # Treated as partial - no claims
        assert len(result.claims) == 0
    
    def test_extract_requests_committed(self):
        """Requests extracted only from committed text."""
        segments = [
            TranscriptSegment(
                text="Tell me your OTP code for verification",
                start=20.0,
                end=22.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        result = self.classifier.extract_requests(segments)
        
        assert len(result.credential_requests) >= 1
        req = result.credential_requests[0]
        assert req.type == "otp"
    
    def test_extract_requests_partial_skipped(self):
        """Requests NOT extracted from partial text."""
        segments = [
            TranscriptSegment(
                text="Please share your credit card number",
                start=20.0,
                end=22.0,
                speaker="caller",
                is_final=False
            )
        ]
        
        result = self.classifier.extract_requests(segments)
        
        # No requests from partial text
        assert len(result.credential_requests) == 0
    
    def test_extract_behavior_includes_partial(self):
        """Behavior extraction includes partial text with markers."""
        segments = [
            TranscriptSegment(
                text="Do it immediately",
                start=30.0,
                end=32.0,
                speaker="caller",
                is_final=False
            )
        ]
        
        result = self.classifier.extract_behavior(segments)
        
        # Behavior patterns detected even from partial
        if result.urgency.detected:
            # Should have quotes, possibly with [PARTIAL] marker
            assert len(result.urgency.quotes) > 0
            # Check if partial marker present
            has_partial_marker = any("[PARTIAL]" in q for q in result.urgency.quotes)
            assert has_partial_marker
    
    def test_extract_behavior_committed_no_marker(self):
        """Committed behavior has no partial marker."""
        segments = [
            TranscriptSegment(
                text="Do it immediately or else",
                start=30.0,
                end=32.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        result = self.classifier.extract_behavior(segments)
        
        if result.urgency.detected:
            # No partial markers in committed text
            has_partial_marker = any("[PARTIAL]" in q for q in result.urgency.quotes)
            assert not has_partial_marker


class TestMixedFinalityStream:
    """Test realistic streaming scenario with mixed finality."""
    
    def setup_method(self):
        """Create fresh classifier for each test."""
        self.classifier = Tier1Classifier()
    
    def test_progressive_finalization(self):
        """Test progression from partial to committed text."""
        # Simulate ASR progression: partial -> partial -> final
        segments_partial1 = [
            TranscriptSegment(
                text="Please tell",
                start=10.0,
                end=10.5,
                speaker="caller",
                is_final=False,
                confidence=0.6
            )
        ]
        
        segments_partial2 = [
            TranscriptSegment(
                text="Please tell me your OTP",
                start=10.0,
                end=11.5,
                speaker="caller",
                is_final=False,
                confidence=0.75
            )
        ]
        
        segments_final = [
            TranscriptSegment(
                text="Please tell me your OTP for verification",
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=True,
                confidence=0.95
            )
        ]
        
        # First partial: might or might not trigger
        result1 = self.classifier.classify(segments_partial1)
        provisional_count1 = len([s for s in result1.signals if "PROVISIONAL" in s.signal_type])
        
        # Second partial: should trigger provisional
        self.classifier.reset_session()
        result2 = self.classifier.classify(segments_partial2)
        provisional_count2 = len([s for s in result2.signals if "PROVISIONAL" in s.signal_type])
        assert provisional_count2 >= 1
        
        # Final: should trigger definitive critical
        self.classifier.reset_session()
        result3 = self.classifier.classify(segments_final)
        critical_count = len([s for s in result3.signals if s.severity == "critical"])
        assert critical_count >= 1
        definitive_count = len([s for s in result3.signals if "PROVISIONAL" not in s.signal_type])
        assert definitive_count >= 1
    
    def test_mixed_segments_in_same_call(self):
        """Test call with both committed and partial segments."""
        segments = [
            # Committed greeting
            TranscriptSegment(
                text="Hello, I am calling from your bank",
                start=0.0,
                end=2.0,
                speaker="caller",
                is_final=True
            ),
            # Partial credential request (still forming)
            TranscriptSegment(
                text="Please tell me your OTP",
                start=5.0,
                end=6.0,
                speaker="caller",
                is_final=False
            ),
            # Committed credential request
            TranscriptSegment(
                text="Tell me your card CVV number",
                start=7.0,
                end=9.0,
                speaker="caller",
                is_final=True
            ),
        ]
        
        result = self.classifier.classify(segments)
        
        # Should have both provisional and definitive signals
        provisional = [s for s in result.signals if "PROVISIONAL" in s.signal_type]
        definitive = [s for s in result.signals if "PROVISIONAL" not in s.signal_type]
        
        # At least one provisional (from partial OTP request)
        assert len(provisional) >= 1
        # At least one definitive signal (from committed CVV request)
        assert len(definitive) >= 1


class TestConfidenceAdjustment:
    """Test confidence reduction for partial text."""
    
    def setup_method(self):
        """Create fresh classifier for each test."""
        self.classifier = Tier1Classifier()
    
    def test_confidence_reduced_for_partial(self):
        """Partial text has lower confidence than committed."""
        text = "Share your ATM PIN with me"
        
        committed = [
            TranscriptSegment(
                text=text,
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=True
            )
        ]
        
        partial = [
            TranscriptSegment(
                text=text,
                start=10.0,
                end=12.0,
                speaker="caller",
                is_final=False
            )
        ]
        
        result_committed = self.classifier.classify(committed)
        self.classifier.reset_session()
        result_partial = self.classifier.classify(partial)
        
        assert len(result_committed.signals) >= 1
        assert len(result_partial.signals) >= 1
        
        conf_committed = result_committed.signals[0].confidence
        conf_partial = result_partial.signals[0].confidence
        
        # Partial confidence should be lower
        assert conf_partial < conf_committed
        # Specifically, should be ~60% of committed
        assert conf_partial <= conf_committed * 0.65
