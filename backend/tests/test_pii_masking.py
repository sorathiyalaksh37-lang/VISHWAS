"""
Tests for PII masking module.

Ensures sensitive data is properly redacted before LLM calls.
"""
import pytest
from app.extractors.pii_masker import PIIMasker, get_pii_masker, mask_pii


class TestPIIMasker:
    """Test PII detection and masking."""
    
    def test_mask_phone_numbers(self):
        """Test phone number masking in various formats."""
        masker = PIIMasker()
        
        test_cases = [
            ("+91-9876543210", "[MASKED_PHONE]"),
            ("Call me at 9876543210", "Call me at [MASKED_PHONE]"),
            ("My number is +1 (555) 123-4567", "My number is [MASKED_PHONE]"),
            ("+44 20 7946 0958", "[MASKED_PHONE]"),
        ]
        
        for original, expected in test_cases:
            masked, stats = masker.mask_text(original, audit=False)
            assert "[MASKED_PHONE]" in masked, f"Failed to mask: {original}"
            assert stats.get("phone", 0) >= 1
    
    def test_mask_emails(self):
        """Test email masking."""
        masker = PIIMasker()
        
        text = "Contact me at john.doe@example.com or support@bank.co.in"
        masked, stats = masker.mask_text(text, audit=False)
        
        assert "john.doe@example.com" not in masked
        assert "support@bank.co.in" not in masked
        assert masked.count("[MASKED_EMAIL]") == 2
        assert stats["email"] == 2
    
    def test_mask_credit_cards(self):
        """Test credit card number masking."""
        masker = PIIMasker()
        
        test_cases = [
            "My card is 1234 5678 9012 3456",
            "Card: 1234-5678-9012-3456",
        ]
        
        for text in test_cases:
            masked, stats = masker.mask_text(text, audit=False)
            assert "[MASKED_CARD]" in masked
            assert stats.get("card", 0) >= 1
    
    def test_mask_account_numbers(self):
        """Test bank account number masking."""
        masker = PIIMasker()
        
        text = "Transfer to account 1234567890123"
        masked, stats = masker.mask_text(text, audit=False)
        
        assert "1234567890123" not in masked
        assert "[MASKED_ACCOUNT]" in masked
        assert stats.get("account", 0) >= 1
    
    def test_mask_cvv_pin_otp(self):
        """Test CVV/PIN/OTP masking."""
        masker = PIIMasker()
        
        test_cases = [
            "Enter CVV: 123",
            "Your PIN is 4567",
            "OTP 123456",
            "cvv 987",
        ]
        
        for text in test_cases:
            masked, _ = masker.mask_text(text, audit=False)
            # Should not contain the numeric part after keyword
            assert "123" not in masked or "[MASKED" in masked
    
    def test_mask_aadhaar(self):
        """Test Aadhaar number masking (India)."""
        masker = PIIMasker()
        
        text = "My Aadhaar is 1234 5678 9012"
        masked, stats = masker.mask_text(text, audit=False)
        
        assert "1234 5678 9012" not in masked
        assert "[MASKED_AADHAAR]" in masked
    
    def test_mask_pan(self):
        """Test PAN number masking (India)."""
        masker = PIIMasker()
        
        text = "PAN: ABCDE1234F"
        masked, stats = masker.mask_text(text, audit=False)
        
        assert "ABCDE1234F" not in masked
        assert "[MASKED_PAN]" in masked
        assert stats["pan"] == 1
    
    def test_preserve_context(self):
        """Test that masking preserves semantic context."""
        masker = PIIMasker()
        
        text = "Please share your OTP 123456 immediately to verify your bank account 9876543210123."
        masked, _ = masker.mask_text(text, audit=False)
        
        # Context words should remain
        assert "share" in masked
        assert "immediately" in masked
        assert "verify" in masked
        assert "bank account" in masked
        
        # But sensitive data masked
        assert "9876543210123" not in masked
        assert "[MASKED_" in masked
    
    def test_multiple_pii_types(self):
        """Test masking multiple PII types in one text."""
        masker = PIIMasker()
        
        text = (
            "Hi, I'm calling from State Bank. "
            "Please confirm your account 1234567890123, "
            "card number 1234-5678-9012-3456, "
            "and email john@example.com."
        )
        
        masked, stats = masker.mask_text(text, audit=False)
        
        # Should mask card, email, and account
        assert stats.get("card", 0) >= 1
        assert stats.get("email", 0) >= 1
        assert stats.get("account", 0) >= 1
        
        # Original values should not appear
        assert "john@example.com" not in masked
    
    def test_mask_segments(self):
        """Test masking across multiple segments."""
        masker = PIIMasker()
        
        segments = [
            "Call me later.",
            "Or email support@bank.com.",
            "My account is 1234567890.",
        ]
        
        masked_segments, stats = masker.mask_segments(segments)
        
        assert len(masked_segments) == 3
        assert stats.get("email", 0) >= 1
        assert stats.get("account", 0) >= 1
        
        # Original data should not appear in any segment
        for segment in masked_segments:
            assert "support@bank.com" not in segment
    
    def test_is_sensitive(self):
        """Test quick PII detection."""
        masker = PIIMasker()
        
        assert masker.is_sensitive("+91-9876543210") is True
        assert masker.is_sensitive("john@example.com") is True
        assert masker.is_sensitive("Hello, how are you?") is False
        assert masker.is_sensitive("") is False
    
    def test_empty_input(self):
        """Test handling of empty input."""
        masker = PIIMasker()
        
        masked, stats = masker.mask_text("")
        assert masked == ""
        assert stats == {}
        
        masked, stats = masker.mask_text(None)
        assert masked is None
        assert stats == {}
    
    def test_no_pii(self):
        """Test text with no PII."""
        masker = PIIMasker()
        
        text = "This is a normal conversation about the weather."
        masked, stats = masker.mask_text(text, audit=False)
        
        assert masked == text
        assert stats == {}
    
    def test_singleton(self):
        """Test singleton pattern."""
        m1 = get_pii_masker()
        m2 = get_pii_masker()
        assert m1 is m2
    
    def test_convenience_function(self):
        """Test mask_pii convenience function."""
        text = "Email test@example.com for help"
        masked = mask_pii(text)
        
        assert "test@example.com" not in masked
        assert "[MASKED_EMAIL]" in masked


