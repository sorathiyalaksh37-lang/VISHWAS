"""
Transcript quality assessment and commitment-state tracking for VISHWAS Phase 5A.

Provides:
  - TranscriptQuality: backward-compatible quality object attached to evidence
  - AssessmentStatus: provisional / complete / degraded / unavailable
  - TranscriptCommitmentTracker: manages partial → committed → final state

Design principles
-----------------
* Committed text is the ONLY text permitted to generate durable evidence.
* Partial text may change; evidence derived from it is provisional only.
* Poor-quality transcripts yield a degraded assessment, not a confident one.
* All fields are Optional so existing code paths remain unaffected.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


class AssessmentStatus(str, Enum):
    """Overall assessment status exposed to the UI and risk pipeline."""
    PROVISIONAL = "provisional"    # Still accumulating evidence
    COMPLETE = "complete"          # Full evidence available
    DEGRADED = "degraded"          # Evidence limited by quality problems
    UNAVAILABLE = "unavailable"    # No usable transcript available


class TranscriptCommitment(str, Enum):
    """Per-segment commitment state."""
    PARTIAL = "partial"            # Hypothesis; may change
    COMMITTED = "committed"        # Stable; evidence-permitted
    FINAL = "final"               # Stream ended; committed unconditionally


@dataclass
class TranscriptQuality:
    """
    Backward-compatible transcript quality object.

    Attached as an optional field to EvidenceExtraction.
    UI must display a warning whenever status != 'good'.
    """
    status: str = "unknown"        # good | low | degraded | unknown
    reason: str = ""               # Human-readable explanation
    asr_confidence: Optional[float] = None   # Mean ASR logprob if available
    revision_count: int = 0        # How many times stable text was revised
    empty_segments: int = 0        # Segments with no text
    language_uncertain: bool = False

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "reason": self.reason,
            "asr_confidence": self.asr_confidence,
            "revision_count": self.revision_count,
            "empty_segments": self.empty_segments,
            "language_uncertain": self.language_uncertain,
        }

    @classmethod
    def from_indicators(
        cls,
        asr_confidence: Optional[float] = None,
        revision_count: int = 0,
        empty_segments: int = 0,
        total_segments: int = 0,
        language_uncertain: bool = False,
    ) -> "TranscriptQuality":
        """
        Compute quality status from available indicators.

        Does NOT invent values for missing measurements.
        """
        reasons: List[str] = []

        if total_segments == 0:
            return cls(
                status="unavailable",
                reason="No transcript segments received",
                asr_confidence=asr_confidence,
                revision_count=revision_count,
                empty_segments=empty_segments,
                language_uncertain=language_uncertain,
            )

        # Empty segments
        empty_ratio = empty_segments / total_segments if total_segments else 0
        if empty_ratio > 0.5:
            reasons.append(f"High empty-segment ratio ({empty_segments}/{total_segments})")

        # Excessive revisions
        if revision_count >= 5:
            reasons.append(f"Excessive ASR revisions ({revision_count})")

        # ASR confidence (only if the field is actually provided)
        if asr_confidence is not None and asr_confidence < 0.3:
            reasons.append(f"Low ASR confidence ({asr_confidence:.2f})")

        # Language uncertainty
        if language_uncertain:
            reasons.append("Language detection uncertain")

        # Derive status
        if len(reasons) >= 2:
            status = "degraded"
        elif len(reasons) == 1:
            status = "low"
        else:
            status = "good"

        return cls(
            status=status,
            reason="; ".join(reasons) if reasons else "Transcript quality acceptable",
            asr_confidence=asr_confidence,
            revision_count=revision_count,
            empty_segments=empty_segments,
            language_uncertain=language_uncertain,
        )


# ── Commitment tracker ────────────────────────────────────────────────────────

@dataclass
class CommittedSegment:
    """A transcript segment that has been committed (stable)."""
    segment_id: str
    start_time: float
    end_time: float
    text: str
    commitment: TranscriptCommitment = TranscriptCommitment.COMMITTED
    confidence: Optional[float] = None
    revision_of: Optional[str] = None   # segment_id this replaces, if any


class TranscriptCommitmentTracker:
    """
    Tracks the three-state lifecycle of transcript segments:
      PARTIAL → COMMITTED → FINAL

    Rules
    -----
    * Only COMMITTED or FINAL segments may produce durable evidence.
    * A PARTIAL segment is provisional; evidence from it must be marked
      provisional and retracted if the text changes.
    * Text is committed when N consecutive overlapping windows produce the
      same stable prefix (configured via stability_windows).
    * On stream end, any remaining PARTIAL is promoted to FINAL.
    * Duplicate evidence cannot be created from text that has already been
      committed under a prior segment ID.
    """

    def __init__(self, stability_windows: int = 2) -> None:
        self.stability_windows = stability_windows
        self._partial_text: str = ""
        self._committed_text: str = ""
        self._committed_segments: List[CommittedSegment] = []
        self._window_history: List[str] = []   # Recent window transcripts
        self._revision_count: int = 0
        self._empty_count: int = 0
        self._seg_counter: int = 0

    # ── Public properties ─────────────────────────────────────────────────────

    @property
    def partial_transcript(self) -> str:
        """Current provisional text (may change)."""
        return self._partial_text

    @property
    def committed_transcript(self) -> str:
        """Stable committed text (evidence-permitted)."""
        return self._committed_text

    @property
    def committed_segments(self) -> List[CommittedSegment]:
        return list(self._committed_segments)

    @property
    def revision_count(self) -> int:
        return self._revision_count

    @property
    def empty_count(self) -> int:
        return self._empty_count

    # ── Core update ───────────────────────────────────────────────────────────

    def update_window(
        self,
        window_text: str,
        start_time: float,
        end_time: float,
        confidence: Optional[float] = None,
    ) -> List[CommittedSegment]:
        """
        Submit a new window transcript.  Returns any newly committed segments.

        Args:
            window_text: Text from the latest ASR window (after dedup).
            start_time:  Window start in seconds.
            end_time:    Window end in seconds.
            confidence:  ASR confidence if available.

        Returns:
            List of newly committed segments (may be empty).
        """
        text = window_text.strip()

        if not text:
            self._empty_count += 1
            self._window_history.clear()
            return []

        # Track revisions: did the stable portion change?
        old_partial = self._partial_text
        self._partial_text = text
        if old_partial and old_partial != text and not text.startswith(old_partial):
            self._revision_count += 1
            logger.debug(
                "Transcript revision %d: '%s' → '%s'",
                self._revision_count, old_partial[:40], text[:40],
            )

        # Maintain rolling history of the last N window texts
        self._window_history.append(text)
        if len(self._window_history) > self.stability_windows + 1:
            self._window_history.pop(0)

        # Check stability: all last N windows agree on a common prefix
        if len(self._window_history) >= self.stability_windows:
            stable_prefix = self._common_prefix(self._window_history[-self.stability_windows:])
            if stable_prefix:
                return self._maybe_commit(stable_prefix, start_time, end_time, confidence)

        return []

    def finalize(self, end_time: float) -> List[CommittedSegment]:
        """
        Finalize the stream.  Promotes any uncommitted partial text to FINAL.

        Returns:
            List of newly finalized segments.
        """
        uncommitted = self._partial_text.strip()
        if not uncommitted:
            return []

        # Strip already-committed prefix
        already_committed = self._committed_text.strip()
        if already_committed and uncommitted.startswith(already_committed):
            uncommitted = uncommitted[len(already_committed):].strip()

        if not uncommitted:
            return []

        seg = self._make_segment(
            uncommitted,
            start_time=end_time - 2.0,
            end_time=end_time,
            commitment=TranscriptCommitment.FINAL,
        )
        self._committed_segments.append(seg)
        self._committed_text = f"{self._committed_text} {uncommitted}".strip()
        self._partial_text = ""
        logger.debug("Finalized remaining text: '%s'", uncommitted[:60])
        return [seg]

    def validate_quote(self, quote: str) -> bool:
        """
        Return True only if the quote is present in committed (not partial) text.

        Evidence derived from uncommitted text must NOT call this True.
        """
        if not quote or not self._committed_text:
            return False
        return quote.strip() in self._committed_text

    def assessment_status(self, total_segments: int = 0) -> AssessmentStatus:
        """Derive the overall assessment status from current quality indicators."""
        if not self._committed_text and not self._partial_text:
            return AssessmentStatus.UNAVAILABLE
        quality = TranscriptQuality.from_indicators(
            revision_count=self._revision_count,
            empty_segments=self._empty_count,
            total_segments=total_segments or max(1, len(self._committed_segments)),
        )
        if quality.status in ("degraded",):
            return AssessmentStatus.DEGRADED
        if quality.status in ("low",):
            return AssessmentStatus.PROVISIONAL
        return AssessmentStatus.PROVISIONAL if not self._committed_text else AssessmentStatus.COMPLETE

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _maybe_commit(
        self,
        stable_prefix: str,
        start_time: float,
        end_time: float,
        confidence: Optional[float],
    ) -> List[CommittedSegment]:
        """Commit the stable prefix if it extends beyond what is already committed."""
        already = self._committed_text.strip()
        if already and stable_prefix.startswith(already):
            new_text = stable_prefix[len(already):].strip()
        elif not already:
            new_text = stable_prefix.strip()
        else:
            # Prefix does not extend committed text — skip
            return []

        if not new_text:
            return []

        seg = self._make_segment(new_text, start_time, end_time, confidence)
        self._committed_segments.append(seg)
        self._committed_text = stable_prefix.strip()
        logger.debug("Committed segment '%s': '%s'", seg.segment_id, new_text[:60])
        return [seg]

    def _make_segment(
        self,
        text: str,
        start_time: float,
        end_time: float,
        confidence: Optional[float] = None,
        commitment: TranscriptCommitment = TranscriptCommitment.COMMITTED,
    ) -> CommittedSegment:
        self._seg_counter += 1
        return CommittedSegment(
            segment_id=f"seg-{self._seg_counter:04d}",
            start_time=round(start_time, 3),
            end_time=round(end_time, 3),
            text=text,
            commitment=commitment,
            confidence=confidence,
        )

    @staticmethod
    def _common_prefix(texts: List[str]) -> str:
        """
        Return the common word-level prefix of a list of texts.

        Uses token comparison (split on whitespace) to handle minor
        punctuation differences at word boundaries.
        """
        if not texts:
            return ""
        if len(texts) == 1:
            return texts[0]

        # Tokenise each text
        tokenised = [t.split() for t in texts]
        min_len = min(len(t) for t in tokenised)
        if min_len == 0:
            return ""

        common_tokens: List[str] = []
        for i in range(min_len):
            # Normalise: lowercase, strip trailing punctuation for comparison
            tokens_at_i = [t[i].lower().rstrip(".,!?;:") for t in tokenised]
            if len(set(tokens_at_i)) == 1:
                # Use the token from the first text (preserves original case/punct)
                common_tokens.append(tokenised[0][i])
            else:
                break

        return " ".join(common_tokens)
