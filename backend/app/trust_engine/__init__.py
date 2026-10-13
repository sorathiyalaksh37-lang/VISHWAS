"""
Trust Engine package for VISHWAS.

Implements deterministic risk assessment:
- Trust Graph: Relationship and channel context
- Scoring Engine: Evidence-based risk scoring with caps and floors
- Trust Judge: Final deterministic risk assessment

Design Principle: Agents propose. Rules decide. Humans verify.
"""

from app.trust_engine.trust_graph import TrustGraph, ChannelStatus
from app.trust_engine.scoring import (
    TrustScorer,
    ScoreBreakdown,
    HardRuleFloor,
    SCORING_CATEGORIES,
    RISK_BANDS,
)
from app.trust_engine.judge import TrustJudge, RiskAssessment

__all__ = [
    "TrustGraph",
    "ChannelStatus",
    "TrustScorer",
    "ScoreBreakdown",
    "HardRuleFloor",
    "SCORING_CATEGORIES",
    "RISK_BANDS",
    "TrustJudge",
    "RiskAssessment",
]
