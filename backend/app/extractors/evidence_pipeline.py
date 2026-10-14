"""
Evidence extraction pipeline for VISHWAS.

This module provides the main interface for converting transcript data
into structured evidence using the Tier 1 classifier.

Integration points:
- Accepts TranscriptResponse from M2's perception layer
- Produces EvidenceExtraction for M3's trust engine
- Preserves voice evidence from M2 without modification
- Handles streaming and batch processing modes

Privacy:
- Applies PII masking to all evidence quotes before storage
- Masked quotes sent to Tier 2 agents (never raw PII to LLM)
"""
import logging
from typing import Optional
from datetime import datetime

from app.schemas.report import TranscriptResponse, TranscriptSegment
from app.schemas.evidence import (
    EvidenceExtraction,
    ClaimsEvidence,
    RequestEvidence,
    BehaviorEvidence,
    VoiceEvidence,
    Tier1DetectionResult,
)
from app.extractors.tier1_classifier import Tier1Classifier
from app.extractors.pii_masker import get_pii_masker

logger = logging.getLogger(__name__)


def extract_evidence_from_transcript(
    transcript: TranscriptResponse,
    call_id: str,
    voice_evidence: Optional[VoiceEvidence] = None,
) -> EvidenceExtraction:
    """
    Extract structured evidence from transcript using Tier 1 classifier.
    
    This is the main entry point for evidence extraction in Phase 1.
    
    Args:
        transcript: Transcript response from M2's ASR
        call_id: Unique call identifier
        voice_evidence: Optional voice analysis from M2's voice layer
        
    Returns:
        EvidenceExtraction with all detected evidence
        
    Example:
        >>> transcript = TranscriptResponse(...)
        >>> evidence = extract_evidence_from_transcript(transcript, "call-123")
        >>> print(f"Found {len(evidence.claims.claims)} claims")
    """
    logger.info(f"Starting evidence extraction for call {call_id}")
    
    # Validate transcript
    if not transcript or not transcript.segments:
        logger.warning(f"Empty transcript for call {call_id}")
        return _create_empty_evidence(call_id, voice_evidence)
    
    # For completed transcripts, unspecified finality is committed
    if getattr(transcript, "transcription_status", None) == "completed":
        for seg in transcript.segments:
            if seg.is_final is None:
                seg.is_final = True

    # Initialize classifier and PII masker
    classifier = Tier1Classifier()
    classifier.reset_session()  # Ensure clean state
    pii_masker = get_pii_masker()
    
    # Extract evidence by category
    try:
        # Extract identity claims
        claims = classifier.extract_claims(transcript.segments)
        logger.info(f"Extracted {len(claims.claims)} claims")
        
        # Mask PII in claim quotes
        for claim in claims.claims:
            if claim.quote:
                claim.quote, _ = pii_masker.mask_text(claim.quote, audit=False)
        
        # Extract sensitive requests
        requests = classifier.extract_requests(transcript.segments)
        logger.info(
            f"Extracted {len(requests.money_requests)} money requests, "
            f"{len(requests.credential_requests)} credential requests"
        )
        
        # Mask PII in request quotes
        for req in requests.money_requests:
            if req.quote:
                req.quote, _ = pii_masker.mask_text(req.quote, audit=False)
        for req in requests.credential_requests:
            if req.quote:
                req.quote, _ = pii_masker.mask_text(req.quote, audit=False)
        
        # Extract behavioral evidence
        behavior = classifier.extract_behavior(transcript.segments)
        logger.info(
            f"Behavior detected - Urgency: {behavior.urgency.detected}, "
            f"Secrecy: {behavior.secrecy.detected}, "
            f"Emotional: {behavior.emotional_pressure.detected}"
        )
        
        # Mask PII in behavioral quotes
        behavior.urgency.quotes, _ = pii_masker.mask_segments(behavior.urgency.quotes)
        behavior.secrecy.quotes, _ = pii_masker.mask_segments(behavior.secrecy.quotes)
        behavior.emotional_pressure.quotes, _ = pii_masker.mask_segments(behavior.emotional_pressure.quotes)
        
        # Get Tier1 signals for tracking
        tier1_result = classifier.classify(transcript.segments)
        tier1_signals = [s.signal_type for s in tier1_result.signals]
        
        # Detect warnings
        warnings = _generate_warnings(transcript, claims, requests, behavior)
        
        # Build evidence extraction
        evidence = EvidenceExtraction(
            call_id=call_id,
            claims=claims,
            requests=requests,
            behavior=behavior,
            voice=voice_evidence,  # Pass through from M2
            extraction_timestamp=datetime.utcnow(),
            extractor_version="1.0-tier1",
            transcript_segments_analyzed=len(transcript.segments),
            language_detected=transcript.language,
            tier1_signals=tier1_signals,
            tier2_used=False,  # Phase 1: Tier 1 only
            fallback_used=False,  # Tier 1 is not a fallback
            extraction_warnings=warnings,
        )
        
        logger.info(f"Evidence extraction complete for call {call_id}")
        logger.info(f"Quality score: {evidence.evidence_quality_score:.2f}")
        logger.info(f"Red flags: {evidence.has_red_flags}")
        
        return evidence
        
    except Exception as e:
        logger.error(f"Evidence extraction failed for call {call_id}: {e}", exc_info=True)
        # Return empty evidence rather than failing
        return _create_empty_evidence(
            call_id,
            voice_evidence,
            warnings=[f"Extraction failed: {str(e)}"]
        )


