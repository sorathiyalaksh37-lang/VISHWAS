"""
Real analysis service — replaces mock_analysis_service for production.

Orchestrates the full analysis pipeline:
  1. Load file from storage
  2. Convert to 16 kHz mono WAV (ffmpeg or PyAV)
  3. Validate audio
  4. Run ASR (faster-whisper)
  5. Run evidence extraction + Trust Engine assessment
  6. Persist transcript + findings to DB
  7. Update call status

This service is called by BackgroundTasks in the API routes.
The analyze_call method signature matches MockAnalysisService for interchangeability.
"""
import json
import logging
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.audio.preprocessor import convert_to_wav, validate_audio
from app.audio.asr_service import get_asr_service, ASRResult
from app.models.call import CallRecord, AnalysisReport
from app.core.config import settings

logger = logging.getLogger(__name__)


def _run_asr(wav_path: Path, call_id: str) -> ASRResult:
    """Run ASR synchronously."""
    asr = get_asr_service(model_size=settings.whisper_model_size)
    return asr.transcribe(wav_path, call_id=call_id, vad_filter=True)


def _asr_result_to_dict(result: ASRResult, call_id: str) -> dict:
    """Serialize ASRResult to the transcript JSON schema."""
    return {
        "call_id": call_id,
        "language": result.language,
        "language_probability": result.language_probability,
        "transcription_status": result.transcription_status,
        "duration_seconds": result.duration_seconds,
        "processing_time_seconds": result.processing_time_seconds,
        "model_name": result.model_name,
        "is_mock": result.is_mock,
        "segments": [
            {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
                "language": seg.language,
                "speaker": seg.speaker,
                "confidence": seg.confidence,
            }
            for seg in result.segments
        ],
        "error": result.error,
    }


