"""
ParameterExtractor — converts Tier1 evidence + optional LLM output
into canonical CallParameters for the deterministic Trust Judge.

Extraction strategy (in priority order):
  1. LLM (Qwen2.5-3B-Instruct) when enabled via settings.llm_extraction_enabled
  2. Tier1 regex classifier always runs as baseline / fallback
  3. Voice data passed through unchanged from voice_layer

Failure modes:
  - LLM unavailable / timeout / bad output → set llm_extraction_degraded=True,
    use Tier1 output only, add warning.
  - Tier1 also fails → return empty CallParameters with full warnings.
  - Never silently degrade without recording a warning.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.schemas.evidence import EvidenceExtraction, VoiceEvidence
from app.schemas.parameters import (
    CallParameters,
    BehaviorParameters,
    ChannelParam,
    ConsistencyParam,
    ConsistencyParameters,
    CredentialRequestParam,
    EvidenceStatus,
    ExtractionMeta,
    IdentityParam,
    IdentityParameters,
    MoneyRequestParam,
    PressureTacticParam,
    SensitiveRequestParameters,
    VoiceParam,
)
from app.schemas.report import TranscriptResponse

logger = logging.getLogger(__name__)

LLM_META = ExtractionMeta(
    source="llm",
    model_id="Qwen/Qwen2.5-3B-Instruct",
    model_revision="main",
)
TIER1_META = ExtractionMeta(source="tier1_regex")


# ── Public entry point ─────────────────────────────────────────────────────────

def build_call_parameters(
    transcript: TranscriptResponse,
    call_id: str,
    evidence: EvidenceExtraction,
    voice_evidence: Optional[VoiceEvidence],
    caller_number: Optional[str] = None,
    channel_status: str = "UNKNOWN",
    trust_context: Optional[Dict[str, Any]] = None,
) -> CallParameters:
    """
    Combine Tier1 evidence + optional LLM extraction into CallParameters.

    Args:
        transcript: ASR transcript (needed for LLM text)
        call_id: Call UUID
        evidence: Tier1 EvidenceExtraction (always available)
        voice_evidence: Voice layer result (may be None)
        caller_number: Caller's number for channel context
        channel_status: "VERIFIED" | "UNKNOWN" | "MISMATCH"
        trust_context: Trust Graph context dict
    """
    warnings: List[str] = []
    llm_degraded = False
    tier2_used = False
    llm_raw: Optional[Dict[str, Any]] = None

    # ── Step 1: Attempt LLM extraction ─────────────────────────────────────────
    if getattr(settings, "llm_extraction_enabled", False):
        try:
            from app.llm.qwen_extractor import (
                extract_parameters_llm,
                LLMExtractionError,
                QWEN_MODEL_ID,
                QWEN_REVISION,
            )
            transcript_text = _transcript_to_text(transcript)
            llm_raw = extract_parameters_llm(transcript_text, call_id)
            tier2_used = True
            logger.info(f"[{call_id}] LLM extraction succeeded")

        except Exception as exc:  # includes LLMExtractionError
            logger.warning(
                f"[{call_id}] LLM extraction failed, falling back to Tier1: {exc}"
            )
            llm_degraded = True
            warnings.append(f"LLM extraction unavailable — using Tier1 fallback: {str(exc)[:120]}")

    # ── Step 2: Build parameters ────────────────────────────────────────────────
    if tier2_used and llm_raw:
        identity_params = _build_identity_from_llm(llm_raw)
        request_params = _build_requests_from_llm(llm_raw)
        behavior_params = _build_behavior_from_llm(llm_raw)
        consistency_params = _build_consistency_from_llm(llm_raw)
    else:
        identity_params = _build_identity_from_tier1(evidence)
        request_params = _build_requests_from_tier1(evidence)
        behavior_params = _build_behavior_from_tier1(evidence)
        consistency_params = ConsistencyParameters()

    # ── Step 3: Channel (always from trust context, never LLM) ─────────────────
    channel_param = _build_channel_param(
        channel_status, caller_number, trust_context or {}
    )

    # ── Step 4: Voice (always from voice layer, never LLM) ─────────────────────
    voice_param = _build_voice_param(voice_evidence)

    # ── Step 5: Assemble ────────────────────────────────────────────────────────
    return CallParameters(
        call_id=call_id,
        identity=identity_params,
        requests=request_params,
        behavior=behavior_params,
        channel=channel_param,
        consistency=consistency_params,
        voice=voice_param,
        extractor_version="2.0-llm" if tier2_used else "2.0-tier1",
        tier1_used=True,
        tier2_used=tier2_used,
        llm_extraction_degraded=llm_degraded,
        extraction_warnings=warnings + list(evidence.extraction_warnings),
        transcript_segments_analyzed=len(transcript.segments) if transcript else 0,
    )


# ── LLM → Parameter builders ───────────────────────────────────────────────────

def _build_identity_from_llm(raw: Dict[str, Any]) -> IdentityParameters:
    ident_raw = raw.get("identity", {})
    params: List[IdentityParam] = []

    rel = ident_raw.get("claimed_relationship")
    status: EvidenceStatus = "detected" if rel else "not_detected"

    param = IdentityParam(
        status=status,
        claimed_name=ident_raw.get("claimed_name"),
        claimed_relationship=_safe_rel(rel),
        verification_status=_safe_verif(ident_raw.get("verification_status", "not_attempted")),
        inconsistencies=ident_raw.get("inconsistencies", []),
        speaker=ident_raw.get("speaker"),
        transcript_excerpt=ident_raw.get("excerpt"),
        timestamp_s=_safe_float(ident_raw.get("timestamp_s")),
        extraction_confidence=_safe_conf(ident_raw.get("confidence", 0.0)),
        meta=LLM_META,
    )
    params.append(param)

    return IdentityParameters(
        params=params,
        primary=param if status == "detected" else None,
        claim_changes=int(ident_raw.get("claim_changes", 0)),
    )


def _build_requests_from_llm(raw: Dict[str, Any]) -> SensitiveRequestParameters:
    money_list: List[MoneyRequestParam] = []
    cred_list: List[CredentialRequestParam] = []

    for mr in raw.get("money_requests", []):
        money_list.append(MoneyRequestParam(
            status="detected",
            amount=_safe_float(mr.get("amount")),
            currency=mr.get("currency", "INR"),
            payment_method=mr.get("payment_method"),
            transcript_excerpt=mr.get("excerpt"),
            timestamp_s=_safe_float(mr.get("timestamp_s")),
            speaker=mr.get("speaker"),
            extraction_confidence=_safe_conf(mr.get("confidence", 0.0)),
            meta=LLM_META,
        ))

    for cr in raw.get("credential_requests", []):
        cred_type = cr.get("credential_type")
        if cred_type not in (
            "otp", "pin", "password", "cvv", "card_number",
            "account_number", "aadhar", "pan", "kyc_details"
        ):
            cred_type = "other"
        cred_list.append(CredentialRequestParam(
            status="detected",
            credential_type=cred_type,
            transcript_excerpt=cr.get("excerpt"),
            timestamp_s=_safe_float(cr.get("timestamp_s")),
            speaker=cr.get("speaker"),
            extraction_confidence=_safe_conf(cr.get("confidence", 0.0)),
            meta=LLM_META,
        ))

    return SensitiveRequestParameters(money=money_list, credentials=cred_list)


def _build_behavior_from_llm(raw: Dict[str, Any]) -> BehaviorParameters:
    tactics: List[PressureTacticParam] = []
    valid_types = {"urgency", "threat", "secrecy", "emotional",
                   "repeated_demand", "resistance_to_verification"}

    for pt in raw.get("pressure_tactics", []):
        t_type = pt.get("tactic_type")
        if t_type not in valid_types:
            t_type = "urgency"
        severity = pt.get("severity", "low")
        if severity not in ("low", "medium", "high"):
            severity = "low"

        tactics.append(PressureTacticParam(
            status="detected",
            tactic_type=t_type,
            severity=severity,
            transcript_excerpt=pt.get("excerpt"),
            timestamp_s=_safe_float(pt.get("timestamp_s")),
            speaker=pt.get("speaker"),
            extraction_confidence=_safe_conf(pt.get("confidence", 0.0)),
            meta=LLM_META,
        ))

    return BehaviorParameters(tactics=tactics)


def _build_consistency_from_llm(raw: Dict[str, Any]) -> ConsistencyParameters:
    items: List[ConsistencyParam] = []
    valid_types = {"changed_story", "changed_identity", "bypass_verification",
                   "self_contradiction", "other"}

    for c in raw.get("consistency", []):
        c_type = c.get("contradiction_type", "other")
        if c_type not in valid_types:
            c_type = "other"
        items.append(ConsistencyParam(
            status="detected",
            contradiction_type=c_type,
            transcript_excerpt=c.get("excerpt"),
            timestamp_s=_safe_float(c.get("timestamp_s")),
            extraction_confidence=_safe_conf(c.get("confidence", 0.0)),
            meta=LLM_META,
        ))

    return ConsistencyParameters(contradictions=items)


# ── Tier1 → Parameter builders ─────────────────────────────────────────────────

def _build_identity_from_tier1(evidence: EvidenceExtraction) -> IdentityParameters:
    params: List[IdentityParam] = []
    for claim in evidence.claims.claims:
        params.append(IdentityParam(
            status="detected",
            claimed_name=claim.value,
            claimed_relationship=claim.type if claim.type != "unknown" else None,
            verification_status="not_attempted",
            speaker=None,
            transcript_excerpt=claim.quote,
            timestamp_s=claim.t,
            extraction_confidence=claim.confidence,
            meta=TIER1_META,
        ))

    primary: Optional[IdentityParam] = None
    if evidence.claims.primary_claim:
        primary = IdentityParam(
            status="detected",
            claimed_name=evidence.claims.primary_claim.value,
            claimed_relationship=(
                evidence.claims.primary_claim.type
                if evidence.claims.primary_claim.type != "unknown" else None
            ),
            verification_status="not_attempted",
            transcript_excerpt=evidence.claims.primary_claim.quote,
            timestamp_s=evidence.claims.primary_claim.t,
            extraction_confidence=evidence.claims.primary_claim.confidence,
            meta=TIER1_META,
        )

    return IdentityParameters(
        params=params,
        primary=primary,
        claim_changes=evidence.claims.claim_changes,
    )


def _build_requests_from_tier1(evidence: EvidenceExtraction) -> SensitiveRequestParameters:
    money_list: List[MoneyRequestParam] = []
    cred_list: List[CredentialRequestParam] = []

    for mr in evidence.requests.money_requests:
        money_list.append(MoneyRequestParam(
            status="detected",
            amount=mr.amount,
            currency=mr.currency,
            payment_method=mr.method,
            transcript_excerpt=mr.quote,
            timestamp_s=mr.t,
            extraction_confidence=mr.confidence,
            meta=TIER1_META,
        ))

    for cr in evidence.requests.credential_requests:
        money_list_type = cr.type if cr.type in (
            "otp", "pin", "password", "cvv", "card_number",
            "account_number", "aadhar", "pan", "kyc_details"
        ) else "other"
        cred_list.append(CredentialRequestParam(
            status="detected",
            credential_type=money_list_type,
            transcript_excerpt=cr.quote,
            timestamp_s=cr.t,
            extraction_confidence=cr.confidence,
            meta=TIER1_META,
        ))

    return SensitiveRequestParameters(money=money_list, credentials=cred_list)


def _build_behavior_from_tier1(evidence: EvidenceExtraction) -> BehaviorParameters:
    tactics: List[PressureTacticParam] = []
    beh = evidence.behavior

    if beh.urgency.detected:
        sev_map = {"high": "high", "medium": "medium", "low": "low"}
        severity = sev_map.get(beh.urgency.severity, "low")
        for i, quote in enumerate(beh.urgency.quotes):
            ts = beh.urgency.timestamps[i] if i < len(beh.urgency.timestamps) else None
            tactics.append(PressureTacticParam(
                status="detected",
                tactic_type="urgency",
                severity=severity,
                transcript_excerpt=quote,
                timestamp_s=ts,
                extraction_confidence=0.75,
                meta=TIER1_META,
            ))

    if beh.secrecy.detected:
        for i, quote in enumerate(beh.secrecy.quotes):
            ts = beh.secrecy.timestamps[i] if i < len(beh.secrecy.timestamps) else None
            tactics.append(PressureTacticParam(
                status="detected",
                tactic_type="secrecy",
                severity="medium",
                transcript_excerpt=quote,
                timestamp_s=ts,
                extraction_confidence=0.75,
                meta=TIER1_META,
            ))

    if beh.emotional_pressure.detected:
        for i, quote in enumerate(beh.emotional_pressure.quotes):
            ts = (
                beh.emotional_pressure.timestamps[i]
                if i < len(beh.emotional_pressure.timestamps) else None
            )
            tactics.append(PressureTacticParam(
                status="detected",
                tactic_type="emotional",
                severity="medium",
                transcript_excerpt=quote,
                timestamp_s=ts,
                extraction_confidence=0.75,
                meta=TIER1_META,
            ))

    return BehaviorParameters(tactics=tactics)


# ── Channel & Voice builders ───────────────────────────────────────────────────

def _build_channel_param(
    channel_status: str,
    caller_number: Optional[str],
    trust_context: Dict[str, Any],
) -> ChannelParam:
    valid = {"VERIFIED", "UNKNOWN", "MISMATCH"}
    safe_status = channel_status if channel_status in valid else "UNKNOWN"
    ev_status: EvidenceStatus = (
        "detected" if safe_status in ("VERIFIED", "MISMATCH") else "unknown"
    )
    return ChannelParam(
        status=ev_status,
        channel_status=safe_status,
        caller_number=caller_number,
        contact_found=bool(trust_context.get("contact_found")),
        contact_name=trust_context.get("contact_name"),
        verified_numbers=trust_context.get("verified_numbers", []),
        meta=ExtractionMeta(source="manual"),
    )


def _build_voice_param(voice_evidence: Optional[VoiceEvidence]) -> VoiceParam:
    if voice_evidence is None:
        return VoiceParam(status="not_analyzed")

    status_map = {
        "ok": "ok",
        "inconclusive": "inconclusive",
        "unavailable": "unavailable",
        "error": "error",
    }
    status = status_map.get(voice_evidence.status, "unavailable")

    spoof_prob: Optional[float] = None
    windows: Optional[int] = None
    if voice_evidence.spoof_detection:
        spoof_prob = voice_evidence.spoof_detection.spoof_prob
        windows = voice_evidence.spoof_detection.windows_analyzed

    speaker_match: Optional[bool] = None
    if voice_evidence.voiceprint_match:
        speaker_match = voice_evidence.voiceprint_match.is_match

    quality_ok: Optional[bool] = None
    if voice_evidence.quality:
        quality_ok = voice_evidence.quality.is_sufficient_quality

    return VoiceParam(
        status=status,
        spoof_prob=spoof_prob,
        windows_analyzed=windows,
        speaker_match=speaker_match,
        quality_sufficient=quality_ok,
        model_id=(
            voice_evidence.spoof_detection.model
            if voice_evidence.spoof_detection else None
        ),
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _transcript_to_text(transcript: Optional[TranscriptResponse]) -> str:
    if not transcript or not transcript.segments:
        return ""
    lines: List[str] = []
    for seg in transcript.segments:
        speaker = getattr(seg, "speaker", None) or "UNKNOWN"
        text = getattr(seg, "text", "")
        t = getattr(seg, "start", 0.0)
        lines.append(f"[{t:.1f}s {speaker}]: {text}")
    return "\n".join(lines)


def _safe_float(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _safe_conf(v: Any) -> float:
    try:
        f = float(v)
        return max(0.0, min(1.0, f))
    except (TypeError, ValueError):
        return 0.0


def _safe_rel(v: Optional[str]) -> Optional[str]:
    valid = {"relative", "organization", "authority",
             "service_provider", "friend", "unknown"}
    return v if v in valid else None


def _safe_verif(v: Optional[str]) -> str:
    valid = {"verified", "unverified", "mismatch", "not_attempted"}
    return v if v in valid else "not_attempted"