def extract_evidence_streaming(
    segments: list[TranscriptSegment],
    call_id: str,
    session_classifier: Optional[Tier1Classifier] = None,
) -> Tier1DetectionResult:
    """
    Extract evidence from streaming transcript segments.
    
    Designed for real-time/live mode where segments arrive incrementally.
    Returns instant signals for immediate UI updates.
    
    Args:
        segments: New transcript segments (typically 1-2 segments per call)
        call_id: Unique call identifier
        session_classifier: Optional persistent classifier for session
        
    Returns:
        Tier1DetectionResult with instant signals
        
    Note:
        For streaming, maintain a session classifier instance to handle
        deduplication across chunks. Call reset_session() when starting
        a new call.
    """
    logger.debug(f"Streaming extraction for call {call_id}: {len(segments)} segments")
    
    # Use provided classifier or create new one
    classifier = session_classifier or Tier1Classifier()
    
    # Get instant signals
    result = classifier.classify(segments)
    
    if result.has_critical_signal:
        logger.warning(f"CRITICAL signal detected in streaming mode for call {call_id}")
    elif result.has_high_or_critical_signal:
        logger.info(f"HIGH signal detected in streaming mode for call {call_id}")
    
    return result


def _create_empty_evidence(
    call_id: str,
    voice_evidence: Optional[VoiceEvidence] = None,
    warnings: Optional[list[str]] = None,
) -> EvidenceExtraction:
    """Create empty evidence structure for error cases."""
    from app.schemas.evidence import (
        UrgencyEvidence,
        SecrecyEvidence,
        EmotionalPressureEvidence,
    )
    
    if warnings is None:
        warnings = ["Empty or invalid transcript"]
    
    return EvidenceExtraction(
        call_id=call_id,
        claims=ClaimsEvidence(claims=[], primary_claim=None, claim_changes=0),
        requests=RequestEvidence(),
        behavior=BehaviorEvidence(
            urgency=UrgencyEvidence(
                detected=False,
                quotes=[],
                timestamps=[],
                severity="low",
                patterns_found=[]
            ),
            secrecy=SecrecyEvidence(
                detected=False,
                quotes=[],
                timestamps=[],
                patterns_found=[]
            ),
            emotional_pressure=EmotionalPressureEvidence(
                detected=False,
                quotes=[],
                timestamps=[],
                pressure_types=[]
            ),
        ),
        voice=voice_evidence,
        extraction_timestamp=datetime.utcnow(),
        extractor_version="1.0-tier1",
        transcript_segments_analyzed=0,
        language_detected=None,
        tier1_signals=[],
        tier2_used=False,
        fallback_used=False,
        extraction_warnings=warnings,
    )


def _generate_warnings(
    transcript: TranscriptResponse,
    claims: ClaimsEvidence,
    requests: RequestEvidence,
    behavior: BehaviorEvidence,
) -> list[str]:
    """Generate warnings about extraction limitations."""
    warnings = []
    
    # Transcript quality warnings
    if transcript.is_mock:
        warnings.append("Using mock transcript data")
    
    if transcript.transcription_status != "completed":
        warnings.append(f"Transcript status: {transcript.transcription_status}")
    
    # Language warnings
    if transcript.language and transcript.language not in ["en", "hi", "hinglish"]:
        warnings.append(f"Limited support for language: {transcript.language}")
    
    # Segment warnings
    if len(transcript.segments) < 2:
        warnings.append("Very short transcript may limit detection accuracy")
    
    # Detection warnings - only add if truly no evidence
    if not claims.claims and not requests.has_sensitive_request and not behavior.has_pressure_tactics:
        warnings.append("No claims, requests, or pressure tactics detected")
    
    # Tier 1 limitations - removed misleading message about Tier 2
    # (Tier 2 is configurable via settings.tier2_enabled)
    
    return warnings


def get_extraction_summary(evidence: EvidenceExtraction) -> dict:
    """
    Generate a summary of extracted evidence for logging/debugging.
    
    Args:
        evidence: Evidence extraction result
        
    Returns:
        Dictionary with extraction summary
    """
    return {
        "call_id": evidence.call_id,
        "claims_count": len(evidence.claims.claims),
        "primary_claim": evidence.claims.primary_claim.value if evidence.claims.primary_claim else None,
        "money_requests": len(evidence.requests.money_requests),
        "credential_requests": len(evidence.requests.credential_requests),
        "max_money_amount": evidence.requests.max_money_amount,
        "urgency_detected": evidence.behavior.urgency.detected,
        "secrecy_detected": evidence.behavior.secrecy.detected,
        "pressure_detected": evidence.behavior.emotional_pressure.detected,
        "voice_status": evidence.voice.status if evidence.voice else "unavailable",
        "has_red_flags": evidence.has_red_flags,
        "quality_score": evidence.evidence_quality_score,
        "tier1_signals": len(evidence.tier1_signals),
        "segments_analyzed": evidence.transcript_segments_analyzed,
        "warnings": len(evidence.extraction_warnings),
    }
