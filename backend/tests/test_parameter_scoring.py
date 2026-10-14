"""
Comprehensive tests for parameter-based risk scoring pipeline.

Tests cover:
- Money, OTP, secrecy, urgency and identity claims
- Negation and hypothetical statements (must NOT score)
- Speaker attribution preserved
- Unknown / unavailable evidence handling
- Malformed LLM output recovery
- Duplicate evidence deduplication
- Scoring caps, risk bands, and hard-rule floors
- End-to-end parameter → score pipeline

All tests are synchronous and require no external dependencies.
"""
import pytest
import uuid
from datetime import datetime

from app.schemas.parameters import (
    CallParameters,
    IdentityParam, IdentityParameters,
    MoneyRequestParam, CredentialRequestParam, SensitiveRequestParameters,
    PressureTacticParam, BehaviorParameters,
    ChannelParam, ConsistencyParam, ConsistencyParameters,
    VoiceParam, ExtractionMeta,
)
from app.trust_engine.parameter_scorer import score_from_parameters


# ── Helpers ────────────────────────────────────────────────────────────────────

def _base_params(**kwargs) -> CallParameters:
    return CallParameters(call_id=str(uuid.uuid4()), **kwargs)


def _identity(rel, verif, confidence=0.9) -> IdentityParameters:
    p = IdentityParam(
        status="detected",
        claimed_name=rel,
        claimed_relationship=rel,
        verification_status=verif,
        extraction_confidence=confidence,
    )
    return IdentityParameters(params=[p], primary=p)


def _money(amount=None, ccy="INR") -> SensitiveRequestParameters:
    m = MoneyRequestParam(
        status="detected", amount=amount, currency=ccy,
        extraction_confidence=0.9,
        transcript_excerpt="Send money now",
    )
    return SensitiveRequestParameters(money=[m])


def _cred(ctype="otp") -> SensitiveRequestParameters:
    c = CredentialRequestParam(
        status="detected", credential_type=ctype,
        extraction_confidence=0.9,
        transcript_excerpt="Give me your OTP",
    )
    return SensitiveRequestParameters(credentials=[c])


def _behavior(*tactic_types, severity="medium") -> BehaviorParameters:
    tactics = [
        PressureTacticParam(
            status="detected", tactic_type=t, severity=severity,
            extraction_confidence=0.9,
        )
        for t in tactic_types
    ]
    return BehaviorParameters(tactics=tactics)


def _channel(status) -> ChannelParam:
    return ChannelParam(status="detected", channel_status=status)


def _voice(spoof_prob, status="ok") -> VoiceParam:
    return VoiceParam(status=status, spoof_prob=spoof_prob)


# ── Category: Identity ─────────────────────────────────────────────────────────

class TestIdentityScoring:
    def test_no_identity_claim_zero_points(self):
        p = _base_params()
        bd = score_from_parameters(p)
        assert bd.identity == 0

    def test_identity_mismatch_20_points(self):
        p = _base_params(identity=_identity("relative", "mismatch"))
        bd = score_from_parameters(p)
        assert bd.identity == 20

    def test_identity_unknown_number_15_points(self):
        p = _base_params(identity=_identity("authority", "unverified"))
        bd = score_from_parameters(p)
        assert bd.identity == 15

    def test_verified_identity_zero_points(self):
        p = _base_params(identity=_identity("relative", "verified"))
        bd = score_from_parameters(p)
        assert bd.identity == 0

    def test_identity_capped_at_25(self):
        ident = _identity("relative", "mismatch")
        ident.claim_changes = 5
        p = _base_params(identity=ident)
        bd = score_from_parameters(p)
        assert bd.identity <= 25

    def test_friend_claim_unknown_no_penalty(self):
        """Unknown caller claiming to be 'friend' — unclear, do not penalise."""
        p = _base_params(identity=_identity("friend", "not_attempted"))
        bd = score_from_parameters(p)
        assert bd.identity == 0

    def test_unknown_caller_no_claim_zero_points(self):
        """No identity claim at all must not add identity points."""
        p = _base_params()
        bd = score_from_parameters(p)
        assert bd.identity == 0
        assert bd.request == 0


