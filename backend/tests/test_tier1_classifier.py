"""
Unit tests for Tier 1 classifier.

Tests cover:
- Positive cases (fraud signals)
- Negative cases (legitimate conversations)
- Negation detection
- Edge cases and data quality
- Deduplication
- Language support
"""
import pytest
from app.schemas.report import TranscriptSegment
from app.extractors.tier1_classifier import Tier1Classifier


class TestTier1CredentialDetection:
    """Test credential request detection."""
    
    def test_otp_request_detected(self):
        """Should detect OTP disclosure request."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=5.0,
                end=8.0,
                speaker="caller",
                text="Please tell me your OTP to verify your account", is_final=True
            )
        ]
        
        result = classifier.classify(segments)
        
        assert len(result.signals) > 0
        assert any("OTP" in s.signal_type for s in result.signals)
        assert result.highest_severity == "critical"
        assert result.has_critical_signal
    
    def test_pin_request_detected(self):
        """Should detect PIN disclosure request."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=10.0,
                end=13.0,
                speaker="caller",
                text="Enter your ATM PIN to complete the transaction", is_final=True
            )
        ]
        
        result = classifier.classify(segments)
        
        assert len(result.signals) > 0
        assert any("PIN" in s.signal_type for s in result.signals)
        assert result.highest_severity == "critical"
    
    def test_password_request_detected(self):
        """Should detect password disclosure request."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=15.0,
                end=18.0,
                speaker="caller",
                text="What is your account password for verification?", is_final=True
            )
        ]
        
        result = classifier.classify(segments)
        
        assert len(result.signals) > 0
        assert any("PASSWORD" in s.signal_type for s in result.signals)
        assert result.highest_severity == "critical"
    
    def test_hindi_otp_request(self):
        """Should detect Hindi/Hinglish OTP request."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=5.0,
                end=8.0,
                speaker="caller",
                text="OTP bata do jaldi please", is_final=True
            )
        ]
        
        result = classifier.classify(segments)
        
        assert len(result.signals) > 0
        assert any("OTP" in s.signal_type for s in result.signals)
        assert result.highest_severity == "critical"


class TestTier1MoneyDetection:
    """Test money request detection."""
    
    def test_money_request_detected(self):
        """Should detect money transfer request."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=20.0,
                end=23.0,
                speaker="caller",
                text="Please send 50000 rupees immediately", is_final=True
            )
        ]
        
        result = classifier.classify(segments)
        
        assert len(result.signals) > 0
        assert any("MONEY" in s.signal_type for s in result.signals)
        assert result.highest_severity in ["high", "critical"]
    
    def test_hindi_money_request(self):
        """Should detect Hindi money request."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=25.0,
                end=28.0,
                speaker="caller",
                text="50000 rupaye bhej do turant", is_final=True
            )
        ]
        
        result = classifier.classify(segments)
        
        assert len(result.signals) > 0
        assert any("MONEY" in s.signal_type for s in result.signals)
    
    def test_extract_money_amount(self):
        """Should extract money request with amount."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=20.0,
                end=23.0,
                speaker="caller",
                text="Transfer 25000 rupees to my account", is_final=True
            )
        ]
        
        requests = classifier.extract_requests(segments)
        
        assert len(requests.money_requests) > 0
        assert requests.money_requests[0].amount == 25000.0
        assert requests.max_money_amount == 25000.0


class TestTier1NegationDetection:
    """Test negation detection to avoid false positives."""
    
    def test_negated_otp_warning_not_detected(self):
        """Should NOT detect negated OTP warning as request."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=5.0,
                end=8.0,
                speaker="caller",
                text="Never share your OTP with anyone", is_final=True
            )
        ]
        
        result = classifier.classify(segments)
        
        # Should have few or no critical signals (negation should filter it)
        critical_signals = [s for s in result.signals if s.severity == "critical"]
        assert len(critical_signals) == 0
    
    def test_negated_password_advice(self):
        """Should NOT detect password security advice as request."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=10.0,
                end=13.0,
                speaker="caller",
                text="Don't tell anyone your password", is_final=True
            )
        ]
        
        result = classifier.classify(segments)
        
        critical_signals = [s for s in result.signals if s.severity == "critical"]
        assert len(critical_signals) == 0
    
    def test_hindi_negation(self):
        """Should detect Hindi negation."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=5.0,
                end=8.0,
                speaker="caller",
                text="OTP kisi ko mat batana", is_final=True
            )
        ]
        
        result = classifier.classify(segments)
        
        critical_signals = [s for s in result.signals if s.severity == "critical"]
        assert len(critical_signals) == 0


