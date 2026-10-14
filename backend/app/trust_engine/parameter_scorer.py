"""
Parameter-Based Deterministic Scorer for VISHWAS.

Reads from CallParameters (canonical parameter schema) and produces the
same ScoreBreakdown as TrustScorer so the existing TrustJudge works unchanged.

Design rules (from spec):
- Category caps: Identity(25), Request(30), Behavior(20), Channel(15), Voice(10)
- Risk bands: Low(0-24), Medium(25-49), High(50-74), Critical(75-100)
- Hard floors preserved (OTP non-verified = 75, money+secrecy+mismatch = 50,
  relative+spoof+unverified = 50)
- Unknown caller != identity mismatch (must not auto-penalise)
- Missing audio != genuine voice (voice unavailable = 0 points, not negative)
- Unknown/unavailable evidence does NOT become negative evidence
- Duplicate evidence_ids are deduplicated before scoring
- Optional LLM never overrides Judge
"""
from __future__ import annotations

import logging
from typing import Dict, List

from app.schemas.parameters import CallParameters
from app.trust_engine.scoring import ScoreBreakdown, RiskLevel

logger = logging.getLogger(__name__)

# ── Category caps (same as existing scorer) ───────────────────────────────────
CAP_IDENTITY = 25
CAP_REQUEST  = 30
CAP_BEHAVIOR = 20
CAP_CHANNEL  = 15
CAP_VOICE    = 10


def score_from_parameters(params: CallParameters) -> ScoreBreakdown:
    """
    Deterministically score a call from its CallParameters.
    Returns the same ScoreBreakdown used by TrustJudge.
    """
    bd = ScoreBreakdown()

    bd.identity = _score_identity(params, bd)
    bd.request  = _score_requests(params, bd)
    bd.behavior = _score_behavior(params, bd)
    bd.channel  = _score_channel(params, bd)
    bd.voice    = _score_voice(params, bd)

    bd.total       = bd.identity + bd.request + bd.behavior + bd.channel + bd.voice
    bd.capped_total = min(100, bd.total)
    bd.final_score  = _apply_floors(bd.capped_total, params, bd)
    bd.final_score  = max(0, min(100, bd.final_score))

    logger.info(
        f"[{params.call_id}] param-score={bd.final_score} "
        f"({bd.risk_level.value}) "
        f"id={bd.identity} req={bd.request} beh={bd.behavior} "
        f"ch={bd.channel} v={bd.voice}"
    )
    return bd


# ── Identity scoring (max 25) ─────────────────────────────────────────────────

def _score_identity(params: CallParameters, bd: ScoreBreakdown) -> int:
    score = 0
    primary = params.identity.primary

    if primary is None or primary.status != "detected":
        # No identity claim detected → neutral, not penalised
        return 0

    rel = primary.claimed_relationship
    if rel in ("relative", "organization", "authority", "service_provider"):
        vs = primary.verification_status
        if vs == "mismatch":
            score += 20
            bd.reasons.append(
                f"Caller claims to be {primary.claimed_name or rel} "
                "but number contradicts verified records"
            )
            bd.fired_rules.append("PARAM_IDENTITY_MISMATCH")
        elif vs == "unverified":
            score += 15
            bd.reasons.append(
                f"Caller claims to be {primary.claimed_name or rel} "
                "from an unverified/unknown number"
            )
            bd.fired_rules.append("PARAM_IDENTITY_UNKNOWN")
        # "not_attempted" or "verified" → 0 additional points

    # Inconsistencies (story changes)
    if params.identity.claim_changes > 1:
        score = min(score + 5, CAP_IDENTITY)
        bd.reasons.append(f"Identity claim changed {params.identity.claim_changes} times during call")
        bd.fired_rules.append("PARAM_IDENTITY_CHANGED")

    return min(score, CAP_IDENTITY)


# ── Request scoring (max 30) ──────────────────────────────────────────────────