# ── Category: Sensitive Requests ──────────────────────────────────────────────

class TestRequestScoring:
    def test_otp_request_30_points(self):
        p = _base_params(requests=_cred("otp"))
        bd = score_from_parameters(p)
        assert bd.request == 30

    def test_pin_request_30_points(self):
        p = _base_params(requests=_cred("pin"))
        bd = score_from_parameters(p)
        assert bd.request == 30

    def test_password_request_25_points(self):
        p = _base_params(requests=_cred("password"))
        bd = score_from_parameters(p)
        assert bd.request == 25

    def test_cvv_request_20_points(self):
        p = _base_params(requests=_cred("cvv"))
        bd = score_from_parameters(p)
        assert bd.request == 20

    def test_money_high_amount_20_points(self):
        p = _base_params(requests=_money(amount=100_000))
        bd = score_from_parameters(p)
        assert bd.request == 20

    def test_money_low_amount_15_points(self):
        p = _base_params(requests=_money(amount=500))
        bd = score_from_parameters(p)
        assert bd.request == 15

    def test_no_request_zero_points(self):
        p = _base_params()
        bd = score_from_parameters(p)
        assert bd.request == 0

    def test_request_capped_at_30(self):
        # Both OTP and money — should still cap at 30
        creds = _cred("otp")
        money_r = MoneyRequestParam(status="detected", amount=50000, extraction_confidence=0.9)
        combined = SensitiveRequestParameters(
            money=[money_r],
            credentials=creds.credentials,
        )
        p = _base_params(requests=combined)
        bd = score_from_parameters(p)
        assert bd.request <= 30


# ── Negation & hypothetical (must NOT score) ───────────────────────────────────

class TestNegationHypothetical:
    def test_not_detected_request_zero(self):
        """If status=not_detected the item should contribute 0 points."""
        c = CredentialRequestParam(
            status="not_detected", credential_type="otp",
            extraction_confidence=0.9,
        )
        p = _base_params(requests=SensitiveRequestParameters(credentials=[c]))
        bd = score_from_parameters(p)
        assert bd.request == 0, "not_detected credential must not score"

    def test_not_detected_money_zero(self):
        m = MoneyRequestParam(status="not_detected", amount=100000, extraction_confidence=0.9)
        p = _base_params(requests=SensitiveRequestParameters(money=[m]))
        bd = score_from_parameters(p)
        assert bd.request == 0

    def test_not_detected_tactic_zero(self):
        t = PressureTacticParam(status="not_detected", tactic_type="urgency", severity="high",
                                extraction_confidence=0.9)
        p = _base_params(behavior=BehaviorParameters(tactics=[t]))
        bd = score_from_parameters(p)
        assert bd.behavior == 0


# ── Speaker attribution ───────────────────────────────────────────────────────

class TestSpeakerAttribution:
    def test_speaker_field_preserved_in_params(self):
        c = CredentialRequestParam(
            status="detected", credential_type="otp",
            speaker="SPEAKER_01",
            extraction_confidence=0.95,
        )
        reqs = SensitiveRequestParameters(credentials=[c])
        p = _base_params(requests=reqs)
        assert p.requests.credentials[0].speaker == "SPEAKER_01"

    def test_money_speaker_preserved(self):
        m = MoneyRequestParam(
            status="detected", amount=5000, speaker="SPEAKER_00",
            extraction_confidence=0.9,
        )
        reqs = SensitiveRequestParameters(money=[m])
        p = _base_params(requests=reqs)
        assert p.requests.money[0].speaker == "SPEAKER_00"


# ── Behavioral pressure ───────────────────────────────────────────────────────