class TestRealWorldScenarios:
    """Test PII masking in realistic fraud scenarios."""
    
    def test_bank_fraud_scenario(self):
        """Test typical bank fraud call transcript."""
        masker = PIIMasker()
        
        transcript = (
            "Hello sir, I'm calling from HDFC Bank security department. "
            "We've detected suspicious activity on your account 1234567890123. "
            "Please verify your card number 1234-5678-9012-3456 and CVV 456. "
            "We'll send an OTP to your registered mobile +91-9876543210. "
            "Don't share this OTP with anyone, but tell me when you receive it."
        )
        
        masked, stats = masker.mask_text(transcript, audit=False)
        
        # All sensitive data should be masked
        assert "1234567890123" not in masked
        assert "1234-5678-9012-3456" not in masked
        assert "9876543210" not in masked
        assert "456" not in masked or "[MASKED" in masked
        
        # Context preserved for fraud detection
        assert "HDFC Bank" in masked
        assert "security department" in masked
        assert "suspicious activity" in masked
        assert "verify" in masked
        assert "OTP" in masked
        assert "Don't share" in masked
        
        # Multiple PII types detected
        assert len(stats) >= 3
    
    def test_impersonation_scenario(self):
        """Test family impersonation with money request."""
        masker = PIIMasker()
        
        transcript = (
            "Hi Mom, it's me. I'm in trouble and need ₹50,000 urgently. "
            "Please transfer to account 9876543210123 immediately. "
            "Don't tell Dad. Call me back at +91-8765432109 if you have any questions. "
            "This is my new number."
        )
        
        masked, stats = masker.mask_text(transcript, audit=False)
        
        # Phone and account masked
        assert "9876543210123" not in masked
        assert "8765432109" not in masked
        
        # Fraud indicators preserved
        assert "trouble" in masked
        assert "urgently" in masked
        assert "Don't tell Dad" in masked
        assert "₹50,000" in masked  # Amount not PII, should remain
    
    def test_legitimate_call_scenario(self):
        """Test that legitimate calls without PII pass through."""
        masker = PIIMasker()
        
        transcript = (
            "Hi dear, how are you? "
            "I wanted to check if you're free for dinner tomorrow. "
            "Let me know what time works for you."
        )
        
        masked, stats = masker.mask_text(transcript, audit=False)
        
        # No masking should occur
        assert masked == transcript
        assert stats == {}
