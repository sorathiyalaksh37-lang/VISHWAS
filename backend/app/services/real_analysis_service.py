"""
Real analysis service — replaces mock_analysis_service for production.

Orchestrates the full Member 2 pipeline:
  1. Load file from storage
  2. Convert to 16 kHz mono WAV (ffmpeg)
  3. Validate audio
  4. Run ASR (faster-whisper) + Voice Layer in parallel
  5. Persist transcript + voice evidence to DB
  6. Update call status

This service is called by the background task in the API routes.
"""
import asyncio
import json
import logging
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.audio.preprocessor import convert_to_wav, validate_audio
from app.audio.asr_service import get_asr_service, ASRResult
from app.audio.voice_layer import get_voice_layer, VoiceEvidence
from app.models.call import CallRecord, AnalysisReport
from app.core.config import settings

logger = logging.getLogger(__name__)

# Thread pool for CPU-bound tasks (ASR, voice) so they don't block the event loop
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="asr-worker")


def _run_asr(wav_path: Path, call_id: str) -> ASRResult:
    """Run ASR synchronously in the thread pool."""
    asr = get_asr_service(model_size=settings.whisper_model_size)
    return asr.transcribe(wav_path, call_id=call_id, vad_filter=True)


def _run_voice(
    wav_path: Path,
    claimed_contact: Optional[str] = None,
    enrolled_embedding=None,
) -> VoiceEvidence:
    """Run voice analysis synchronously in the thread pool."""
    voice = get_voice_layer()
    return voice.analyze(
        wav_path,
        claimed_contact=claimed_contact,
        enrolled_embedding=enrolled_embedding,
    )


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


def _voice_evidence_to_dict(evidence: VoiceEvidence) -> dict:
    """Serialize VoiceEvidence to the voice JSON contract (§4)."""
    result = {
        "status": evidence.status,
        "spoof_prob": evidence.spoof_prob,
        "windows_analyzed": evidence.windows_analyzed,
        "duration_s": evidence.duration_s,
        "snr_db": evidence.snr_db,
        "model": evidence.model,
        "processing_time_s": evidence.processing_time_s,
        "error": evidence.error,
        "speaker_match": None,
    }
    if evidence.speaker_match:
        result["speaker_match"] = {
            "claimed_contact": evidence.speaker_match.claimed_contact,
            "similarity": evidence.speaker_match.similarity,
            "enrolled": evidence.speaker_match.enrolled,
            "threshold": evidence.speaker_match.threshold,
        }
    return result