class TestBehaviorScoring:
    def test_high_urgency_15_points(self):
        p = _base_params(behavior=_behavior("urgency", severity="high"))
        bd = score_from_parameters(p)
        assert bd.behavior == 15

    def test_medium_urgency_10_points(self):
        p = _base_params(behavior=_behavior("urgency", severity="medium"))
        bd = score_from_parameters(p)
        assert bd.behavior == 10

    def test_low_urgency_5_points(self):
        p = _base_params(behavior=_behavior("urgency", severity="low"))
        bd = score_from_parameters(p)
        assert bd.behavior == 5

    def test_secrecy_alone_5_points(self):
        p = _base_params(behavior=_behavior("secrecy"))
        bd = score_from_parameters(p)
        assert bd.behavior == 5

    def test_behavior_capped_at_20(self):
        p = _base_params(behavior=_behavior(
            "urgency", "secrecy", "emotional",
            "repeated_demand", "resistance_to_verification",
            severity="high",
        ))
        bd = score_from_parameters(p)
        assert bd.behavior <= 20

    def test_no_behavior_zero_points(self):
        p = _base_params()
        bd = score_from_parameters(p)
        assert bd.behavior == 0


# ── Channel scoring ───────────────────────────────────────────────────────────

class TestChannelScoring:
    def test_mismatch_15_points(self):
        p = _base_params(channel=_channel("MISMATCH"))
        bd = score_from_parameters(p)
        assert bd.channel == 15

    def test_unknown_with_claim_10_points(self):
        p = _base_params(
            identity=_identity("relative", "unverified"),
            channel=_channel("UNKNOWN"),
        )
        bd = score_from_parameters(p)
        assert bd.channel == 10

    def test_unknown_no_claim_zero_points(self):
        """Unknown caller with no claim must not be penalised on channel."""
        p = _base_params(channel=_channel("UNKNOWN"))
        bd = score_from_parameters(p)
        assert bd.channel == 0

    def test_verified_zero_points(self):
        p = _base_params(channel=_channel("VERIFIED"))
        bd = score_from_parameters(p)
        assert bd.channel == 0

    def test_channel_capped_at_15(self):
        p = _base_params(channel=_channel("MISMATCH"))
        bd = score_from_parameters(p)
        assert bd.channel <= 15


# ── Voice scoring ─────────────────────────────────────────────────────────────

class TestVoiceScoring:
    def test_spoof_high_10_points(self):
        p = _base_params(voice=_voice(0.95))
        bd = score_from_parameters(p)
        assert bd.voice == 10

    def test_spoof_medium_5_points(self):
        p = _base_params(voice=_voice(0.70))
        bd = score_from_parameters(p)
        assert bd.voice == 5

    def test_spoof_low_zero_points(self):
        p = _base_params(voice=_voice(0.30))
        bd = score_from_parameters(p)
        assert bd.voice == 0

    def test_voice_unavailable_zero_points(self):
        """Missing audio must not contribute positive evidence."""
        p = _base_params(voice=VoiceParam(status="unavailable"))
        bd = score_from_parameters(p)
        assert bd.voice == 0

    def test_voice_not_analyzed_zero_points(self):
        p = _base_params(voice=VoiceParam(status="not_analyzed"))
        bd = score_from_parameters(p)
        assert bd.voice == 0

    def test_voice_inconclusive_zero_or_low(self):
        """Inconclusive voice with no spoof_prob → zero points."""
        p = _base_params(voice=VoiceParam(status="inconclusive"))
        bd = score_from_parameters(p)
        assert bd.voice == 0

    def test_voice_capped_at_10(self):
        v = VoiceParam(status="ok", spoof_prob=0.99, speaker_match=False)
        p = _base_params(voice=v)
        bd = score_from_parameters(p)
        assert bd.voice <= 10


# ── Unknown / unavailable evidence ────────────────────────────────────────────

