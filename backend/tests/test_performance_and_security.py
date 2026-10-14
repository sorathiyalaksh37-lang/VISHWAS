"""
Performance, Latency Benchmarks, and Security / PII Masking Verification.
Validates:
1. Deterministic Trust Judge evaluation latency (< 5ms).
2. ASR deduplication throughput and latency.
3. PII masking verification across incoming messages (Aadhaar, cards, OTPs, phone numbers).
4. Memory bounding and backpressure under burst traffic.
"""
import asyncio
import time
import pytest
from app.audio.incremental_asr import IncrementalASR
from app.extractors.pii_masker import get_pii_masker
from app.schemas.evidence import (
    BehaviorEvidence,
    ClaimEvidence,
    ClaimsEvidence,
    CredentialRequest,
    MoneyRequest,
    RequestEvidence,
    UrgencyEvidence,
    VoiceEvidence,
)
from app.schemas.live_session import LiveSessionStartRequest
from app.schemas.parameters import (
    CallParameters,
    IdentityParameters,
    IdentityParam,
    SensitiveRequestParameters,
    CredentialRequestParam,
    BehaviorParameters,
    PressureTacticParam,
)
from app.services.live_session_manager import LiveSessionManager, MAX_PAYLOAD_SIZE
from app.trust_engine.judge import TrustJudge
from app.trust_engine.parameter_scorer import score_from_parameters


class TestPerformanceBenchmarks:
    """Performance and latency benchmarks for real-time operation."""

    def test_trust_judge_deterministic_latency_sub_5ms(self):
        """Trust Judge deterministic scoring must execute in under 5ms."""
        id_p = IdentityParam(
            status="detected",
            claimed_name="bank",
            claimed_relationship="organization",
            verification_status="unverified",
            extraction_confidence=0.9,
        )
        call_params = CallParameters(
            call_id="perf-benchmark-call",
            identity=IdentityParameters(params=[id_p], primary=id_p),
            requests=SensitiveRequestParameters(
                credentials=[
                    CredentialRequestParam(
                        status="detected",
                        credential_type="otp",
                        extraction_confidence=0.9,
                    )
                ]
            ),
            behavior=BehaviorParameters(
                tactics=[
                    PressureTacticParam(
                        status="detected",
                        tactic_type="urgency",
                        extraction_confidence=0.9,
                    )
                ]
            ),
        )

        # Warm up
        for _ in range(10):
            score_from_parameters(call_params)

        # Benchmark 100 runs
        runs = 100
        start = time.perf_counter()
        for _ in range(runs):
            res = score_from_parameters(call_params)
            assert res.final_score >= 75
        elapsed_total = time.perf_counter() - start
        avg_latency_ms = (elapsed_total / runs) * 1000

        print(f"\n[BENCHMARK] Trust Judge average latency: {avg_latency_ms:.3f} ms / evaluation")
        assert avg_latency_ms < 5.0, f"Judge latency {avg_latency_ms:.3f}ms exceeded 5ms SLA"

    def test_asr_deduplication_latency_sub_10ms(self):
        """Sliding-window text deduplication must run in under 10ms."""
        finalized_text = "This is a long ongoing call where the caller has stated their credentials and authority."
        window_text = "stated their credentials and authority. Please read out your one time password immediately."

        # Warmup
        for _ in range(10):
            IncrementalASR._deduplicate(window_text, finalized_text)

        runs = 200
        start = time.perf_counter()
        for _ in range(runs):
            deduped = IncrementalASR._deduplicate(window_text, finalized_text)
            assert "one time password" in deduped
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / runs) * 1000

        print(f"\n[BENCHMARK] ASR deduplication latency: {avg_ms:.3f} ms / window")
        assert avg_ms < 10.0, f"Deduplication latency {avg_ms:.3f}ms exceeded 10ms threshold"


class TestSecurityAndPIIMasking:
    """Validates that sensitive user PII is masked before downstream exposure."""

    def test_pii_masker_redacts_credentials_and_personal_data(self):
        """Verify credit cards, phone numbers, Aadhaar, and OTPs are redacted."""
        masker = get_pii_masker()

        raw_text = (
            "My Aadhaar number is 9876 5432 1098 and my card is 4532-1234-5678-9012. "
            "Your OTP is 482910 on phone +91-9876543210."
        )

        masked_text, pii_found = masker.mask_text(raw_text, audit=False)

        # Raw values must NOT appear in masked text
        assert "9876 5432 1098" not in masked_text
        assert "4532-1234-5678-9012" not in masked_text
        assert "482910" not in masked_text

        # Mask tokens should be present
        assert "[MASKED_AADHAAR]" in masked_text
        assert "[MASKED_CARD]" in masked_text
        assert "[MASKED_CVV]" in masked_text
        assert "[MASKED_PHONE]" in masked_text

    @pytest.mark.asyncio
    async def test_oversized_audio_payload_protection(self):
        """Reject audio chunks exceeding maximum payload cap (64KB)."""
        mgr = LiveSessionManager()
        req = LiveSessionStartRequest(mode="webrtc", audio_authorized=True)
        session = await mgr.create_session("user-payload-test", req)

        oversized_data = b"\x00" * (MAX_PAYLOAD_SIZE + 1024)
        ok = await mgr.submit_audio_chunk(
            session_id=session.session_id,
            user_id="user-payload-test",
            sequence_number=1,
            timestamp_ms=100,
            sample_rate=16000,
            channel_count=1,
            audio_data=oversized_data,
        )
        assert ok is False
        assert session.total_chunks_received == 0
        await mgr.cancel_session(session.session_id, "user-payload-test")