class TestTier1ClaimExtraction:
    """Test identity claim extraction."""
    
    def test_relative_claim_detected(self):
        """Should detect relative identity claim."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=2.0,
                end=5.0,
                speaker="caller",
                text="I am your mother calling from a new number", is_final=True
            )
        ]
        
        claims = classifier.extract_claims(segments)
        
        assert len(claims.claims) > 0
        assert claims.claims[0].type == "relative"
        assert "mother" in claims.claims[0].value
        assert claims.primary_claim is not None
    
    def test_hindi_relative_claim(self):
        """Should detect Hindi relative claim."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=2.0,
                end=5.0,
                speaker="caller",
                text="Mummy bol rahi hoon beta", is_final=True
            )
        ]
        
        claims = classifier.extract_claims(segments)
        
        assert len(claims.claims) > 0
        assert claims.claims[0].type == "relative"
        assert "mother" in claims.claims[0].value
    
    def test_bank_claim_detected(self):
        """Should detect bank organization claim."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=2.0,
                end=5.0,
                speaker="caller",
                text="I am calling from HDFC bank regarding your account", is_final=True
            )
        ]
        
        claims = classifier.extract_claims(segments)
        
        assert len(claims.claims) > 0
        assert claims.claims[0].type == "organization"
        assert "bank" in claims.claims[0].value.lower()
    
    def test_police_claim_detected(self):
        """Should detect police authority claim."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=2.0,
                end=5.0,
                speaker="caller",
                text="This is Inspector Kumar from the police station", is_final=True
            )
        ]
        
        claims = classifier.extract_claims(segments)
        
        assert len(claims.claims) > 0
        assert claims.claims[0].type == "authority"
        assert "police" in claims.claims[0].value


class TestTier1BehaviorExtraction:
    """Test behavioral evidence extraction."""
    
    def test_urgency_detected(self):
        """Should detect urgency patterns."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=10.0,
                end=13.0,
                speaker="caller",
                text="This is urgent! You must act immediately or your account will be blocked", is_final=True
            )
        ]
        
        behavior = classifier.extract_behavior(segments)
        
        assert behavior.urgency.detected
        assert len(behavior.urgency.quotes) > 0
        assert behavior.urgency.severity in ["medium", "high"]
    
    def test_secrecy_detected(self):
        """Should detect secrecy patterns."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=15.0,
                end=18.0,
                speaker="caller",
                text="Don't tell anyone about this transaction", is_final=True
            )
        ]
        
        behavior = classifier.extract_behavior(segments)
        
        assert behavior.secrecy.detected
        assert len(behavior.secrecy.quotes) > 0
    
    def test_hindi_secrecy(self):
        """Should detect Hindi secrecy patterns."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=15.0,
                end=18.0,
                speaker="caller",
                text="Kisi ko mat batana yeh baat", is_final=True
            )
        ]
        
        behavior = classifier.extract_behavior(segments)
        
        assert behavior.secrecy.detected
    
    def test_threat_detected(self):
        """Should detect threat patterns."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=10.0,
                end=13.0,
                speaker="caller",
                text="Legal action will be taken against you if you don't pay", is_final=True
            )
        ]
        
        behavior = classifier.extract_behavior(segments)
        
        assert behavior.urgency.detected
        assert "threat" in behavior.urgency.patterns_found or behavior.urgency.severity == "high"