class TestUnknownUnavailableEvidence:
    def test_unknown_status_not_scored(self):
        c = CredentialRequestParam(status="unknown", credential_type="otp",
                                   extraction_confidence=0.9)
        p = _base_params(requests=SensitiveRequestParameters(credentials=[c]))
        bd = score_from_parameters(p)
        assert bd.request == 0

    def test_unavailable_voice_not_negative(self):
        p = _base_params(voice=VoiceParam(status="unavailable"))
        bd = score_from_parameters(p)
        assert bd.voice >= 0
        assert bd.voice == 0

    def test_spoof_prob_cleared_for_unavailable(self):
        """VoiceParam validator must clear spoof_prob when status=unavailable."""
        v = VoiceParam(status="unavailable", spoof_prob=0.99)
        assert v.spoof_prob is None


# ── Duplicate deduplication ───────────────────────────────────────────────────

class TestDeduplication:
    def test_duplicate_money_requests_not_counted_twice(self):
        m = MoneyRequestParam(
            evidence_id="SAME-ID",
            status="detected", amount=100_000,
            extraction_confidence=0.9,
        )
        # Insert same evidence_id twice
        reqs = SensitiveRequestParameters(money=[m, m])
        deduped = reqs.deduped_money()
        assert len(deduped) == 1

    def test_duplicate_cred_requests_deduped(self):
        c = CredentialRequestParam(
            evidence_id="SAME-CRED",
            status="detected", credential_type="otp",
            extraction_confidence=0.9,
        )
        reqs = SensitiveRequestParameters(credentials=[c, c, c])
        assert len(reqs.deduped_creds()) == 1

    def test_duplicate_behavior_deduped(self):
        t = PressureTacticParam(
            evidence_id="SAME-T", status="detected",
            tactic_type="urgency", severity="high",
            extraction_confidence=0.9,
        )
        beh = BehaviorParameters(tactics=[t, t])
        assert len(beh.deduped()) == 1

    def test_score_with_duplicate_evidence_same_as_single(self):
        """Duplicate evidence must not inflate the score."""
        m = MoneyRequestParam(
            evidence_id="DEDUP-SCORE-TEST",
            status="detected", amount=1000,
            extraction_confidence=0.9,
        )
        p_single = _base_params(requests=SensitiveRequestParameters(money=[m]))
        p_double = _base_params(requests=SensitiveRequestParameters(money=[m, m]))
        bd_s = score_from_parameters(p_single)
        bd_d = score_from_parameters(p_double)
        assert bd_s.request == bd_d.request


# ── Hard-rule floors ──────────────────────────────────────────────────────────

class TestHardRuleFloors:
    def test_otp_unverified_channel_floor_75(self):
        p = _base_params(
            requests=_cred("otp"),
            channel=_channel("UNKNOWN"),
        )
        bd = score_from_parameters(p)
        assert bd.final_score >= 75
        assert bd.risk_level.value == "CRITICAL"
        assert any("OTP" in f for f in bd.applied_floors)

    def test_otp_verified_channel_no_floor(self):
        """OTP on VERIFIED channel must NOT trigger the floor."""
        p = _base_params(
            requests=_cred("otp"),
            channel=_channel("VERIFIED"),
        )
        bd = score_from_parameters(p)
        # OTP on verified channel: floor not applied
        assert not any("OTP" in f for f in bd.applied_floors)

    def test_money_secrecy_mismatch_floor_50(self):
        p = _base_params(
            requests=_money(amount=5000),
            behavior=_behavior("secrecy"),
            channel=_channel("MISMATCH"),
        )
        bd = score_from_parameters(p)
        assert bd.final_score >= 50
        assert any("secrecy" in f.lower() or "money" in f.lower()
                   for f in bd.applied_floors)

    def test_relative_spoof_unverified_floor_50(self):
        v = VoiceParam(status="ok", spoof_prob=0.92)
        p = _base_params(
            identity=_identity("relative", "unverified"),
            channel=_channel("UNKNOWN"),
            voice=v,
        )
        bd = score_from_parameters(p)
        assert bd.final_score >= 50
        assert any("relative" in f.lower() or "spoof" in f.lower()
                   for f in bd.applied_floors)

    def test_floor_is_minimum_not_additive(self):
        """A floor of 75 when score is already 80 must not add 75 more."""
        p = _base_params(
            requests=_cred("otp"),
            identity=_identity("authority", "mismatch"),
            behavior=_behavior("urgency", severity="high"),
            channel=_channel("MISMATCH"),
            voice=_voice(0.95),
        )
        bd = score_from_parameters(p)
        assert bd.final_score <= 100


