"""
Evidence extraction modules for VISHWAS.

This package contains:
- Tier 1: Rule-based pattern detection (deterministic, offline)
- Tier 2: LLM-based extraction (future implementation)
"""

from app.extractors.tier1_classifier import Tier1Classifier
from app.extractors.evidence_pipeline import (
    extract_evidence_from_transcript,
    extract_evidence_streaming,
    get_extraction_summary,
)

__all__ = [
    "Tier1Classifier",
    "extract_evidence_from_transcript",
    "extract_evidence_streaming",
    "get_extraction_summary",
]
