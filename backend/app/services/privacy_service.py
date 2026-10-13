"""
Privacy Service for Phase 9: PII Protection and Data Sanitization

This service provides centralized PII protection across the application:
- Sanitizes transcripts before API responses
- Masks PII in evidence quotes
- Redacts sensitive data from logs
- Provides separate raw/sanitized data access policies

IMPORTANT: This does NOT alter stored data (database contains raw transcripts).
Masking is applied at the presentation layer for privacy-safe responses.
"""
import json
import logging
from typing import List, Dict, Optional, Any
from app.extractors.pii_masker import get_pii_masker

logger = logging.getLogger(__name__)


class PrivacyService:
    """
    Centralized privacy and PII protection service.
    
    Design principles:
    - Raw data stored in database for analysis and audit
    - Sanitized data returned in API responses by default
    - Masking preserves fraud detection context (keeps [MASKED_X] tokens)
    - Separate access policies for raw vs sanitized data
    """
    
    def __init__(self):
        """Initialize privacy service with PII masker."""
        self.pii_masker = get_pii_masker()
        logger.info("PrivacyService initialized")
    
    def sanitize_transcript_segments(
        self,
        segments: List[Dict[str, Any]],
        audit: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Sanitize transcript segments for API response.
        
        Masks PII in the 'text' field of each segment while preserving structure.
        
        Args:
            segments: List of transcript segment dictionaries
            audit: Whether to log masking statistics
            
        Returns:
            List of sanitized segments with masked PII
        """
        if not segments:
            return segments
        
        sanitized = []
        total_stats: Dict[str, int] = {}
        
        for segment in segments:
            # Create a copy to avoid modifying original
            sanitized_segment = segment.copy()
            
            # Mask PII in text field
            if "text" in segment and segment["text"]:
                masked_text, stats = self.pii_masker.mask_text(segment["text"], audit=False)
                sanitized_segment["text"] = masked_text
                
                # Aggregate stats
                for pii_type, count in stats.items():
                    total_stats[pii_type] = total_stats.get(pii_type, 0) + count
            
            sanitized.append(sanitized_segment)
        
        if audit and total_stats:
            logger.info(
                f"Sanitized {len(segments)} transcript segments, "
                f"masked {sum(total_stats.values())} PII instances: "
                f"{', '.join(f'{k}={v}' for k, v in total_stats.items())}"
            )
        
        return sanitized
    
    def sanitize_transcript_response(
        self,
        transcript_dict: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Sanitize complete transcript response.
        
        Args:
            transcript_dict: Transcript dictionary from database
            
        Returns:
            Sanitized transcript dictionary safe for API response
        """
        if not transcript_dict:
            return None
        
        # Create a copy
        sanitized = transcript_dict.copy()
        
        # Sanitize segments
        if "segments" in sanitized and sanitized["segments"]:
            sanitized["segments"] = self.sanitize_transcript_segments(
                sanitized["segments"],
                audit=True
            )
        
        return sanitized
    
    def sanitize_agent_findings(
        self,
        findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Sanitize agent findings for API response.
        
        Masks PII in evidence_text fields.
        
        Args:
            findings: List of agent finding dictionaries
            
        Returns:
            List of sanitized findings
        """
        if not findings:
            return findings
        
        sanitized = []
        
        for finding in findings:
            sanitized_finding = finding.copy()
            
            # Mask PII in evidence text
            if "evidence_text" in finding and finding["evidence_text"]:
                masked_text, _ = self.pii_masker.mask_text(finding["evidence_text"], audit=False)
                sanitized_finding["evidence_text"] = masked_text
            
            sanitized.append(sanitized_finding)
        
        return sanitized
    
    def sanitize_analysis_report(
        self,
        report_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Sanitize complete analysis report for API response.
        
        Applies PII masking to:
        - Transcript segments
        - Agent findings evidence text
        - Reasons (if they contain quotes)
        
        Args:
            report_dict: Report dictionary ready for serialization
            
        Returns:
            Sanitized report dictionary safe for API response
        """
        # Create a copy
        sanitized = report_dict.copy()
        
        # Sanitize transcript
        if "transcript" in sanitized and sanitized["transcript"]:
            transcript_data = sanitized["transcript"]
            if isinstance(transcript_data, dict) and "segments" in transcript_data:
                transcript_data["segments"] = self.sanitize_transcript_segments(
                    transcript_data["segments"],
                    audit=False
                )
        
        # Sanitize agent findings
        if "agent_findings" in sanitized and sanitized["agent_findings"]:
            sanitized["agent_findings"] = self.sanitize_agent_findings(
                sanitized["agent_findings"]
            )
        
        # Sanitize reasons (may contain quoted text with PII)
        if "reasons" in sanitized and sanitized["reasons"]:
            sanitized_reasons = []
            for reason in sanitized["reasons"]:
                if isinstance(reason, str):
                    masked_reason, _ = self.pii_masker.mask_text(reason, audit=False)
                    sanitized_reasons.append(masked_reason)
                else:
                    sanitized_reasons.append(reason)
            sanitized["reasons"] = sanitized_reasons
        
        logger.debug(f"Sanitized analysis report for call_id={sanitized.get('call_id')}")
        return sanitized
    
    def redact_for_logging(self, text: str, max_length: int = 100) -> str:
        """
        Redact sensitive data for safe logging.
        
        Masks PII and truncates to reasonable length for log entries.
        
        Args:
            text: Text to redact
            max_length: Maximum length for log output
            
        Returns:
            Redacted and truncated text safe for logging
        """
        if not text:
            return text
        
        # Mask PII
        masked, _ = self.pii_masker.mask_text(text, audit=False)
        
        # Truncate if needed
        if len(masked) > max_length:
            masked = masked[:max_length] + "..."
        
        return masked
    
    def is_sensitive_filename(self, filename: str) -> bool:
        """
        Check if filename might contain PII.
        
        Returns True if filename should be sanitized before logging.
        """
        if not filename:
            return False
        
        return self.pii_masker.is_sensitive(filename)
    
    def sanitize_error_message(self, error_msg: str) -> str:
        """
        Sanitize error messages before returning to client.
        
        Masks PII that might appear in error messages (e.g., from validation).
        
        Args:
            error_msg: Original error message
            
        Returns:
            Sanitized error message safe for client response
        """
        if not error_msg:
            return error_msg
        
        masked, _ = self.pii_masker.mask_text(error_msg, audit=False)
        return masked


# Singleton instance
_privacy_service_instance = None


def get_privacy_service() -> PrivacyService:
    """Get or create the global PrivacyService singleton."""
    global _privacy_service_instance
    if _privacy_service_instance is None:
        _privacy_service_instance = PrivacyService()
    return _privacy_service_instance


def sanitize_for_api(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to sanitize data for API response.
    
    Automatically detects and sanitizes analysis reports.
    """
    service = get_privacy_service()
    
    # Check if this is an analysis report
    if "transcript" in data or "agent_findings" in data:
        return service.sanitize_analysis_report(data)
    
    return data


def redact_for_log(text: str) -> str:
    """Convenience function to redact text for logging."""
    service = get_privacy_service()
    return service.redact_for_logging(text)