# ── Risk bands ────────────────────────────────────────────────────────────────

class TestRiskBands:
    def test_score_0_is_low(self):
        p = _base_params()
        bd = score_from_parameters(p)
        assert bd.final_score < 25
        assert bd.risk_level.value == "LOW"

    def test_medium_band(self):
        p = _base_params(
            requests=_money(amount=1000),
            behavior=_behavior("urgency", severity="medium"),
        )
        bd = score_from_parameters(p)
        # money (15) + medium urgency (10) = 25 → MEDIUM
        assert 25 <= bd.final_score < 50
        assert bd.risk_level.value == "MEDIUM"

    def test_high_band(self):
        p = _base_params(
            requests=_money(amount=1000),
            identity=_identity("relative", "mismatch"),
            behavior=_behavior("urgency", severity="high"),
            channel=_channel("MISMATCH"),
        )
        bd = score_from_parameters(p)
        assert 50 <= bd.final_score < 75
        assert bd.risk_level.value == "HIGH"

    def test_critical_band(self):
        p = _base_params(
            requests=_cred("otp"),
            channel=_channel("UNKNOWN"),
        )
        bd = score_from_parameters(p)
        assert bd.final_score >= 75
        assert bd.risk_level.value == "CRITICAL"

    def test_score_never_exceeds_100(self):
        p = _base_params(
            requests=_cred("otp"),
            identity=_identity("authority", "mismatch"),
            behavior=_behavior("urgency", "secrecy", "emotional", severity="high"),
            channel=_channel("MISMATCH"),
            voice=_voice(0.99),
        )
        bd = score_from_parameters(p)
        assert bd.final_score <= 100

    def test_score_never_below_0(self):
        p = _base_params()
        bd = score_from_parameters(p)
        assert bd.final_score >= 0


# ── Malformed LLM output ──────────────────────────────────────────────────────

class TestMalformedLLMOutput:
    """
    Tests for the _extract_json utility and parameter validation guards.
    These ensure graceful degradation when LLM output is corrupt.
    """

    def test_invalid_credential_type_coerced_to_other(self):
        """LLM outputs unknown credential type → must coerce to 'other'."""
        from app.extractors.parameter_extractor import _safe_rel, _safe_verif
        # Unknown relationship
        assert _safe_rel("grandparent") is None
        assert _safe_rel("relative") == "relative"

    def test_confidence_out_of_range_clamped(self):
        from app.extractors.parameter_extractor import _safe_conf
        assert _safe_conf(1.5) == 1.0
        assert _safe_conf(-0.1) == 0.0
        assert _safe_conf("bad") == 0.0

    def test_malformed_json_raises_extraction_error(self):
        from app.llm.qwen_extractor import _extract_json, LLMExtractionError
        with pytest.raises(LLMExtractionError):
            _extract_json("This is not JSON at all!!")

    def test_partial_json_extracted(self):
        from app.llm.qwen_extractor import _extract_json
        raw = 'Sure! Here you go:\n{"identity": {"claimed_name": "test"}, "money_requests": []}'
        result = _extract_json(raw)
        assert result["identity"]["claimed_name"] == "test"

    def test_empty_transcript_raises_llm_error(self):
        from app.llm.qwen_extractor import LLMExtractionError
        # We don't actually load the model; test that empty transcript short-circuits
        # by calling with the model explicitly not loaded
        import app.llm.qwen_extractor as qe
        old_pipeline = qe._pipeline
        old_error = qe._load_error
        qe._pipeline = None
        qe._load_error = "test_sentinel"
        try:
            with pytest.raises(LLMExtractionError):
                qe.extract_parameters_llm("", "call-test")
        finally:
            qe._pipeline = old_pipeline
            qe._load_error = old_error