class TestTier1EdgeCases:
    """Test edge cases and data quality handling."""
    
    def test_empty_segments(self):
        """Should handle empty segment list."""
        classifier = Tier1Classifier()
        segments = []
        
        result = classifier.classify(segments)
        
        assert result.signals == []
        assert result.highest_severity is None
        assert result.detection_time_ms >= 0
    
    def test_empty_text_segments(self):
        """Should handle segments with empty text."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(start=1.0, end=2.0, speaker="caller", text="", is_final=True),
            TranscriptSegment(start=2.0, end=3.0, speaker="caller", text="   ", is_final=True),
        ]
        
        result = classifier.classify(segments)
        
        assert result.signals == []
    
    def test_deduplication_same_segment(self):
        """Should deduplicate repeated segments."""
        classifier = Tier1Classifier()
        classifier.reset_session()
        
        # Same segment processed twice
        segment = TranscriptSegment(
            start=5.0,
            end=8.0,
            speaker="caller",
            text="Tell me your OTP", is_final=True
        )
        
        result1 = classifier.classify([segment])
        count1 = len(result1.signals)
        
        result2 = classifier.classify([segment])
        count2 = len(result2.signals)
        
        # Second pass should find 0 new signals (deduplication)
        assert count2 == 0
    
    def test_multiple_patterns_in_segment(self):
        """Should detect multiple patterns in one segment."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=10.0,
                end=15.0,
                speaker="caller",
                text="Tell me your OTP and send 50000 rupees immediately", is_final=True
            )
        ]
        
        result = classifier.classify(segments)
        
        # Should detect both OTP request and money request
        assert len(result.signals) >= 2
        signal_types = [s.signal_type for s in result.signals]
        assert any("OTP" in st for st in signal_types)
        assert any("MONEY" in st for st in signal_types)
    
    def test_session_reset(self):
        """Should reset deduplication on session reset."""
        classifier = Tier1Classifier()
        
        segment = TranscriptSegment(
            start=5.0,
            end=8.0,
            speaker="caller",
            text="Tell me your OTP", is_final=True
        )
        
        result1 = classifier.classify([segment])
        count1 = len(result1.signals)
        
        classifier.reset_session()
        
        result2 = classifier.classify([segment])
        count2 = len(result2.signals)
        
        # After reset, should detect again
        assert count2 == count1


class TestTier1LegitimateConversations:
    """Test that legitimate conversations don't trigger false positives."""
    
    def test_bank_mention_not_claim(self):
        """Mentioning a bank shouldn't always be a claim."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=5.0,
                end=8.0,
                speaker="caller",
                text="I went to the bank yesterday to deposit money", is_final=True
            )
        ]
        
        result = classifier.classify(segments)
        
        # Might detect "bank" mention but shouldn't be high severity
        high_signals = [s for s in result.signals if s.severity in ["high", "critical"]]
        assert len(high_signals) == 0
    
    def test_past_money_transfer_not_request(self):
        """Description of past transfer shouldn't be flagged as request."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=10.0,
                end=13.0,
                speaker="caller",
                text="I sent you 5000 rupees last week", is_final=True
            )
        ]
        
        result = classifier.classify(segments)
        
        # May detect money mention but context suggests past tense
        # Should not be high severity request
        critical_signals = [s for s in result.signals if s.severity == "critical"]
        assert len(critical_signals) == 0
    
    def test_educational_otp_discussion(self):
        """Educational discussion about OTPs shouldn't trigger."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=5.0,
                end=8.0,
                speaker="caller",
                text="OTP security is important for banking", is_final=True
            )
        ]
        
        result = classifier.classify(segments)
        
        # Might mention OTP but no request context
        critical_signals = [s for s in result.signals if s.severity == "critical"]
        assert len(critical_signals) == 0
    
    def test_normal_urgency_not_threat(self):
        """Normal urgency in legitimate context shouldn't be flagged."""
        classifier = Tier1Classifier()
        segments = [
            TranscriptSegment(
                start=10.0,
                end=13.0,
                speaker="caller",
                text="We need to finish this now before the meeting", is_final=True
            )
        ]
        
        result = classifier.classify(segments)
        
        # Might detect "now" but context is legitimate
        # Should be low severity at most
        high_signals = [s for s in result.signals if s.severity in ["high", "critical"]]
        assert len(high_signals) == 0


