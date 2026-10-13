"""
Tier 1 Rule-Based Classifier for VISHWAS.

This classifier uses deterministic pattern matching to detect potential fraud signals
in transcript text. It operates entirely offline without LLM or external API calls.

Key responsibilities:
- Process transcript segments
- Apply categorized detection patterns
- Generate structured evidence candidates
- Handle negation and false positives
- Support streaming/chunked input with deduplication
"""
import re
import time
import logging
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict

from app.schemas.report import TranscriptSegment
from app.schemas.evidence import (
    ClaimEvidence,
    ClaimsEvidence,
    MoneyRequest,
    CredentialRequest,
    ActionRequest,
    RequestEvidence,
    UrgencyEvidence,
    SecrecyEvidence,
    EmotionalPressureEvidence,
    BehaviorEvidence,
    Tier1Signal,
    Tier1DetectionResult,
)
from app.extractors.patterns import DetectionPatterns

logger = logging.getLogger(__name__)


class Tier1Classifier:
    """
    Rule-based classifier for instant fraud signal detection.
    
    Design principles:
    - Deterministic: same input always produces same output
    - Offline: no external dependencies
    - Conservative: avoids false positives through negation checking
    - Traceable: preserves quotes, timestamps, and pattern IDs
    - Streaming-ready: handles partial and overlapping segments
    """
    
    def __init__(self):
        """Initialize classifier with compiled patterns."""
        # Compile all patterns at initialization
        self.identity_patterns = DetectionPatterns.compile_pattern_dict(
            DetectionPatterns.IDENTITY_CLAIMS
        )
        self.credential_patterns = DetectionPatterns.compile_pattern_dict(
            DetectionPatterns.CREDENTIAL_REQUESTS
        )
        self.money_patterns = DetectionPatterns.compile_patterns(
            DetectionPatterns.MONEY_REQUESTS
        )
        self.urgency_patterns = DetectionPatterns.compile_patterns(
            DetectionPatterns.URGENCY_PATTERNS
        )
        self.secrecy_patterns = DetectionPatterns.compile_patterns(
            DetectionPatterns.SECRECY_PATTERNS
        )
        self.emotional_patterns = DetectionPatterns.compile_pattern_dict(
            DetectionPatterns.EMOTIONAL_PRESSURE
        )
        
        # Deduplication tracking for streaming
        self._seen_evidence: Set[str] = set()
        
        logger.info("Tier1Classifier initialized with compiled patterns")
    
    def classify(self, segments: List[TranscriptSegment]) -> Tier1DetectionResult:
        """
        Classify transcript segments and generate instant signals.
        
        Args:
            segments: List of transcript segments with text and timestamps
            
        Returns:
            Tier1DetectionResult with detected signals
        """
        start_time = time.time()
        signals: List[Tier1Signal] = []
        
        for segment in segments:
            if not segment.text or not segment.text.strip():
                continue
            
            # Detect all signal types for this segment
            segment_signals = self._detect_segment_signals(segment)
            signals.extend(segment_signals)
        
        # Calculate detection time
        detection_time_ms = (time.time() - start_time) * 1000
        
        # Determine highest severity
        severities = [s.severity for s in signals]
        highest = None
        if severities:
            if "critical" in severities:
                highest = "critical"
            elif "high" in severities:
                highest = "high"
            elif "medium" in severities:
                highest = "medium"
            elif "low" in severities:
                highest = "low"
        
        result = Tier1DetectionResult(
            signals=signals,
            highest_severity=highest,
            detection_time_ms=detection_time_ms
        )
        
        logger.info(f"Tier1 classification complete: {len(signals)} signals, {detection_time_ms:.2f}ms")
        return result
    
    def _detect_segment_signals(self, segment: TranscriptSegment) -> List[Tier1Signal]:
        """Detect all signals in a single segment."""
        signals = []
        text = segment.text
        timestamp = segment.start
        
        # Check for credential requests (CRITICAL)
        cred_signals = self._detect_credential_requests(text, timestamp)
        signals.extend(cred_signals)
        
        # Check for money requests (HIGH)
        money_signals = self._detect_money_requests(text, timestamp)
        signals.extend(money_signals)
        
        # Check for urgency (MEDIUM/HIGH)
        urgency_signals = self._detect_urgency(text, timestamp)
        signals.extend(urgency_signals)
        
        # Check for secrecy (MEDIUM)
        secrecy_signals = self._detect_secrecy(text, timestamp)
        signals.extend(secrecy_signals)
        
        return signals
    
    def _detect_credential_requests(self, text: str, timestamp: float) -> List[Tier1Signal]:
        """Detect credential disclosure requests."""
        signals = []
        
        for cred_type, patterns in self.credential_patterns.items():
            for pattern, pattern_id, confidence in patterns:
                for match in pattern.finditer(text):
                    # Check for negation
                    if DetectionPatterns.check_negation(text, match.start()):
                        logger.debug(f"Negated match for {pattern_id}: {match.group()}")
                        continue
                    
                    quote = match.group().strip()
                    
                    # Deduplication check
                    dedup_key = f"{cred_type}:{quote}:{timestamp}"
                    if dedup_key in self._seen_evidence:
                        continue
                    self._seen_evidence.add(dedup_key)
                    
                    signal = Tier1Signal(
                        signal_type=f"CREDENTIAL_REQUEST_{cred_type.upper()}",
                        severity="critical",
                        quote=quote,
                        t=timestamp,
                        pattern_matched=pattern_id,
                        confidence=confidence
                    )
                    signals.append(signal)
                    logger.info(f"CRITICAL: Credential request detected - {cred_type} at {timestamp}s")
        
        return signals
    
    def _detect_money_requests(self, text: str, timestamp: float) -> List[Tier1Signal]:
        """Detect money transfer requests."""
        signals = []
        
        for pattern, pattern_id, confidence in self.money_patterns:
            for match in pattern.finditer(text):
                # Check for negation
                if DetectionPatterns.check_negation(text, match.start()):
                    continue
                
                quote = match.group().strip()
                
                # Deduplication
                dedup_key = f"money:{quote}:{timestamp}"
                if dedup_key in self._seen_evidence:
                    continue
                self._seen_evidence.add(dedup_key)
                
                signal = Tier1Signal(
                    signal_type="MONEY_REQUEST",
                    severity="high",
                    quote=quote,
                    t=timestamp,
                    pattern_matched=pattern_id,
                    confidence=confidence
                )
                signals.append(signal)
                logger.info(f"HIGH: Money request detected at {timestamp}s")
        
        return signals
    
    def _detect_urgency(self, text: str, timestamp: float) -> List[Tier1Signal]:
        """Detect urgency and pressure tactics."""
        signals = []
        
        for pattern, pattern_id, confidence in self.urgency_patterns:
            for match in pattern.finditer(text):
                quote = match.group().strip()
                
                # Deduplication
                dedup_key = f"urgency:{quote}:{timestamp}"
                if dedup_key in self._seen_evidence:
                    continue
                self._seen_evidence.add(dedup_key)
                
                # Determine severity based on pattern type
                severity = "high" if "THREAT" in pattern_id else "medium"
                
                signal = Tier1Signal(
                    signal_type="URGENCY_DETECTED",
                    severity=severity,
                    quote=quote,
                    t=timestamp,
                    pattern_matched=pattern_id,
                    confidence=confidence
                )
                signals.append(signal)
        
        return signals
    
    def _detect_secrecy(self, text: str, timestamp: float) -> List[Tier1Signal]:
        """Detect secrecy and isolation tactics."""
        signals = []
        
        for pattern, pattern_id, confidence in self.secrecy_patterns:
            for match in pattern.finditer(text):
                quote = match.group().strip()
                
                # Deduplication
                dedup_key = f"secrecy:{quote}:{timestamp}"
                if dedup_key in self._seen_evidence:
                    continue
                self._seen_evidence.add(dedup_key)
                
                signal = Tier1Signal(
                    signal_type="SECRECY_DETECTED",
                    severity="medium",
                    quote=quote,
                    t=timestamp,
                    pattern_matched=pattern_id,
                    confidence=confidence
                )
                signals.append(signal)
        
        return signals
    
    def extract_claims(self, segments: List[TranscriptSegment]) -> ClaimsEvidence:
        """
        Extract identity and relationship claims from transcript.
        
        Args:
            segments: Transcript segments to analyze
            
        Returns:
            ClaimsEvidence with detected claims
        """
        claims: List[ClaimEvidence] = []
        claim_types_seen: Dict[str, int] = defaultdict(int)
        
        for segment in segments:
            if not segment.text or not segment.text.strip():
                continue
            
            text = segment.text
            timestamp = segment.start
            
            # Check each claim category
            for claim_type, patterns in self.identity_patterns.items():
                for pattern, pattern_id, confidence in patterns:
                    for match in pattern.finditer(text):
                        quote = match.group().strip()
                        
                        # Extract claimed value (e.g., "mother", "bank")
                        value = self._extract_claim_value(match.group(), claim_type)
                        
                        # Deduplication
                        dedup_key = f"claim:{claim_type}:{value}:{timestamp}"
                        if dedup_key in self._seen_evidence:
                            continue
                        self._seen_evidence.add(dedup_key)
                        
                        claim = ClaimEvidence(
                            type=claim_type,
                            value=value,
                            quote=quote,
                            t=timestamp,
                            confidence=confidence,
                            language=self._detect_language(text)
                        )
                        claims.append(claim)
                        claim_types_seen[claim_type] += 1
                        
                        logger.info(f"Claim detected: {claim_type}={value} at {timestamp}s")
        
        # Determine primary claim (most frequent type, first occurrence)
        primary_claim = claims[0] if claims else None
        
        # Count claim changes (switching between different identities)
        claim_changes = max(0, len(set(claim_types_seen.keys())) - 1)
        
        return ClaimsEvidence(
            claims=claims,
            primary_claim=primary_claim,
            claim_changes=claim_changes
        )
    
    def extract_requests(self, segments: List[TranscriptSegment]) -> RequestEvidence:
        """
        Extract sensitive requests from transcript.
        
        Args:
            segments: Transcript segments to analyze
            
        Returns:
            RequestEvidence with detected requests
        """
        money_requests: List[MoneyRequest] = []
        credential_requests: List[CredentialRequest] = []
        action_requests: List[ActionRequest] = []
        
        for segment in segments:
            if not segment.text or not segment.text.strip():
                continue
            
            text = segment.text
            timestamp = segment.start
            
            # Extract credential requests
            cred_reqs = self._extract_credential_requests(text, timestamp)
            credential_requests.extend(cred_reqs)
            
            # Extract money requests
            money_reqs = self._extract_money_requests(text, timestamp)
            money_requests.extend(money_reqs)
        
        return RequestEvidence(
            money_requests=money_requests,
            credential_requests=credential_requests,
            action_requests=action_requests
        )
    
    def _extract_credential_requests(
        self, text: str, timestamp: float
    ) -> List[CredentialRequest]:
        """Extract credential requests with type classification."""
        requests = []
        
        for cred_type, patterns in self.credential_patterns.items():
            for pattern, pattern_id, confidence in patterns:
                for match in pattern.finditer(text):
                    # Check negation
                    if DetectionPatterns.check_negation(text, match.start()):
                        continue
                    
                    quote = match.group().strip()
                    
                    # Deduplication
                    dedup_key = f"cred_req:{cred_type}:{quote}:{timestamp}"
                    if dedup_key in self._seen_evidence:
                        continue
                    self._seen_evidence.add(dedup_key)
                    
                    request = CredentialRequest(
                        type=cred_type,
                        quote=quote,
                        t=timestamp,
                        confidence=confidence
                    )
                    requests.append(request)
        
        return requests
    
    def _extract_money_requests(self, text: str, timestamp: float) -> List[MoneyRequest]:
        """Extract money requests with amount parsing."""
        requests = []
        
        for pattern, pattern_id, confidence in self.money_patterns:
            for match in pattern.finditer(text):
                # Check negation
                if DetectionPatterns.check_negation(text, match.start()):
                    continue
                
                quote = match.group().strip()
                
                # Try to extract amount
                amount = self._extract_amount(quote)
                
                # Deduplication
                dedup_key = f"money_req:{quote}:{timestamp}"
                if dedup_key in self._seen_evidence:
                    continue
                self._seen_evidence.add(dedup_key)
                
                request = MoneyRequest(
                    amount=amount,
                    currency="INR",
                    method=None,  # Could be enhanced to detect UPI/bank/cash
                    quote=quote,
                    t=timestamp,
                    confidence=confidence
                )
                requests.append(request)
        
        return requests
    
    def extract_behavior(self, segments: List[TranscriptSegment]) -> BehaviorEvidence:
        """
        Extract behavioral evidence (urgency, secrecy, pressure).
        
        Args:
            segments: Transcript segments to analyze
            
        Returns:
            BehaviorEvidence with detected patterns
        """
        urgency_quotes: List[str] = []
        urgency_timestamps: List[float] = []
        urgency_patterns_found: List[str] = []
        
        secrecy_quotes: List[str] = []
        secrecy_timestamps: List[float] = []
        secrecy_patterns_found: List[str] = []
        
        emotional_quotes: List[str] = []
        emotional_timestamps: List[float] = []
        pressure_types: List[str] = []
        
        for segment in segments:
            if not segment.text or not segment.text.strip():
                continue
            
            text = segment.text
            timestamp = segment.start
            
            # Detect urgency
            for pattern, pattern_id, confidence in self.urgency_patterns:
                for match in pattern.finditer(text):
                    quote = match.group().strip()
                    urgency_quotes.append(quote)
                    urgency_timestamps.append(timestamp)
                    
                    # Categorize pattern type
                    if "THREAT" in pattern_id:
                        urgency_patterns_found.append("threat")
                    elif "TIME" in pattern_id:
                        urgency_patterns_found.append("time_limit")
                    elif "EMERG" in pattern_id:
                        urgency_patterns_found.append("emergency")
            
            # Detect secrecy
            for pattern, pattern_id, confidence in self.secrecy_patterns:
                for match in pattern.finditer(text):
                    quote = match.group().strip()
                    secrecy_quotes.append(quote)
                    secrecy_timestamps.append(timestamp)
                    
                    if "DONT_TELL" in pattern_id:
                        secrecy_patterns_found.append("dont_tell")
                    elif "SECRET" in pattern_id:
                        secrecy_patterns_found.append("secret")
                    elif "ALONE" in pattern_id:
                        secrecy_patterns_found.append("alone")
            
            # Detect emotional pressure
            for pressure_type, patterns in self.emotional_patterns.items():
                for pattern, pattern_id, confidence in patterns:
                    for match in pattern.finditer(text):
                        quote = match.group().strip()
                        emotional_quotes.append(quote)
                        emotional_timestamps.append(timestamp)
                        if pressure_type not in pressure_types:
                            pressure_types.append(pressure_type)
        
        # Determine urgency severity
        urgency_severity = "low"
        if "threat" in urgency_patterns_found:
            urgency_severity = "high"
        elif "time_limit" in urgency_patterns_found or "emergency" in urgency_patterns_found:
            urgency_severity = "medium"
        
        urgency_evidence = UrgencyEvidence(
            detected=len(urgency_quotes) > 0,
            quotes=urgency_quotes,
            timestamps=urgency_timestamps,
            severity=urgency_severity,
            patterns_found=list(set(urgency_patterns_found))
        )
        
        secrecy_evidence = SecrecyEvidence(
            detected=len(secrecy_quotes) > 0,
            quotes=secrecy_quotes,
            timestamps=secrecy_timestamps,
            patterns_found=list(set(secrecy_patterns_found))
        )
        
        emotional_evidence = EmotionalPressureEvidence(
            detected=len(emotional_quotes) > 0,
            quotes=emotional_quotes,
            timestamps=emotional_timestamps,
            pressure_types=pressure_types
        )
        
        return BehaviorEvidence(
            urgency=urgency_evidence,
            secrecy=secrecy_evidence,
            emotional_pressure=emotional_evidence,
            call_timing=None  # Requires call metadata, not available from transcript alone
        )
    
    def reset_session(self):
        """Reset deduplication tracking for a new call session."""
        self._seen_evidence.clear()
        logger.debug("Tier1Classifier session reset")
    
    # Helper methods
    
    def _extract_claim_value(self, matched_text: str, claim_type: str) -> str:
        """Extract the specific claim value from matched text."""
        matched_lower = matched_text.lower()
        
        # Relative claims
        if claim_type == "relative":
            for term in ["mother", "mom", "mummy", "ma", "maa", "amma"]:
                if term in matched_lower:
                    return "mother"
            for term in ["father", "dad", "daddy", "papa", "pitaji"]:
                if term in matched_lower:
                    return "father"
            for term in ["son", "beta", "bete"]:
                if term in matched_lower:
                    return "son"
            for term in ["daughter", "beti", "bitiya"]:
                if term in matched_lower:
                    return "daughter"
            for term in ["brother", "bhai", "bhaiya"]:
                if term in matched_lower:
                    return "brother"
            for term in ["sister", "behan", "didi"]:
                if term in matched_lower:
                    return "sister"
        
        # Organization claims
        elif claim_type == "organization":
            for bank in ["hdfc", "icici", "sbi", "axis", "kotak"]:
                if bank in matched_lower:
                    return f"{bank} bank"
            if "bank" in matched_lower:
                return "bank"
            if "government" in matched_lower or "sarkari" in matched_lower:
                return "government"
            if "customer" in matched_lower:
                return "customer service"
        
        # Authority claims
        elif claim_type == "authority":
            if "police" in matched_lower or "station" in matched_lower:
                return "police"
            if "inspector" in matched_lower or "officer" in matched_lower:
                return "police"
            if "lawyer" in matched_lower or "advocate" in matched_lower:
                return "lawyer"
        
        # Default: return first 50 chars
        return matched_text[:50].strip()
    
    def _extract_amount(self, text: str) -> Optional[float]:
        """Extract numeric amount from money request text."""
        # Look for consecutive digits (handles 5000, 50000, etc.)
        amount_pattern = r"(\d{3,})"  # At least 3 digits for meaningful amounts
        matches = re.findall(amount_pattern, text)
        
        if matches:
            # Take the largest numeric value (usually the actual amount)
            amounts = [float(m) for m in matches]
            return max(amounts)
        
        return None
    
    def _detect_language(self, text: str) -> str:
        """Simple language detection based on character patterns."""
        # Check for Devanagari script
        if re.search(r'[\u0900-\u097F]', text):
            return "hi"
        
        # Check for common Hindi/Hinglish words in Latin script
        hinglish_words = ["hai", "hoon", "aap", "tumhara", "kya", "bol", "raha", "rahi"]
        text_lower = text.lower()
        if any(word in text_lower for word in hinglish_words):
            return "hinglish"
        
        return "en"