class RealAnalysisService:
    """
    Production analysis service.
    Uses real faster-whisper ASR and evidence extraction pipeline.

    Falls back gracefully if models are unavailable.
    """

    def __init__(self):
        """Initialize real analysis service."""
        self.analysis_mode = "real"

    def analyze_call(self, call_id: str) -> None:
        """
        Full analysis pipeline for a single call.
        Designed to run as a FastAPI BackgroundTask.

        Signature matches MockAnalysisService.analyze_call() so they
        are interchangeable via _analysis_service() in the routes.

        Steps:
          1. Mark call as 'processing'
          2. Locate stored audio file
          3. Convert to 16 kHz mono WAV
          4. Validate audio quality
          5. Run ASR transcription
          6. Extract evidence + run Trust Engine
          7. Persist results
          8. Mark call as 'completed' or 'failed'
        """
        # Create a new database session for the background task
        from app.database.session import SessionLocal
        db = SessionLocal()
        wav_path: Optional[Path] = None

        try:
            logger.info(f"[{call_id}] Starting real analysis pipeline")

            # ── Step 1: Mark as processing ────────────────────────────────────
            call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
            if not call:
                logger.error(f"[{call_id}] CallRecord not found — aborting")
                return

            call.status = "processing"
            call.analysis_mode = self.analysis_mode
            db.commit()

            # ── Step 2: Locate stored file ────────────────────────────────────
            storage_path = Path(call.storage_reference)
            if not storage_path.exists():
                raise FileNotFoundError(
                    f"Audio file not found at {storage_path}"
                )

            # ── Step 3: Convert to 16 kHz mono WAV ───────────────────────────
            tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_wav.close()
            wav_path = Path(tmp_wav.name)

            logger.info(f"[{call_id}] Converting audio: {storage_path} → {wav_path}")
            wav_path = convert_to_wav(storage_path, wav_path)

            # ── Step 4: Validate ──────────────────────────────────────────────
            is_valid, reason = validate_audio(wav_path)
            if not is_valid:
                raise ValueError(f"Audio validation failed: {reason}")

            # ── Step 5: Run ASR transcription ─────────────────────────────────
            logger.info(f"[{call_id}] Running ASR transcription...")
            asr_result = _run_asr(wav_path, call_id)

            logger.info(
                f"[{call_id}] ASR: {asr_result.transcription_status} "
                f"({len(asr_result.segments)} segments)"
            )

            # ── Step 6: Evidence extraction + Risk assessment ─────────────────
            transcript_dict = _asr_result_to_dict(asr_result, call_id)
            full_text = " ".join(seg.text for seg in asr_result.segments)

            risk_score = 0
            risk_level = "low"
            reasons = []
            recommended_actions = []
            warnings = []
            agent_findings = []
            category_scores_dict = None
            fired_rules_list = []
            verification_dict = None
            killchain_stage = None
            voice_dict = None

            # ── Step 6a: Voice layer (anti-spoof) ────────────────────────────
            try:
                if settings.enable_voice_layer:
                    from app.audio.voice_layer import get_voice_layer
                    from dataclasses import asdict
                    voice_layer = get_voice_layer()
                    voice_result = voice_layer.analyze(wav_path)

                    if voice_result:
                        # Convert dataclass to dict
                        voice_dict = asdict(voice_result)
                        logger.info(
                            f"[{call_id}] Voice layer: status={voice_result.status}, "
                            f"spoof_prob={voice_result.spoof_prob}"
                        )
                    else:
                        voice_dict = {"status": "unavailable"}
                        warnings.append("Voice layer returned no result")
                else:
                    voice_dict = {"status": "unavailable"}
            except Exception as ve:
                logger.warning(
                    f"[{call_id}] Voice layer failed (continuing safely): {ve}",
                    exc_info=True,
                )
                voice_dict = {"status": "unavailable"}
                warnings.append(f"Voice analysis unavailable: {str(ve)[:100]}")

            # ── Step 6b: Trust Engine assessment ─────────────────────────────
            try:
                from app.trust_engine.trust_graph import TrustGraph
                from app.trust_engine.judge import TrustJudge
                from app.extractors.evidence_pipeline import extract_evidence_from_transcript
                from app.schemas.report import TranscriptResponse, TranscriptSegment as SchemaSegment

                logger.info(f"[{call_id}] Running Trust Engine assessment")

                # Build TranscriptResponse from ASR result for the evidence pipeline
                schema_segments = [
                    SchemaSegment(
                        start=seg.start,
                        end=seg.end,
                        text=seg.text,
                        language=seg.language,
                        speaker=seg.speaker,
                    )
                    for seg in asr_result.segments
                ]
                transcript_response = TranscriptResponse(
                    call_id=call_id,
                    language=asr_result.language,
                    transcription_status=asr_result.transcription_status,
                    segments=schema_segments,
                    is_mock=False,
                )

                # Extract evidence using the proper pipeline
                evidence = extract_evidence_from_transcript(
                    transcript=transcript_response,
                    call_id=call_id,
                )

                trust_graph = TrustGraph(db)
                judge = TrustJudge()
                assessment = judge.evaluate(
                    call_id=call_id,
                    evidence=evidence,
                    trust_graph=trust_graph,
                    caller_number=None
                )

                risk_score = assessment.score
                risk_level = assessment.risk_level
                reasons = assessment.reasons
                warnings.extend(assessment.warnings)
                fired_rules_list = assessment.fired_rules
                killchain_stage = assessment.killchain_stage

                # Category scores
                category_scores_dict = assessment.category_scores

                # Verification
                if assessment.verification_details:
                    verification_dict = {
                        "action": assessment.verification_details.get("action"),
                        "target": assessment.verification_details.get("recommendation"),
                        "safe_word_prompt": None,
                    }
                    action = assessment.verification_details.get("action", "")
                    rec = assessment.verification_details.get("recommendation", "")
                    if action:
                        recommended_actions.append(action)
                    if rec:
                        recommended_actions.append(rec)

                # Convert evidence to agent_findings for the report
                if hasattr(evidence, 'claims') and evidence.claims:
                    for claim in evidence.claims.claims:
                        agent_findings.append({
                            "agent": "tier1_classifier",
                            "signal": f"identity_claim_{claim.claim_type}" if hasattr(claim, 'claim_type') else "identity_claim",
                            "severity": "medium",
                            "evidence_text": getattr(claim, 'quote', str(claim)),
                            "source": "real"
                        })
                if hasattr(evidence, 'requests') and evidence.requests:
                    for req in evidence.requests.credential_requests:
                        agent_findings.append({
                            "agent": "tier1_classifier",
                            "signal": "sensitive_credential_request",
                            "severity": "critical",
                            "evidence_text": getattr(req, 'quote', str(req)),
                            "source": "real"
                        })
                    for req in evidence.requests.money_requests:
                        agent_findings.append({
                            "agent": "tier1_classifier",
                            "signal": "financial_request",
                            "severity": "critical",
                            "evidence_text": getattr(req, 'quote', str(req)),
                            "source": "real"
                        })
                if hasattr(evidence, 'behavior') and evidence.behavior:
                    if evidence.behavior.urgency and evidence.behavior.urgency.detected:
                        agent_findings.append({
                            "agent": "tier1_classifier",
                            "signal": "urgency_tactic",
                            "severity": "high",
                            "evidence_text": evidence.behavior.urgency.quote or "Urgency detected",
                            "source": "real"
                        })

                logger.info(
                    f"[{call_id}] Trust Judge: {risk_level} (score={risk_score})"
                )

            except Exception as e:
                logger.warning(
                    f"[{call_id}] Trust Engine assessment failed, using text-based fallback: {e}",
                    exc_info=True
                )
                # Fallback: basic text analysis
                risk_score, risk_level, reasons, agent_findings = (
                    self._basic_text_analysis(full_text, asr_result)
                )
                warnings.append(
                    f"Trust Engine unavailable — using simplified text analysis. ({str(e)[:100]})"
                )
                recommended_actions.append(
                    "Verify caller identity through independent channels"
                )

            # Add ASR warnings
            if asr_result.transcription_status == "failed":
                warnings.append("ASR transcription failed — transcript unavailable.")
                # Treat failed ASR as uncertainty, not evidence of innocence
                if risk_score < 25:
                    risk_score = 25
                    risk_level = "medium"
                    warnings.append("Risk elevated to MEDIUM due to ASR failure — cannot assess transcript content.")
            elif asr_result.transcription_status == "unavailable":
                warnings.append(
                    "faster-whisper not installed — transcript unavailable. "
                    "Install with: pip install faster-whisper"
                )
                if risk_score < 25:
                    risk_score = 25
                    risk_level = "medium"
                    warnings.append("Risk elevated to MEDIUM — ASR unavailable, transcript content unknown.")
            
            if not recommended_actions:
                recommended_actions = self._get_default_actions(risk_level)

            # ── Step 7: Persist to DB ─────────────────────────────────────────
            report = (
                db.query(AnalysisReport)
                .filter(AnalysisReport.call_id == call_id)
                .first()
            )
            if report is None:
                report = AnalysisReport(call_id=call_id)
                db.add(report)

            report.transcript_json = json.dumps(transcript_dict, ensure_ascii=False)
            report.agent_findings_json = json.dumps(agent_findings, ensure_ascii=False)
            report.risk_level = risk_level
            report.risk_score = risk_score
            report.reasons_json = json.dumps(reasons, ensure_ascii=False)
            report.recommended_actions_json = json.dumps(
                recommended_actions, ensure_ascii=False
            )
            report.warnings_json = json.dumps(warnings, ensure_ascii=False)
            report.analysis_mode = self.analysis_mode

            # v3 Trust Engine fields
            if category_scores_dict:
                report.category_scores_json = json.dumps(category_scores_dict, ensure_ascii=False)
            if fired_rules_list:
                report.fired_rules_json = json.dumps(fired_rules_list, ensure_ascii=False)
            if verification_dict:
                report.verification_json = json.dumps(verification_dict, ensure_ascii=False)
            report.killchain_stage = killchain_stage
            if voice_dict:
                report.voice_json = json.dumps(voice_dict, ensure_ascii=False)

            # ── Step 8: Mark completed ────────────────────────────────────────
            call.status = "completed"
            call.completed_at = datetime.now(timezone.utc)
            db.commit()

            logger.info(f"[{call_id}] Real analysis complete ✓")

        except Exception as e:
            logger.error(
                f"[{call_id}] Analysis pipeline failed: {e}", exc_info=True
            )
            try:
                call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
                if call:
                    call.status = "failed"
                    call.error_message = str(e)[:500]
                    call.completed_at = datetime.now(timezone.utc)
                    db.commit()
            except Exception as commit_error:
                logger.error(f"Failed to update error status: {commit_error}")
                db.rollback()

        finally:
            # Clean up temp WAV
            if wav_path and wav_path.exists():
                try:
                    wav_path.unlink()
                except Exception:
                    pass
            # Always close the database session
            db.close()

    @staticmethod
    def _basic_text_analysis(
        full_text: str, asr_result: ASRResult
    ) -> tuple[int, str, list[str], list[dict]]:
        """
        Fallback text-based analysis when Trust Engine is unavailable.
        Scans transcript for common fraud indicators.
        """
        text_lower = full_text.lower()
        reasons = []
        findings = []
        score = 0

        # Credential requests
        cred_patterns = [
            ("otp", "OTP/one-time password request"),
            ("password", "Password request"),
            ("pin number", "PIN number request"),
            ("card number", "Card number request"),
            ("cvv", "CVV/security code request"),
            ("account number", "Account number request"),
            ("social security", "Social security number request"),
            ("bank details", "Bank details request"),
        ]
        for pattern, label in cred_patterns:
            if pattern in text_lower:
                score += 25
                reasons.append(f"Sensitive credential request detected: {label}")
                findings.append({
                    "agent": "text_analyzer",
                    "signal": "sensitive_credential_request",
                    "severity": "critical",
                    "evidence_text": label,
                    "start_time": None,
                    "end_time": None,
                    "confidence": None,
                    "source": "real_text_analysis"
                })

        # Urgency tactics
        urgency_patterns = [
            ("immediately", "Urgency: 'immediately'"),
            ("urgent", "Urgency tactic"),
            ("right now", "Urgency: 'right now'"),
            ("limited time", "Limited time pressure"),
            ("will be blocked", "Account blocking threat"),
            ("will be suspended", "Account suspension threat"),
            ("will be closed", "Account closure threat"),
            ("act fast", "Urgency: 'act fast'"),
            ("hurry", "Urgency: 'hurry'"),
        ]
        for pattern, label in urgency_patterns:
            if pattern in text_lower:
                score += 15
                reasons.append(f"Urgency/pressure tactic: {label}")
                findings.append({
                    "agent": "text_analyzer",
                    "signal": "urgency_tactic",
                    "severity": "high",
                    "evidence_text": label,
                    "start_time": None,
                    "end_time": None,
                    "confidence": None,
                    "source": "real_text_analysis"
                })

        # Authority impersonation
        authority_patterns = [
            ("bank security", "Bank security department claim"),
            ("fraud department", "Fraud department claim"),
            ("government", "Government authority claim"),
            ("police", "Law enforcement claim"),
            ("income tax", "Tax authority claim"),
            ("reserve bank", "Central bank claim"),
            ("rbi", "RBI claim"),
        ]
        for pattern, label in authority_patterns:
            if pattern in text_lower:
                score += 20
                reasons.append(f"Authority impersonation: {label}")
                findings.append({
                    "agent": "text_analyzer",
                    "signal": "authority_impersonation",
                    "severity": "high",
                    "evidence_text": label,
                    "start_time": None,
                    "end_time": None,
                    "confidence": None,
                    "source": "real_text_analysis"
                })

        # Money transfer requests
        money_patterns = [
            ("transfer money", "Money transfer request"),
            ("send money", "Money sending request"),
            ("wire transfer", "Wire transfer request"),
            ("gift card", "Gift card purchase request"),
            ("crypto", "Cryptocurrency payment request"),
            ("bitcoin", "Bitcoin payment request"),
            ("upi", "UPI transfer request"),
            ("google pay", "Payment app request"),
            ("paytm", "Payment app request"),
        ]
        for pattern, label in money_patterns:
            if pattern in text_lower:
                score += 25
                reasons.append(f"Financial request: {label}")
                findings.append({
                    "agent": "text_analyzer",
                    "signal": "financial_request",
                    "severity": "critical",
                    "evidence_text": label,
                    "start_time": None,
                    "end_time": None,
                    "confidence": None,
                    "source": "real_text_analysis"
                })

        # Cap score at 100
        score = min(score, 100)

        # Determine risk level
        if score >= 75:
            level = "critical"
        elif score >= 50:
            level = "high"
        elif score >= 25:
            level = "medium"
        else:
            level = "low"

        if not reasons:
            reasons.append("No suspicious patterns detected in transcript")

        return score, level, reasons, findings

    @staticmethod
    def _get_default_actions(risk_level: str) -> list[str]:
        """Return default recommended actions based on risk level."""
        if risk_level in ("high", "critical"):
            return [
                "Do NOT share any sensitive information with this caller",
                "Hang up and call back using an official number you trust",
                "Report this call to your bank or the relevant authority",
                "Block this number if you suspect fraud",
            ]
        elif risk_level == "medium":
            return [
                "Verify the caller's identity through independent channels",
                "Do not share OTPs, passwords, or financial details",
                "Call back using an official number to confirm",
            ]
        else:
            return [
                "Always verify caller identity for financial matters",
                "Never share OTPs or passwords over the phone",
            ]


# ── Singleton ─────────────────────────────────────────────────────────────────
real_analysis_service = RealAnalysisService()