class TestTier1LanguageDetection:
    """Test language detection helper."""
    
    def test_detect_english(self):
        """Should detect English."""
        classifier = Tier1Classifier()
        lang = classifier._detect_language("Please send me the money")
        assert lang == "en"
    
    def test_detect_hinglish(self):
        """Should detect Hinglish."""
        classifier = Tier1Classifier()
        lang = classifier._detect_language("Aap mujhe paisa bhej do")
        assert lang == "hinglish"
    
    def test_detect_hindi_script(self):
        """Should detect Hindi script."""
        classifier = Tier1Classifier()
        lang = classifier._detect_language("आप मुझे पैसा भेज दो")
        assert lang == "hi"


class TestTier1AmountExtraction:
    """Test amount extraction from text."""
    
    def test_extract_simple_amount(self):
        """Should extract simple numeric amount."""
        classifier = Tier1Classifier()
        amount = classifier._extract_amount("send 5000 rupees")
        assert amount == 5000.0
    
    def test_extract_comma_separated_amount(self):
        """Should handle Indian comma-separated amounts."""
        classifier = Tier1Classifier()
        
        # Indian format: 1,50,000
        amount = classifier._extract_amount("transfer 1,50,000 rupees")
        assert amount == 150000.0
        
        # Indian format: 12,50,000
        amount2 = classifier._extract_amount("send 12,50,000 immediately")
        assert amount2 == 1250000.0
    
    def test_extract_western_comma_amount(self):
        """Should handle Western comma-separated amounts."""
        classifier = Tier1Classifier()
        
        # Western format: 150,000
        amount = classifier._extract_amount("transfer 150,000 rupees")
        assert amount == 150000.0
        
        # Western format: 1,500
        amount2 = classifier._extract_amount("send 1,500 rupees")
        assert amount2 == 1500.0
    
    def test_extract_currency_prefix_amounts(self):
        """Should handle currency prefixes."""
        classifier = Tier1Classifier()
        
        # Rupee symbol
        amount1 = classifier._extract_amount("send ₹25,000 now")
        assert amount1 == 25000.0
        
        # Rs. prefix
        amount2 = classifier._extract_amount("transfer Rs. 1,50,000")
        assert amount2 == 150000.0
        
        # INR prefix
        amount3 = classifier._extract_amount("pay INR 50000")
        assert amount3 == 50000.0
    
    def test_extract_decimal_amounts(self):
        """Should handle decimal amounts when part of larger pattern."""
        classifier = Tier1Classifier()
        
        # Decimal extraction works with currency markers
        amount = classifier._extract_amount("send ₹1500.50 rupees")
        assert amount in [1500.50, 1500.0]  # Either is acceptable
        
        # Plain numbers are extracted (decimal part may be optional)
        amount2 = classifier._extract_amount("transfer 25000.00")
        assert amount2 == 25000.0
    
    def test_extract_no_amount(self):
        """Should return None when no amount found."""
        classifier = Tier1Classifier()
        amount = classifier._extract_amount("send some money")
        assert amount is None
        
        # Small numbers (< 100) should not be extracted to avoid false positives
        amount2 = classifier._extract_amount("call me at 9 PM")
        assert amount2 is None