def _score_requests(params: CallParameters, bd: ScoreBreakdown) -> int:
    score = 0
    # Only count requests that were actually detected
    creds  = [c for c in params.requests.deduped_creds() if c.status == "detected"]
    moneys = [m for m in params.requests.deduped_money() if m.status == "detected"]

    # Credential requests (highest priority)
    if creds:
        otp_pin = [c for c in creds if c.credential_type in ("otp", "pin")]
        passwords = [c for c in creds if c.credential_type == "password"]
        fin = [c for c in creds if c.credential_type in (
            "cvv", "card_number", "account_number")]
        other = [c for c in creds if c not in otp_pin + passwords + fin]

        if otp_pin:
            score = 30
            bd.reasons.append("Request for OTP or PIN detected")
            bd.fired_rules.append("PARAM_REQ_OTP_PIN")
        elif passwords:
            score = 25
            bd.reasons.append("Request for account password")
            bd.fired_rules.append("PARAM_REQ_PASSWORD")
        elif fin:
            score = 20
            bd.reasons.append("Request for sensitive financial credentials")
            bd.fired_rules.append("PARAM_REQ_FINANCIAL_CRED")
        else:
            score = 15
            bd.reasons.append("Request for confidential information")
            bd.fired_rules.append("PARAM_REQ_CONFIDENTIAL")

    elif moneys:
        amounts = [m.amount for m in moneys if m.amount is not None]
        max_amt = max(amounts, default=0.0)
        if max_amt and max_amt >= 50_000:
            score = 20
            bd.reasons.append(f"Request to transfer ₹{max_amt:,.0f}")
            bd.fired_rules.append("PARAM_REQ_MONEY_HIGH")
        else:
            score = 15
            bd.reasons.append(
                f"Money transfer request detected"
                + (f" (₹{max_amt:,.0f})" if max_amt else "")
            )
            bd.fired_rules.append("PARAM_REQ_MONEY")

    return min(score, CAP_REQUEST)


# ── Behavior scoring (max 20) ─────────────────────────────────────────────────

def _score_behavior(params: CallParameters, bd: ScoreBreakdown) -> int:
    score = 0
    sev_order = {"high": 2, "medium": 1, "low": 0}
    tactics = params.behavior.deduped()

    # Only count tactics that were actually detected
    detected = [t for t in tactics if t.status == "detected"]
    urgency_tacs    = [t for t in detected if t.tactic_type in ("urgency", "threat")]
    secrecy_tacs    = [t for t in detected if t.tactic_type == "secrecy"]
    emotional_tacs  = [t for t in detected if t.tactic_type == "emotional"]
    repeated_tacs   = [t for t in detected if t.tactic_type == "repeated_demand"]
    bypass_tacs     = [t for t in detected if t.tactic_type == "resistance_to_verification"]

    if urgency_tacs:
        max_sev = max(urgency_tacs, key=lambda t: sev_order.get(t.severity, 0)).severity
        if max_sev == "high":
            score += 15
            bd.reasons.append("High urgency or threats detected")
            bd.fired_rules.append("PARAM_BEHAVIOR_URGENCY_HIGH")
        elif max_sev == "medium":
            score += 10
            bd.reasons.append("Urgency pressure tactics detected")
            bd.fired_rules.append("PARAM_BEHAVIOR_URGENCY_MED")
        else:
            score += 5
            bd.reasons.append("Time pressure indicators")
            bd.fired_rules.append("PARAM_BEHAVIOR_URGENCY_LOW")

    if secrecy_tacs:
        score += 5
        bd.reasons.append("Secrecy or isolation tactics detected")
        bd.fired_rules.append("PARAM_BEHAVIOR_SECRECY")

    if emotional_tacs:
        score += 5
        bd.reasons.append("Emotional manipulation detected")
        bd.fired_rules.append("PARAM_BEHAVIOR_EMOTIONAL")

    if repeated_tacs:
        score = min(score + 3, CAP_BEHAVIOR)
        bd.reasons.append("Repeated demands detected")
        bd.fired_rules.append("PARAM_BEHAVIOR_REPEATED")

    if bypass_tacs:
        score = min(score + 3, CAP_BEHAVIOR)
        bd.reasons.append("Resistance to verification attempts")
        bd.fired_rules.append("PARAM_BEHAVIOR_BYPASS")

    return min(score, CAP_BEHAVIOR)


# ── Channel scoring (max 15) ──────────────────────────────────────────────────