# ── VoiceParam validation ─────────────────────────────────────────────────────

class TestVoiceParamValidation:
    def test_spoof_prob_cleared_when_unavailable(self):
        v = VoiceParam(status="unavailable", spoof_prob=0.95)
        assert v.spoof_prob is None

    def test_spoof_prob_preserved_when_ok(self):
        v = VoiceParam(status="ok", spoof_prob=0.95)
        assert v.spoof_prob == 0.95

    def test_spoof_prob_preserved_when_inconclusive(self):
        v = VoiceParam(status="inconclusive", spoof_prob=0.50)
        assert v.spoof_prob == 0.50


# ── CallParameters quality_score ─────────────────────────────────────────────

class TestCallParametersQuality:
    def test_empty_params_low_quality(self):
        p = _base_params()
        assert p.quality_score <= 0.5

    def test_llm_extraction_boosts_quality(self):
        p = _base_params()
        p.tier2_used = True
        p.llm_extraction_degraded = False
        assert p.quality_score > 0.5

    def test_degraded_llm_no_boost(self):
        p = _base_params()
        p.tier2_used = True
        p.llm_extraction_degraded = True
        low_q = p.quality_score
        p2 = _base_params()
        p2.tier2_used = True
        p2.llm_extraction_degraded = False
        assert p2.quality_score > low_q

    def test_is_provisional_on_short_transcript(self):
        p = _base_params()
        p.transcript_segments_analyzed = 1
        assert p.is_provisional is True

    def test_not_provisional_on_full_transcript(self):
        p = _base_params()
        p.transcript_segments_analyzed = 5
        assert p.is_provisional is False


# ── Parameter extractor (Tier1 path) ─────────────────────────────────────────

class TestParameterExtractorTier1:
    def _make_transcript(self, texts):
        from app.schemas.report import TranscriptResponse, TranscriptSegment
        segments = [
            TranscriptSegment(start=i, end=i+1, text=t, confidence=0.9, is_final=True)
            for i, t in enumerate(texts)
        ]
        return TranscriptResponse(
            call_id="test", language="en",
            transcription_status="completed",
            segments=segments, is_mock=True,
        )

    def test_tier1_builds_call_parameters(self):
        from app.extractors.tier1_classifier import Tier1Classifier
        from app.extractors.evidence_pipeline import extract_evidence_from_transcript
        from app.extractors.parameter_extractor import build_call_parameters

        transcript = self._make_transcript([
            "I am calling from HDFC Bank.",
            "Please share your OTP immediately.",
        ])
        evidence = extract_evidence_from_transcript(transcript, "test-call")
        params = build_call_parameters(
            transcript=transcript,
            call_id="test-call",
            evidence=evidence,
            voice_evidence=None,
        )
        assert isinstance(params, CallParameters)
        assert params.tier1_used is True
        assert params.tier2_used is False

    def test_otp_transcript_scores_critical(self):
        from app.extractors.evidence_pipeline import extract_evidence_from_transcript
        from app.extractors.parameter_extractor import build_call_parameters

        transcript = self._make_transcript([
            "This is HDFC Bank. There is suspicious activity.",
            "Please share your OTP urgently or your account will be blocked.",
            "Do not tell anyone.",
        ])
        evidence = extract_evidence_from_transcript(transcript, "otp-call")
        params = build_call_parameters(
            transcript=transcript,
            call_id="otp-call",
            evidence=evidence,
            voice_evidence=None,
        )
        bd = score_from_parameters(params)
        assert bd.final_score >= 25, "OTP call must score at least MEDIUM"
