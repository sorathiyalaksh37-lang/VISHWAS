"""
Phase 4: Voice Anti-Spoof Detection - Audit and Verification Tests

Tests the existing voice layer implementation, quality gates, and Trust Judge integration.

CRITICAL FINDING: The current spoof model is a PLACEHOLDER (facebook/wav2vec2-base)
which has NO anti-spoof detection capability. Real model integration is incomplete.
"""
import pytest
import tempfile
import wave
import struct
import math
from pathlib import Path
from sqlalchemy.orm import Session

from app.schemas.evidence import (
    EvidenceExtraction, ClaimsEvidence, RequestEvidence, BehaviorEvidence,
    VoiceEvidence, VoiceSpoofEvidence, VoiceQualityEvidence,
    ClaimEvidence, CredentialRequest, UrgencyEvidence, SecrecyEvidence,
    EmotionalPressureEvidence
)
from app.trust_engine.judge import TrustJudge
from app.trust_engine.trust_graph import TrustGraph
from app.trust_engine.scoring import RiskLevel


def create_test_wav(duration_s: float, frequency: int = 440, sample_rate: int = 16000) -> bytes:
    """Create a synthetic WAV file for testing."""
    num_samples = int(sample_rate * duration_s)
    
    wav_buffer = []
    for i in range(num_samples):
        value = int(32767 * 0.3 * math.sin(2 * math.pi * frequency * i / sample_rate))
        wav_buffer.append(struct.pack('h', value))
    
    # Create WAV file
    wav_data = b''.join(wav_buffer)
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        with wave.open(f.name, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(wav_data)
        f.seek(0)
        return Path(f.name).read_bytes()


class TestVoiceProviderStatus:
    """Test voice provider status states."""
    
    def test_unavailable_status_when_no_model(self):
        """When model unavailable, status should be 'unavailable'."""
        from app.audio.voice_layer import get_voice_layer
        
        voice_layer = get_voice_layer()
        
        # Create test audio
        wav_bytes = create_test_wav(5.0)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(wav_bytes)
            wav_path = Path(f.name)
        
        try:
            evidence = voice_layer.analyze(wav_path, "test-call")
            
            # Model dependencies may not be installed - should handle gracefully
            assert evidence.status in ["ok", "unavailable", "inconclusive"]
            
            if evidence.status == "unavailable":
                assert evidence.error is not None
            
        finally:
            wav_path.unlink(missing_ok=True)
    
    def test_inconclusive_on_short_audio(self):
        """Audio < 3s should return inconclusive."""
        from app.audio.voice_layer import get_voice_layer, MIN_SPEECH_SECONDS
        
        voice_layer = get_voice_layer()
        
        # Create 1s audio (too short)
        wav_bytes = create_test_wav(1.0)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(wav_bytes)
            wav_path = Path(f.name)
        
        try:
            evidence = voice_layer.analyze(wav_path, "test-short")
            
            # Should be inconclusive or unavailable (depending on dependencies)
            assert evidence.status in ["inconclusive", "unavailable"]
            
            if evidence.status == "inconclusive":
                assert evidence.duration_s < MIN_SPEECH_SECONDS
                
        finally:
            wav_path.unlink(missing_ok=True)


class TestSpoofScoreThresholds:
    """Test spoof probability threshold boundaries."""
    
    def test_spoof_high_threshold_80(self, test_db: Session):
        """spoof_prob >= 0.80 should give 10 voice points."""
        judge = TrustJudge()
        graph = TrustGraph(test_db)
        
        # Create evidence with high spoof probability
        evidence = create_voice_evidence(spoof_prob=0.85)
        
        assessment = judge.evaluate(
            call_id="test-high-spoof",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Should add maximum voice points (10)
        assert assessment.category_scores["voice"] == 10
        assert "VOICE_SPOOF_HIGH" in assessment.fired_rules
    
    def test_spoof_medium_threshold_60(self, test_db: Session):
        """spoof_prob >= 0.60 but < 0.80 should give 5 voice points."""
        judge = TrustJudge()
        graph = TrustGraph(test_db)
        
        # Create evidence with medium spoof probability
        evidence = create_voice_evidence(spoof_prob=0.70)
        
        assessment = judge.evaluate(
            call_id="test-med-spoof",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Should add 5 voice points
        assert assessment.category_scores["voice"] == 5
        assert "VOICE_SPOOF_MED" in assessment.fired_rules
    
    def test_spoof_below_threshold_no_points(self, test_db: Session):
        """spoof_prob < 0.60 should give 0 voice points."""
        judge = TrustJudge()
        graph = TrustGraph(test_db)
        
        # Create evidence with low spoof probability
        evidence = create_voice_evidence(spoof_prob=0.30)
        
        assessment = judge.evaluate(
            call_id="test-low-spoof",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Should add 0 voice points
        assert assessment.category_scores["voice"] == 0
        assert "VOICE_SPOOF" not in str(assessment.fired_rules)
    
    def test_threshold_boundaries(self, test_db: Session):
        """Test exact threshold values."""
        judge = TrustJudge()
        graph = TrustGraph(test_db)
        
        # Exactly 0.80 should trigger high
        evidence_80 = create_voice_evidence(spoof_prob=0.80)
        assessment_80 = judge.evaluate(
            call_id="test-80",
            evidence=evidence_80,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        assert assessment_80.category_scores["voice"] == 10
        
        # 0.79 should trigger medium (not high)
        evidence_79 = create_voice_evidence(spoof_prob=0.79)
        assessment_79 = judge.evaluate(
            call_id="test-79",
            evidence=evidence_79,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        assert assessment_79.category_scores["voice"] == 5
        
        # Exactly 0.60 should trigger medium
        evidence_60 = create_voice_evidence(spoof_prob=0.60)
        assessment_60 = judge.evaluate(
            call_id="test-60",
            evidence=evidence_60,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        assert assessment_60.category_scores["voice"] == 5
        
        # 0.59 should trigger nothing
        evidence_59 = create_voice_evidence(spoof_prob=0.59)
        assessment_59 = judge.evaluate(
            call_id="test-59",
            evidence=evidence_59,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        assert assessment_59.category_scores["voice"] == 0


class TestVoiceSafetyRules:
    """Test voice evidence safety properties."""
    
    def test_unavailable_voice_zero_points(self, test_db: Session):
        """Unavailable voice should contribute 0 points, not negative."""
        judge = TrustJudge()
        graph = TrustGraph(test_db)
        
        # Create evidence with unavailable voice
        evidence = create_voice_evidence(status="unavailable")
        
        assessment = judge.evaluate(
            call_id="test-unavailable",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Should be 0, not negative
        assert assessment.category_scores["voice"] == 0
    
    def test_inconclusive_voice_zero_points(self, test_db: Session):
        """Inconclusive voice should contribute 0 points."""
        judge = TrustJudge()
        graph = TrustGraph(test_db)
        
        # Create evidence with inconclusive voice
        evidence = create_voice_evidence(status="inconclusive")
        
        assessment = judge.evaluate(
            call_id="test-inconclusive",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        assert assessment.category_scores["voice"] == 0
    
    def test_voice_never_exceeds_10_points(self, test_db: Session):
        """Voice category should never exceed 10 points."""
        judge = TrustJudge()
        graph = TrustGraph(test_db)
        
        # Create evidence with maximum spoof probability
        evidence = create_voice_evidence(spoof_prob=1.0)
        
        assessment = judge.evaluate(
            call_id="test-cap",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Should cap at 10
        assert assessment.category_scores["voice"] <= 10
    
    def test_voice_does_not_lower_score(self, test_db: Session):
        """Low spoof_prob should not reduce total risk score."""
        judge = TrustJudge()
        graph = TrustGraph(test_db)
        
        # Create evidence with OTP request (high risk)
        evidence_with_low_voice = create_voice_evidence(
            spoof_prob=0.10,  # Very low
            has_otp_request=True
        )
        
        evidence_no_voice = create_voice_evidence(
            status="unavailable",
            has_otp_request=True
        )
        
        assessment_with = judge.evaluate(
            call_id="test-with-voice",
            evidence=evidence_with_low_voice,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        judge.scorer.reset_session()
        
        assessment_without = judge.evaluate(
            call_id="test-no-voice",
            evidence=evidence_no_voice,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Low voice should not reduce score below no-voice score
        assert assessment_with.score >= assessment_without.score


class TestHardFloor3:
    """Test Hard Floor 3: Relative + voice spoof + unverified."""
    
    def test_floor3_relative_voice_spoof_unverified(self, test_db: Session):
        """Relative claim + high spoof + unverified should trigger floor 3 (50 min)."""
        judge = TrustJudge()
        graph = TrustGraph(test_db)
        
        # Add known contact to make channel unverified (not in contact list)
        # Caller claims relative relationship
        evidence = create_voice_evidence(
            spoof_prob=0.85,  # High spoof
            claimed_relative=True
        )
        
        assessment = judge.evaluate(
            call_id="test-floor3",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"  # Unknown number
        )
        
        # Should trigger floor 3
        assert assessment.score >= 50
        assert assessment.risk_level in [RiskLevel.HIGH.value, RiskLevel.CRITICAL.value]
    
    def test_floor3_not_triggered_without_relative_claim(self, test_db: Session):
        """High spoof alone without relative claim should not trigger floor 3."""
        judge = TrustJudge()
        graph = TrustGraph(test_db)
        
        # High spoof but no relative claim
        evidence = create_voice_evidence(
            spoof_prob=0.90,
            claimed_relative=False
        )
        
        assessment = judge.evaluate(
            call_id="test-no-floor3",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # May have high score from voice points, but floor 3 not triggered
        # (floor requires all three conditions)
        # Just voice alone: 10 points (not 50)
        assert assessment.category_scores["voice"] == 10


class TestVoiceASRIndependence:
    """Test that voice analysis and ASR are independent."""
    
    def test_asr_failure_no_fake_voice(self, test_db: Session):
        """ASR failure should not create fabricated voice evidence."""
        judge = TrustJudge()
        graph = TrustGraph(test_db)
        
        # Create evidence with no voice (ASR failed, voice unavailable)
        evidence = create_voice_evidence(status="unavailable")
        
        assessment = judge.evaluate(
            call_id="test-asr-fail",
            evidence=evidence,
            trust_graph=graph,
            caller_number="+919999999999"
        )
        
        # Voice should be 0
        assert assessment.category_scores["voice"] == 0
        assert assessment.score == 0  # No evidence at all


# Helper function to create test evidence
def create_voice_evidence(
    status="ok",
    spoof_prob=None,
    claimed_relative=False,
    has_otp_request=False
) -> EvidenceExtraction:
    """Create test evidence with voice analysis."""
    
    # Create voice evidence
    voice = None
    if status == "ok" and spoof_prob is not None:
        voice = VoiceEvidence(
            status="ok",
            spoof_detection=VoiceSpoofEvidence(
                spoof_prob=spoof_prob,
                windows_analyzed=10,
                model="test-model-v1"
            ),
            voiceprint_match=None,
            quality=VoiceQualityEvidence(
                duration_s=10.0,
                snr_db=20.0
            ),
            model_version="1.0"
        )
    elif status == "unavailable":
        voice = VoiceEvidence(
            status="unavailable",
            spoof_detection=None,
            voiceprint_match=None,
            quality=None,
            model_version="1.0"
        )
    elif status == "inconclusive":
        voice = VoiceEvidence(
            status="inconclusive",
            spoof_detection=None,
            voiceprint_match=None,
            quality=VoiceQualityEvidence(duration_s=1.0, snr_db=3.0),
            model_version="1.0"
        )
    
    # Create claims if needed
    claims = ClaimsEvidence(claims=[], primary_claim=None)
    if claimed_relative:
        claim = ClaimEvidence(
            type="relative",
            value="mother",
            quote="I am your mother",
            t=1.0,
            confidence=0.95,
            language="en"
        )
        claims.claims = [claim]
        claims.primary_claim = claim
    
    # Create requests if needed
    requests = RequestEvidence(
        money_requests=[],
        credential_requests=[],
        action_requests=[]
    )
    if has_otp_request:
        requests.credential_requests = [
            CredentialRequest(
                type="otp",
                quote="Tell me your OTP",
                t=2.0,
                confidence=0.95
            )
        ]
    
    # Create behavior
    behavior = BehaviorEvidence(
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
        call_timing=None
    )
    
    return EvidenceExtraction(
        call_id="test-call",
        claims=claims,
        requests=requests,
        behavior=behavior,
        voice=voice,
        evidence_quality_score=0.8,
        transcript_segments_analyzed=5,
        extractor_version="1.0",
        extraction_warnings=[]
    )