def _score_channel(params: CallParameters, bd: ScoreBreakdown) -> int:
    score = 0
    ch = params.channel.channel_status

    if ch == "MISMATCH":
        score = 15
        bd.reasons.append("Communication channel mismatch with verified records")
        bd.fired_rules.append("PARAM_CHANNEL_MISMATCH")
    elif ch == "UNKNOWN":
        # Only penalise if there is also an identity claim
        primary = params.identity.primary
        if primary and primary.status == "detected":
            score = 10
            bd.reasons.append("Identity claimed from unknown/unsaved number")
            bd.fired_rules.append("PARAM_CHANNEL_UNKNOWN")
        # No identity claim from unknown number → do NOT penalise
    # VERIFIED → 0 points

    return min(score, CAP_CHANNEL)


# ── Voice scoring (max 10, soft signal) ───────────────────────────────────────

def _score_voice(params: CallParameters, bd: ScoreBreakdown) -> int:
    v = params.voice

    # Only score when voice layer actually ran and succeeded
    if v.status not in ("ok", "inconclusive"):
        return 0  # unavailable / not_analyzed / error → 0, never negative

    if v.spoof_prob is None:
        return 0

    score = 0
    if v.spoof_prob >= 0.80:
        score += 10
        bd.reasons.append("Voice analysis indicates synthetic speech (experimental)")
        bd.fired_rules.append("PARAM_VOICE_SPOOF_HIGH")
    elif v.spoof_prob >= 0.60:
        score += 5
        bd.reasons.append("Possible synthetic voice indicators (experimental)")
        bd.fired_rules.append("PARAM_VOICE_SPOOF_MED")

    # Voiceprint mismatch (within cap)
    if v.speaker_match is False:
        score = min(score + 5, CAP_VOICE)
        bd.reasons.append("Voice doesn't match enrolled voiceprint (experimental)")
        bd.fired_rules.append("PARAM_VOICE_MISMATCH")

    return min(score, CAP_VOICE)


# ── Hard-rule floors ──────────────────────────────────────────────────────────

def _apply_floors(preliminary: int, params: CallParameters, bd: ScoreBreakdown) -> int:
    max_floor = preliminary

    # Floor 1: OTP/PIN request on non-verified channel → CRITICAL (75)
    # has_otp_or_pin must only count detected items
    detected_otp_pin = any(
        c.status == "detected" and c.credential_type in ("otp", "pin")
        for c in params.requests.deduped_creds()
    )
    if (detected_otp_pin
            and params.channel.channel_status != "VERIFIED"):
        if 75 > max_floor:
            max_floor = 75
            bd.applied_floors.append("OTP request on non-verified channel")
            bd.reasons.append(
                "OTP/PIN request on unverified channel triggers minimum CRITICAL risk"
            )
            logger.info(f"[{params.call_id}] Floor FLOOR_OTP_NONVERIFIED applied → 75")

    # Floor 2: Money + secrecy + channel mismatch → HIGH (50)
    has_money = any(m.status == "detected" for m in params.requests.money)
    has_secrecy = params.behavior.has_secrecy
    is_mismatch = params.channel.channel_status == "MISMATCH"
    if has_money and has_secrecy and is_mismatch:
        if 50 > max_floor:
            max_floor = 50
            bd.applied_floors.append("Money + secrecy + channel mismatch")
            bd.reasons.append(
                "Money request combined with secrecy and channel mismatch"
            )
            logger.info(f"[{params.call_id}] Floor FLOOR_MONEY_SECRECY_MISMATCH → 50")

    # Floor 3: Relative claim + spoof + unverified → HIGH (50)
    is_relative = (
        params.identity.primary is not None
        and params.identity.primary.claimed_relationship == "relative"
    )
    spoof_high = (
        params.voice.status in ("ok", "inconclusive")
        and params.voice.spoof_prob is not None
        and params.voice.spoof_prob >= 0.80
    )
    not_verified = params.channel.channel_status != "VERIFIED"
    if is_relative and spoof_high and not_verified:
        if 50 > max_floor:
            max_floor = 50
            bd.applied_floors.append("Relative claim + spoof evidence + unverified channel")
            bd.reasons.append(
                "Family member claim with synthetic voice on unverified number"
            )
            logger.info(f"[{params.call_id}] Floor FLOOR_VOICE_RELATIVE_NONVERIFIED → 50")

    return max_floor
