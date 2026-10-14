"""
Canonical Parameter Schemas for VISHWAS Parameter-Based Risk Scoring.

These models represent the validated, normalized parameters that flow from
the LLM extraction layer into the deterministic Trust Judge.

Design contract:
  - LLM extracts raw observations -> these schemas validate & normalize them.
  - Trust Judge reads ONLY from these schemas (never raw LLM text).
  - Status field distinguishes detected / not_detected / unknown / unavailable.
  - Confidence is a hint for human review, never a scoring input.
  - Duplicate evidence_ids are rejected before scoring.

Phase: Parameter-Based Scoring (post Phase 6)
"""
from __future__ import annotations

import uuid
from typing import List, Literal, Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


# EvidenceStatus literal
EvidenceStatus = Literal["detected", "not_detected", "unknown", "unavailable"]


class ExtractionMeta(BaseModel):
    """Provenance: which model/method produced this parameter."""
    source: Literal["tier1_regex", "llm", "voice_layer", "manual"] = "tier1_regex"
    model_id: Optional[str] = Field(None, description="Model id/revision")
    model_revision: Optional[str] = None
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    latency_ms: Optional[float] = None


# ── A. Identity Parameters ─────────────────────────────────────────────────────

class IdentityParam(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: EvidenceStatus
    claimed_name: Optional[str] = None
    claimed_relationship: Optional[Literal[
        "relative", "organization", "authority",
        "service_provider", "friend", "unknown"
    ]] = None
    verification_status: Literal[
        "verified", "unverified", "mismatch", "not_attempted"
    ] = "not_attempted"
    inconsistencies: List[str] = Field(default_factory=list)
    speaker: Optional[str] = None
    transcript_excerpt: Optional[str] = None
    timestamp_s: Optional[float] = Field(None, ge=0)
    extraction_confidence: float = Field(0.0, ge=0, le=1)
    meta: ExtractionMeta = Field(default_factory=ExtractionMeta)

    @field_validator("claimed_name", mode="before")
    @classmethod
    def strip_name(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().lower() if v else None


class IdentityParameters(BaseModel):
    params: List[IdentityParam] = Field(default_factory=list)
    primary: Optional[IdentityParam] = None
    claim_changes: int = Field(0, ge=0)

    def deduped(self) -> List[IdentityParam]:
        seen: set = set()
        out: List[IdentityParam] = []
        for p in self.params:
            if p.evidence_id not in seen:
                seen.add(p.evidence_id)
                out.append(p)
        return out


# ── B. Sensitive Request Parameters ───────────────────────────────────────────

class MoneyRequestParam(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: EvidenceStatus
    amount: Optional[float] = Field(None, ge=0)
    currency: str = "INR"
    payment_method: Optional[str] = None
    transcript_excerpt: Optional[str] = None
    timestamp_s: Optional[float] = Field(None, ge=0)
    speaker: Optional[str] = None
    extraction_confidence: float = Field(0.0, ge=0, le=1)
    meta: ExtractionMeta = Field(default_factory=ExtractionMeta)


class CredentialRequestParam(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: EvidenceStatus
    credential_type: Optional[Literal[
        "otp", "pin", "password", "cvv",
        "card_number", "account_number",
        "aadhar", "pan", "kyc_details", "other"
    ]] = None
    transcript_excerpt: Optional[str] = None
    timestamp_s: Optional[float] = Field(None, ge=0)
    speaker: Optional[str] = None
    extraction_confidence: float = Field(0.0, ge=0, le=1)
    meta: ExtractionMeta = Field(default_factory=ExtractionMeta)


class SensitiveRequestParameters(BaseModel):
    money: List[MoneyRequestParam] = Field(default_factory=list)
    credentials: List[CredentialRequestParam] = Field(default_factory=list)

    @property
    def max_money_amount(self) -> float:
        amounts = [p.amount for p in self.money if p.amount is not None]
        return max(amounts, default=0.0)

    @property
    def has_otp_or_pin(self) -> bool:
        return any(p.credential_type in ("otp", "pin") for p in self.credentials)

    def deduped_money(self) -> List[MoneyRequestParam]:
        seen: set = set()
        return [p for p in self.money
                if not (p.evidence_id in seen or seen.add(p.evidence_id))]  # type: ignore

    def deduped_creds(self) -> List[CredentialRequestParam]:
        seen: set = set()
        return [p for p in self.credentials
                if not (p.evidence_id in seen or seen.add(p.evidence_id))]  # type: ignore


# ── C. Behavioral Pressure Parameters ─────────────────────────────────────────

class PressureTacticParam(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: EvidenceStatus
    tactic_type: Optional[Literal[
        "urgency", "threat", "secrecy", "emotional",
        "repeated_demand", "resistance_to_verification"
    ]] = None
    severity: Literal["low", "medium", "high"] = "low"
    transcript_excerpt: Optional[str] = None
    timestamp_s: Optional[float] = Field(None, ge=0)
    speaker: Optional[str] = None
    extraction_confidence: float = Field(0.0, ge=0, le=1)
    meta: ExtractionMeta = Field(default_factory=ExtractionMeta)


class BehaviorParameters(BaseModel):
    tactics: List[PressureTacticParam] = Field(default_factory=list)

    @property
    def has_secrecy(self) -> bool:
        return any(p.tactic_type == "secrecy" and p.status == "detected"
                   for p in self.tactics)

    @property
    def max_severity(self) -> str:
        order = {"low": 0, "medium": 1, "high": 2}
        detected = [p for p in self.tactics if p.status == "detected"]
        if not detected:
            return "low"
        return max(detected, key=lambda p: order[p.severity]).severity

    def deduped(self) -> List[PressureTacticParam]:
        seen: set = set()
        return [p for p in self.tactics
                if not (p.evidence_id in seen or seen.add(p.evidence_id))]  # type: ignore


# ── D. Channel Parameters ──────────────────────────────────────────────────────

class ChannelParam(BaseModel):
    status: EvidenceStatus
    channel_status: Literal["VERIFIED", "UNKNOWN", "MISMATCH"] = "UNKNOWN"
    caller_number: Optional[str] = None
    contact_found: bool = False
    contact_name: Optional[str] = None
    verified_numbers: List[str] = Field(default_factory=list)
    inconsistencies: List[str] = Field(default_factory=list)
    meta: ExtractionMeta = Field(default_factory=ExtractionMeta)


# ── E. Consistency Parameters ──────────────────────────────────────────────────

class ConsistencyParam(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: EvidenceStatus
    contradiction_type: Optional[Literal[
        "changed_story", "changed_identity",
        "bypass_verification", "self_contradiction", "other"
    ]] = None
    transcript_excerpt: Optional[str] = None
    timestamp_s: Optional[float] = Field(None, ge=0)
    extraction_confidence: float = Field(0.0, ge=0, le=1)
    meta: ExtractionMeta = Field(default_factory=ExtractionMeta)


class ConsistencyParameters(BaseModel):
    contradictions: List[ConsistencyParam] = Field(default_factory=list)


# ── F. Voice Parameters ────────────────────────────────────────────────────────

class VoiceParam(BaseModel):
    """
    Voice analysis results - always supplied by the voice layer,
    never inferred from transcript content. LLM must never invent these.
    """
    status: Literal["ok", "inconclusive", "unavailable", "error", "not_analyzed"]
    spoof_prob: Optional[float] = Field(None, ge=0, le=1)
    windows_analyzed: Optional[int] = Field(None, ge=0)
    speaker_match: Optional[bool] = None
    quality_sufficient: Optional[bool] = None
    model_id: Optional[str] = None
    confidence_note: Optional[str] = None
    meta: ExtractionMeta = Field(
        default_factory=lambda: ExtractionMeta(source="voice_layer")
    )

    @model_validator(mode="after")
    def spoof_requires_ok_status(self) -> "VoiceParam":
        if self.spoof_prob is not None and self.status not in ("ok", "inconclusive"):
            self.spoof_prob = None
        return self


# ── G. Master Parameter Bundle ─────────────────────────────────────────────────

class CallParameters(BaseModel):
    """
    Complete validated parameter set for one call.
    This is the single source of truth that flows into the Trust Judge.
    """
    call_id: str
    identity: IdentityParameters = Field(default_factory=IdentityParameters)
    requests: SensitiveRequestParameters = Field(
        default_factory=SensitiveRequestParameters
    )
    behavior: BehaviorParameters = Field(default_factory=BehaviorParameters)
    channel: ChannelParam = Field(
        default_factory=lambda: ChannelParam(
            status="unknown", channel_status="UNKNOWN"
        )
    )
    consistency: ConsistencyParameters = Field(
        default_factory=ConsistencyParameters
    )
    voice: VoiceParam = Field(
        default_factory=lambda: VoiceParam(status="not_analyzed")
    )

    extractor_version: str = "2.0-llm"
    tier1_used: bool = True
    tier2_used: bool = False
    llm_extraction_degraded: bool = False
    extraction_warnings: List[str] = Field(default_factory=list)
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    transcript_segments_analyzed: int = Field(0, ge=0)

    @property
    def is_provisional(self) -> bool:
        return self.transcript_segments_analyzed < 2

    @property
    def quality_score(self) -> float:
        scores: List[float] = []
        if self.identity.primary and self.identity.primary.status == "detected":
            scores.append(self.identity.primary.extraction_confidence)
        for p in self.requests.money + self.requests.credentials:
            if p.status == "detected":
                scores.append(p.extraction_confidence)
        for p in self.behavior.tactics:
            if p.status == "detected":
                scores.append(p.extraction_confidence)
        if self.tier2_used and not self.llm_extraction_degraded:
            scores.append(0.85)
        return sum(scores) / len(scores) if scores else 0.3