class RealAnalysisService:
    """
    Production analysis service.
    Uses real faster-whisper ASR and optional voice layer.

    Falls back gracefully if models are unavailable.
    """

    async def analyze_call(
        self,
        db: Session,
        call_id: str,
        claimed_contact: Optional[str] = None,
        enrolled_embedding=None,
    ) -> None:
        """
        Full analysis pipeline for a single call.
        Designed to run as a FastAPI BackgroundTask.

        Steps:
          1. Mark call as 'processing'
          2. Locate stored audio file
          3. Convert to 16 kHz mono WAV
          4. Validate audio quality
          5. ASR + Voice Layer in parallel
          6. Persist results
          7. Mark call as 'completed' or 'failed'
        """
        logger.info(f"[{call_id}] Starting real analysis pipeline")
        loop = asyncio.get_event_loop()
        wav_path: Optional[Path] = None

        # ── Step 1: Mark as processing ────────────────────────────────────────
        call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
        if not call:
            logger.error(f"[{call_id}] CallRecord not found — aborting")
            return

        call.status = "processing"
        db.commit()

        try:
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
            wav_path = await loop.run_in_executor(
                _executor,
                lambda: convert_to_wav(storage_path, wav_path),
            )

            # ── Step 4: Validate ──────────────────────────────────────────────
            is_valid, reason = validate_audio(wav_path)
            if not is_valid:
                raise ValueError(f"Audio validation failed: {reason}")

            # ── Step 5: ASR + Voice in parallel ──────────────────────────────
            logger.info(f"[{call_id}] Launching ASR + Voice Layer in parallel")

            asr_future = loop.run_in_executor(
                _executor,
                lambda: _run_asr(wav_path, call_id),
            )
            voice_future = loop.run_in_executor(
                _executor,
                lambda: _run_voice(wav_path, claimed_contact, enrolled_embedding),
            )

            asr_result, voice_evidence = await asyncio.gather(
                asr_future, voice_future
            )

            logger.info(
                f"[{call_id}] ASR: {asr_result.transcription_status} "
                f"({len(asr_result.segments)} segs) | "
                f"Voice: {voice_evidence.status}"
            )

            # ── Step 6: Persist to DB + Trust Engine Assessment ──────────────
            transcript_dict = _asr_result_to_dict(asr_result, call_id)
            voice_dict = _voice_evidence_to_dict(voice_evidence)

            # === Phase 2: Trust Engine Integration ===
            # Extract evidence and run Trust Judge for deterministic risk assessment
            try:
                from app.trust_engine.trust_graph import TrustGraph
                from app.trust_engine.judge import TrustJudge
                from app.extractors.evidence_pipeline import extract_evidence
                
                logger.info(f"[{call_id}] Running Trust Engine assessment")
                
                # Extract evidence from transcript
                full_text = " ".join(seg.text for seg in asr_result.segments)
                evidence = extract_evidence(
                    call_id=call_id,
                    transcript_text=full_text,
                    transcript_segments=asr_result.segments,
                    voice_evidence=voice_evidence
                )
                
                # Run Trust Judge
                trust_graph = TrustGraph(db)
                judge = TrustJudge()
                assessment = judge.evaluate(
                    call_id=call_id,
                    evidence=evidence,
                    trust_graph=trust_graph,
                    caller_number=claimed_contact  # TODO: Pass actual caller number
                )
                
                # Use Trust Judge assessment
                risk_score = assessment.score
                risk_level = assessment.risk_level
                reasons = assessment.reasons
                
                # Build structured verification object per v3 contract
                verification_obj = None
                if assessment.verification_method and assessment.verification_details:
                    verification_obj = {
                        "action": assessment.verification_method,  # snake_case method
                        "target": None,
                        "safe_word_prompt": False  # Default to False, will implement safe word logic later
                    }
                    
                    # Build target string if contact info available
                    if trust_context.get("contact_found"):
                        contact_name = trust_context.get("contact_name")
                        safe_numbers = trust_context.get("verified_numbers", [])
                        if contact_name and safe_numbers:
                            # Format: "Mom (saved: +91-98xxxx)"
                            masked_number = safe_numbers[0][:7] + "xxxx" if safe_numbers else ""
                            verification_obj["target"] = f"{contact_name} (saved: {masked_number})"
                        elif contact_name:
                            verification_obj["target"] = contact_name
                    
                    # Could check if contact has safe_word_hash set
                    # For now, keep as False until safe word validation is implemented
                
                # Backward compat: keep recommended_actions
                recommended_actions = []
                if assessment.verification_details:
                    recommended_actions.append(assessment.verification_details.get("action", ""))
                    recommended_actions.append(assessment.verification_details.get("recommendation", ""))
                
                warnings = assessment.warnings
                
                logger.info(
                    f"[{call_id}] Trust Judge: {risk_level} "
                    f"(score={risk_score}, channel={assessment.channel_status})"
                )
                
                # === Phase 3: Tier 2 Agentic AI (Optional) ===
                # Run Fraud + Skeptic agents if enabled
                agent_analysis_json = None
                try:
                    from app.agents.orchestrator import AgentOrchestrator
                    from app.core.config import settings
                    
                    if settings.tier2_enabled:
                        logger.info(f"[{call_id}] Running Tier 2 agent analysis")
                        
                        orchestrator = AgentOrchestrator()
                        
                        # Get score breakdown from judge (need to extract it)
                        # For now, create a mock breakdown from assessment data
                        from app.trust_engine.scoring import ScoreBreakdown
                        score_breakdown = ScoreBreakdown(
                            identity=assessment.category_scores.get("identity", 0),
                            request=assessment.category_scores.get("request", 0),
                            behavior=assessment.category_scores.get("behavior", 0),
                            channel=assessment.category_scores.get("channel", 0),
                            voice=assessment.category_scores.get("voice", 0),
                            total=assessment.score,
                            final_score=assessment.score,
                            reasons=assessment.reasons,
                            fired_rules=assessment.fired_rules,
                            applied_floors=assessment.applied_floors
                        )
                        
                        # Run agent orchestration
                        agent_result = await orchestrator.analyze(
                            call_id=call_id,
                            evidence=evidence,
                            trust_context=trust_graph.get_trust_context(claimed_contact, None, None),
                            score_breakdown=score_breakdown,
                            timeout_per_agent=settings.tier2_timeout
                        )
                        
                        # Store agent analysis results
                        agent_analysis_json = json.dumps({
                            "tier2_status": agent_result.tier2_status,
                            "fraud_findings": [f.model_dump() for f in agent_result.fraud_findings],
                            "skeptic_challenges": [c.model_dump() for c in agent_result.skeptic_challenges],
                            "agent_metadata": agent_result.agent_metadata,
                            "warnings": agent_result.warnings
                        }, ensure_ascii=False)
                        
                        logger.info(
                            f"[{call_id}] Tier 2: {agent_result.tier2_status}, "
                            f"{len(agent_result.fraud_findings)} findings, "
                            f"{len(agent_result.skeptic_challenges)} challenges"
                        )
                    
                except Exception as e:
                    logger.warning(
                        f"[{call_id}] Tier 2 agent analysis failed (Phase 2 result preserved): {e}",
                        exc_info=True
                    )
                    # Tier 2 failure does not affect Phase 2 results
                
            except Exception as e:
                logger.warning(
                    f"[{call_id}] Trust Engine assessment failed, falling back to preliminary: {e}",
                    exc_info=True
                )
                # Fallback to basic reasons if Trust Engine fails
                reasons, warnings = self._generate_basic_reasons(
                    asr_result, voice_evidence
                )
                risk_score, risk_level = self._preliminary_risk(voice_evidence)
                recommended_actions = ["Await full analysis from Judge module"]

            # Store or update AnalysisReport
            report = (
                db.query(AnalysisReport)
                .filter(AnalysisReport.call_id == call_id)
                .first()
            )
            if report is None:
                report = AnalysisReport(call_id=call_id)
                db.add(report)

            report.transcript_json = json.dumps(transcript_dict, ensure_ascii=False)
            report.voice_json = json.dumps(voice_dict, ensure_ascii=False)
            report.agent_findings_json = agent_analysis_json if agent_analysis_json else json.dumps([], ensure_ascii=False)
            report.risk_level = risk_level
            report.risk_score = risk_score
            report.reasons_json = json.dumps(reasons, ensure_ascii=False)
            report.recommended_actions_json = json.dumps(
                recommended_actions, ensure_ascii=False
            )
            report.warnings_json = json.dumps(warnings, ensure_ascii=False)
            report.analysis_mode = "real"
            
            # Phase 5: Persist v3 Trust Engine fields
            if 'assessment' in locals() and assessment:
                report.category_scores_json = json.dumps(assessment.category_scores, ensure_ascii=False)
                report.fired_rules_json = json.dumps(assessment.fired_rules, ensure_ascii=False)
                report.killchain_stage = assessment.killchain_stage  # Task 2: Persist killchain stage
                if 'verification_obj' in locals() and verification_obj:
                    report.verification_json = json.dumps(verification_obj, ensure_ascii=False)

            # ── Step 7: Mark completed ────────────────────────────────────────
            call.status = "completed"
            call.completed_at = datetime.now(timezone.utc)
            db.commit()

            logger.info(f"[{call_id}] Analysis complete ✓")

        except Exception as e:
            logger.error(
                f"[{call_id}] Analysis pipeline failed: {e}", exc_info=True
            )
            call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
            if call:
                call.status = "failed"
                call.error_message = str(e)[:500]
                db.commit()

        finally:
            # Clean up temp WAV
            if wav_path and wav_path.exists():
                try:
                    wav_path.unlink()
                except Exception:
                    pass

    @staticmethod
    def _generate_basic_reasons(
        asr: ASRResult, voice: VoiceEvidence
    ) -> tuple[list[str], list[str]]:
        """
        Generate human-readable preliminary reasons from ASR + voice results.
        The full evidence extraction is done by M3 (evidence layer).
        """
        reasons: list[str] = []
        warnings: list[str] = []

        if asr.transcription_status == "failed":
            warnings.append("ASR transcription failed — transcript unavailable.")
        elif asr.transcription_status == "unavailable":
            warnings.append(
                "faster-whisper not installed — transcript unavailable. "
                "Install with: pip install faster-whisper"
            )

        if voice.status == "unavailable":
            warnings.append(
                "Voice layer unavailable — install torch, transformers, "
                "speechbrain for voice-clone detection."
            )
        elif voice.status == "inconclusive":
            warnings.append(
                f"Voice analysis inconclusive: {voice.error or 'insufficient audio quality'}."
            )
        elif voice.status == "ok" and voice.spoof_prob is not None:
            if voice.spoof_prob >= 0.80:
                reasons.append(
                    f"Voice shows strong synthetic indicators "
                    f"(spoof_prob={voice.spoof_prob:.2f}) [experimental]."
                )
            elif voice.spoof_prob >= 0.60:
                reasons.append(
                    f"Voice shows moderate synthetic indicators "
                    f"(spoof_prob={voice.spoof_prob:.2f}) [experimental]."
                )

        return reasons, warnings

    @staticmethod
    def _preliminary_risk(voice: VoiceEvidence) -> tuple[float, str]:
        """
        Compute preliminary risk from voice alone.
        Full deterministic scoring is M3's responsibility.
        """
        score = 0.0
        if voice.status == "ok" and voice.spoof_prob is not None:
            if voice.spoof_prob >= 0.80:
                score = 10.0
            elif voice.spoof_prob >= 0.60:
                score = 5.0

        if score >= 75:
            level = "critical"
        elif score >= 50:
            level = "high"
        elif score >= 25:
            level = "medium"
        else:
            level = "low"

        return score, level


# ── Singleton ─────────────────────────────────────────────────────────────────
real_analysis_service = RealAnalysisService()
