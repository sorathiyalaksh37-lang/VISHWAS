"""
PII Masking Module for VISHWAS

Redacts personally identifiable information from transcripts before sending to LLM agents.

Privacy-first principle (§9): Transcripts may contain sensitive data (phone numbers,
account numbers, emails, names) that should NOT be sent to external LLM providers
without explicit user consent.

This module masks PII while preserving semantic meaning for fraud detection.
"""
import re
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

# PII detection patterns (conservative to avoid false positives)
# IMPORTANT: Patterns are applied in order defined below
PII_PATTERNS: Dict[str, Tuple[str, str]] = {
    # CVV/PIN/OTP (must come first, most specific)
    "cvv": (
        r"\b(?:cvv|pin|otp)(?:\s+(?:is|number|code))?[\s:]+\d{3,6}\b",
        "[MASKED_CVV]"
    ),
    
    # Credit card numbers (must have spaces or dashes, 16 digits total)
    "card": (
        r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}\b",
        "[MASKED_CARD]"
    ),
    
    # Aadhaar numbers (India) - 12 digits with spaces/dashes
    "aadhaar": (
        r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}\b",
        "[MASKED_AADHAAR]"
    ),
    
    # PAN numbers (India) - 5 letters, 4 digits, 1 letter
    "pan": (
        r"\b[A-Z]{5}\d{4}[A-Z]\b",
        "[MASKED_PAN]"
    ),
    
    # Phone numbers - various international formats
    # Matches: +91-9876543210, (555) 123-4567, +1 555 123 4567, 9876543210 (10 digits bare)
    # Priority: formatted phones, then 10-digit bare numbers (most common phone format)
    "phone": (
        r"(?:\+\d{1,3}[\s\-\.]\d{8,15}|\(\d{2,4}\)\s?\d{3,4}[\s\-\.]?\d{3,4}|\d{2,4}[\s\-\.]\d{3,4}[\s\-\.]\d{3,4}|\b\d{10}\b)",
        "[MASKED_PHONE]"
    ),
    
    # Bank account numbers (11-17 digits bare, NO spaces/dashes)
    # 10-digit numbers are treated as phones (more common), 11+ as account numbers
    "account": (
        r"\b\d{11,17}\b",
        "[MASKED_ACCOUNT]"
    ),
    
    # Email addresses
    "email": (
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "[MASKED_EMAIL]"
    ),
}


class PIIMasker:
    """
    Mask PII in transcript text while preserving fraud detection signals.
    
    Design principles:
    - Conservative masking: Better to over-mask than leak PII
    - Preserve context: Keep [MASKED_X] tokens so agents know sensitive data was requested
    - Fast: Compiled regex patterns for performance
    - Auditable: Log what was masked (counts, not values)
    """
    
    def __init__(self):
        """Initialize with compiled patterns."""
        self.compiled_patterns = {
            pii_type: (re.compile(pattern, re.IGNORECASE | re.UNICODE), replacement)
            for pii_type, (pattern, replacement) in PII_PATTERNS.items()
        }
        logger.info("PIIMasker initialized with %d pattern types", len(self.compiled_patterns))
    
    def mask_text(self, text: str, audit: bool = True) -> Tuple[str, Dict[str, int]]:
        """
        Mask PII in text, returning masked text and statistics.
        
        Args:
            text: Original text (transcript segment, evidence quote, etc.)
            audit: Whether to log masking statistics
            
        Returns:
            Tuple of (masked_text, stats_dict)
            
        Example:
            >>> masker = PIIMasker()
            >>> masked, stats = masker.mask_text("Call me at +91-9876543210 or email john@example.com")
            >>> print(masked)
            "Call me at [MASKED_PHONE] or email [MASKED_EMAIL]"
            >>> print(stats)
            {"phone": 1, "email": 1}
        """
        if not text:
            return text, {}
        
        masked_text = text
        stats: Dict[str, int] = {}
        
        # Apply each pattern in order
        for pii_type, (pattern, replacement) in self.compiled_patterns.items():
            matches = pattern.findall(masked_text)
            if matches:
                stats[pii_type] = len(matches)
                masked_text = pattern.sub(replacement, masked_text)
        
        if audit and stats:
            total_masked = sum(stats.values())
            logger.info(
                "Masked %d PII instances: %s",
                total_masked,
                ", ".join(f"{k}={v}" for k, v in stats.items())
            )
        
        return masked_text, stats
    
    def mask_segments(self, segments: List[str]) -> Tuple[List[str], Dict[str, int]]:
        """
        Mask PII across multiple text segments.
        
        Args:
            segments: List of text segments (e.g. transcript segments)
            
        Returns:
            Tuple of (masked_segments, aggregate_stats)
        """
        masked_segments = []
        aggregate_stats: Dict[str, int] = {}
        
        for segment in segments:
            masked, stats = self.mask_text(segment, audit=False)
            masked_segments.append(masked)
            
            # Aggregate stats
            for pii_type, count in stats.items():
                aggregate_stats[pii_type] = aggregate_stats.get(pii_type, 0) + count
        
        if aggregate_stats:
            total = sum(aggregate_stats.values())
            logger.info(
                "Masked %d PII instances across %d segments: %s",
                total,
                len(segments),
                ", ".join(f"{k}={v}" for k, v in aggregate_stats.items())
            )
        
        return masked_segments, aggregate_stats
    
    def is_sensitive(self, text: str) -> bool:
        """
        Quick check if text contains any PII patterns.
        
        Useful for pre-filtering before expensive operations.
        """
        if not text:
            return False
        
        for pattern, _ in self.compiled_patterns.values():
            if pattern.search(text):
                return True
        
        return False


# Singleton instance
_pii_masker_instance = None


def get_pii_masker() -> PIIMasker:
    """Get or create the global PIIMasker singleton."""
    global _pii_masker_instance
    if _pii_masker_instance is None:
        _pii_masker_instance = PIIMasker()
    return _pii_masker_instance


def mask_pii(text: str) -> str:
    """
    Convenience function to mask PII in a single text string.
    
    Args:
        text: Text to mask
        
    Returns:
        Masked text with [MASKED_X] tokens
    """
    masker = get_pii_masker()
    masked, _ = masker.mask_text(text)
    return masked


def mask_pii_in_evidence_quotes(quotes: List[str]) -> List[str]:
    """
    Mask PII in evidence quote arrays.
    
    Designed for use with evidence extraction output before agent calls.
    """
    if not quotes:
        return quotes
    
    masker = get_pii_masker()
    masked_quotes, _ = masker.mask_segments(quotes)
    return masked_quotes
