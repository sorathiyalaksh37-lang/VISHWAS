"""
LiveSessionManager — Manages real-time audio and non-audio fraud detection sessions.
Handles WebSocket transport, session ownership, sequence validation, bounded queues,
backpressure, rolling-window processing, parameter scoring, and database persistence.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import struct
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

from app.audio.aasist_streaming import AASISTStreamingAnalyzer, MIN_AUDIO_DURATION_S
from app.audio.incremental_asr import IncrementalASR, PartialTranscript
from app.core.config import settings
from app.extractors.evidence_pipeline import extract_evidence_from_transcript
from app.extractors.parameter_extractor import build_call_parameters
from app.schemas.evidence import VoiceEvidence
from app.schemas.live_session import (
    LiveSessionStartRequest,
    LiveSessionStateResponse,
    SessionMode,
    SessionState,
)
from app.schemas.parameters import CallParameters
from app.schemas.report import (
    CategoryScores,
    TranscriptResponse,
    TranscriptSegment,
    Verification,
)
from app.trust_engine.parameter_scorer import score_from_parameters
from app.trust_engine.scoring import RiskLevel, ScoreBreakdown

logger = logging.getLogger(__name__)

# Bounded configuration
MAX_CONCURRENT_SESSIONS = 100
MAX_QUEUE_SIZE_PER_SESSION = 500  # Max chunks queued (~10s at 50 chunks/sec)
MAX_PAYLOAD_SIZE = 65536         # 64 KB per chunk max
CHUNK_TIMEOUT_SECONDS = 30.0


@dataclass
class AudioChunkData:
    sequence_number: int
    timestamp_ms: int
    sample_rate: int
    channel_count: int
    audio_data: bytes
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class LiveSession:
    session_id: str
    user_id: str
    mode: SessionMode
    audio_authorized: bool
    state: SessionState = "active"
    caller_number: Optional[str] = None
    claimed_identity: Optional[str] = None
    claimed_relationship: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Bounded audio queue
    audio_queue: asyncio.Queue[AudioChunkData] = field(
        default_factory=lambda: asyncio.Queue(maxsize=MAX_QUEUE_SIZE_PER_SESSION)
    )

    # Sequence tracking
    last_sequence: Optional[int] = None
    total_chunks_received: int = 0
    total_chunks_processed: int = 0
    dropped_chunks: int = 0

    # Processing and data
    accumulated_pcm: bytearray = field(default_factory=bytearray)
    transcript_segments: List[TranscriptSegment] = field(default_factory=list)
    call_parameters: Optional[CallParameters] = None
    score_breakdown: Optional[ScoreBreakdown] = None
    current_score: int = 0
    current_level: str = "LOW"
    fired_rules: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)

    # Voice analysis status
    voice_status: str = "unavailable"
    voice_spoof_prob: Optional[float] = None
    windows_analyzed: int = 0
    asr: Any = None
    aasist_analyzer: Any = None

    # Connection and tasks
    websockets: Set[WebSocket] = field(default_factory=set)
    processing_task: Optional[asyncio.Task] = None
    persisted_call_id: Optional[str] = None


class LiveSessionManager:
    """Manages all active real-time analysis sessions with concurrency and ownership bounds."""

    def __init__(self):
        self.sessions: Dict[str, LiveSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        user_id: str,
        request: LiveSessionStartRequest,
    ) -> LiveSession:
        """Create a new live analysis session with user ownership."""
        async with self._lock:
            if len(self.sessions) >= MAX_CONCURRENT_SESSIONS:
                raise ValueError(
                    f"Maximum concurrent sessions ({MAX_CONCURRENT_SESSIONS}) reached."
                )

            session_id = str(uuid.uuid4())
            voice_status = "unavailable"
            if request.mode in ("webrtc", "cellular"):
                voice_status = "pending" if request.audio_authorized else "not_authorized"
            else:
                voice_status = "unavailable"

            session = LiveSession(
                session_id=session_id,
                user_id=user_id,
                mode=request.mode,
                audio_authorized=request.audio_authorized,
                caller_number=request.caller_number,
                claimed_identity=request.claimed_identity,
                claimed_relationship=request.claimed_relationship,
                voice_status=voice_status,
            )

            if not request.audio_authorized and request.mode in ("webrtc", "cellular"):
                session.warnings.append(
                    "Caller audio consent not authorized — voice cloning analysis disabled. Running permitted non-audio detection."
                )

            self.sessions[session_id] = session
            logger.info(
                f"[LiveSession {session_id}] Created mode={request.mode} user={user_id} audio_authorized={request.audio_authorized}"
            )
            return session

    def get_session(self, session_id: str, user_id: Optional[str] = None) -> Optional[LiveSession]:
        """Retrieve session by ID, validating ownership if user_id is provided."""
        session = self.sessions.get(session_id)
        if not session:
            return None
        if user_id is not None and session.user_id != user_id:
            logger.warning(
                f"[LiveSession {session_id}] Unauthorized access attempt by user {user_id} (owner={session.user_id})"
            )
            return None
        return session

    async def register_websocket(self, session_id: str, websocket: WebSocket, user_id: str) -> LiveSession:
        """Attach a WebSocket connection to an active session after ownership validation."""
        session = self.get_session(session_id, user_id)
        if not session:
            raise ValueError("Session not found or unauthorized")

        session.websockets.add(websocket)

        # Start audio background processor if not already running
        if session.processing_task is None or session.processing_task.done():
            session.processing_task = asyncio.create_task(self._audio_processing_loop(session))

        logger.info(f"[LiveSession {session_id}] WebSocket attached. Total listeners: {len(session.websockets)}")
        return session

    def unregister_websocket(self, session_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from a session."""
        session = self.sessions.get(session_id)
        if session:
            session.websockets.discard(websocket)
            logger.info(f"[LiveSession {session_id}] WebSocket detached. Remaining: {len(session.websockets)}")

    async def broadcast_event(self, session: LiveSession, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcast an event to all connected WebSocket clients for this session."""
        payload = {
            "type": event_type,
            "session_id": session.session_id,
            "timestamp_ms": round(datetime.now(timezone.utc).timestamp() * 1000, 1),
            "data": data,
        }
        dead_sockets: List[WebSocket] = []
        for ws in list(session.websockets):
            try:
                await ws.send_json(payload)
            except Exception as e:
                logger.debug(f"[LiveSession {session.session_id}] Error broadcasting to client: {e}")
                dead_sockets.append(ws)

        for ws in dead_sockets:
            session.websockets.discard(ws)

    # ── Audio Submission & Processing ─────────────────────────────────────────

    async def submit_audio_chunk(
        self,
        session_id: str,
        user_id: str,
        sequence_number: int,
        timestamp_ms: int,
        sample_rate: int,
        channel_count: int,
        audio_data: bytes,
    ) -> bool:
        """Submit an incoming audio chunk with sequence validation and backpressure."""
        session = self.get_session(session_id, user_id)
        if not session:
            raise ValueError("Session not found or unauthorized")

        if session.state != "active":
            logger.warning(f"[LiveSession {session_id}] Chunk received in inactive state: {session.state}")
            return False

        if not session.audio_authorized:
            await self.broadcast_event(
                session, "warning",
                {"message": "Audio chunk dropped: Caller audio consent is not authorized for this session."}
            )
            return False

        if len(audio_data) > MAX_PAYLOAD_SIZE:
            logger.warning(f"[LiveSession {session_id}] Oversized chunk dropped: {len(audio_data)} bytes")
            return False

        # Sequence validation: reject duplicate/older sequence numbers
        if session.last_sequence is not None:
            if sequence_number <= session.last_sequence:
                logger.debug(f"[LiveSession {session_id}] Dropping duplicate/out-of-order chunk #{sequence_number}")
                return False
            if sequence_number > session.last_sequence + 1:
                gap = sequence_number - (session.last_sequence + 1)
                session.dropped_chunks += gap
                logger.warning(f"[LiveSession {session_id}] Missing {gap} chunk(s) before #{sequence_number}")

        chunk = AudioChunkData(
            sequence_number=sequence_number,
            timestamp_ms=timestamp_ms,
            sample_rate=sample_rate,
            channel_count=channel_count,
            audio_data=audio_data,
        )

        try:
            session.audio_queue.put_nowait(chunk)
            session.last_sequence = sequence_number
            session.total_chunks_received += 1
            return True
        except asyncio.QueueFull:
            session.dropped_chunks += 1
            logger.warning(f"[LiveSession {session_id}] Audio queue full. Applying backpressure (drop chunk #{sequence_number})")
            await self.broadcast_event(
                session, "warning",
                {"message": "Audio processing backpressure detected. Slowing stream."}
            )
            return False

    async def _audio_processing_loop(self, session: LiveSession) -> None:
        """Background loop reading audio chunks from queue and updating ASR/Trust Judge."""
        logger.info(f"[LiveSession {session.session_id}] Audio processing loop started")
        sample_rate = 16000

        if session.asr is None:
            session.asr = IncrementalASR(sample_rate=sample_rate)
        if session.aasist_analyzer is None:
            session.aasist_analyzer = AASISTStreamingAnalyzer()

        try:
            while session.state == "active":
                try:
                    chunk = await asyncio.wait_for(session.audio_queue.get(), timeout=1.0)
                    sample_rate = chunk.sample_rate or 16000
                    session.accumulated_pcm.extend(chunk.audio_data)
                    session.total_chunks_processed += 1

                    # 1. Feed into incremental ASR
                    session.asr.add_audio(chunk.audio_data, timestamp_ms=chunk.timestamp_ms)

                    # 2. Check for incremental ASR segments
                    if session.asr.has_sufficient_audio():
                        new_transcripts = session.asr.transcribe_current_window()
                        for pt in new_transcripts:
                            if pt.is_final:
                                seg = TranscriptSegment(
                                    start=pt.start_time,
                                    end=pt.end_time,
                                    speaker=pt.speaker,
                                    text=pt.text,
                                    is_final=True,
                                )
                                session.transcript_segments.append(seg)
                                await self.broadcast_event(
                                    session,
                                    "transcript_final",
                                    {
                                        "segment": {
                                            "start": seg.start,
                                            "end": seg.end,
                                            "text": seg.text,
                                            "speaker": seg.speaker,
                                            "is_final": True,
                                        }
                                    },
                                )
                                # Recompute scoring upon finalized segment
                                await self._recompute_scoring(session, voice_ev=None)
                            else:
                                await self.broadcast_event(
                                    session,
                                    "transcript_partial",
                                    {
                                        "segment": {
                                            "start": pt.start_time,
                                            "end": pt.end_time,
                                            "text": pt.text,
                                            "speaker": pt.speaker,
                                            "is_final": False,
                                        }
                                    },
                                )

                    # 3. Voice anti-spoof check (Phase 4): analyze when accumulated PCM >= 3.0s
                    min_bytes_for_voice = int(sample_rate * 2 * MIN_AUDIO_DURATION_S)
                    if session.audio_authorized and len(session.accumulated_pcm) >= min_bytes_for_voice:
                        voice_window = bytes(session.accumulated_pcm[:min_bytes_for_voice])
                        # Keep 1.0s overlap
                        overlap_bytes = int(sample_rate * 2 * 1.0)
                        session.accumulated_pcm = session.accumulated_pcm[min_bytes_for_voice - overlap_bytes:]

                        voice_result = await session.aasist_analyzer.analyze_pcm_window(
                            voice_window, sample_rate, audio_authorized=True
                        )

                        if voice_result.get("status") == "ok":
                            session.windows_analyzed = voice_result.get("windows_analyzed", session.windows_analyzed + 1)
                            session.voice_status = "analyzed"
                            session.voice_spoof_prob = voice_result.get("spoof_prob", 0.05)

                            voice_ev = VoiceEvidence(
                                status="ok",
                                spoof_prob=session.voice_spoof_prob,
                                windows_analyzed=session.windows_analyzed,
                                duration_s=voice_result.get("duration_s", 3.0),
                            )

                            await self.broadcast_event(
                                session,
                                "voice_update",
                                {
                                    "status": "analyzed",
                                    "spoof_prob": session.voice_spoof_prob,
                                    "windows_analyzed": session.windows_analyzed,
                                    "duration_s": voice_result.get("duration_s", 3.0),
                                    "model": voice_result.get("model", "AASIST-L"),
                                },
                            )

                            # Recompute scoring with updated voice evidence
                            await self._recompute_scoring(session, voice_ev)

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"[LiveSession {session.session_id}] Error in processing loop: {e}", exc_info=True)

        finally:
            # Finalize any pending provisional transcript
            if session.asr is not None:
                finalized = session.asr.finalize_remaining()
                for pt in finalized:
                    seg = TranscriptSegment(
                        start=pt.start_time,
                        end=pt.end_time,
                        speaker=pt.speaker,
                        text=pt.text,
                        is_final=True,
                    )
                    session.transcript_segments.append(seg)
                    await self.broadcast_event(
                        session,
                        "transcript_final",
                        {
                            "segment": {
                                "start": seg.start,
                                "end": seg.end,
                                "text": seg.text,
                                "speaker": seg.speaker,
                                "is_final": True,
                            }
                        },
                    )
            logger.info(f"[LiveSession {session.session_id}] Audio processing loop exited")

    # ── Non-Audio Submission (Phase 3) ────────────────────────────────────────

    async def submit_non_audio_message(
        self,
        session_id: str,
        user_id: str,
        text: str,
        speaker: str = "caller",
        timestamp_s: Optional[float] = None,
    ) -> LiveSessionStateResponse:
        """
        Phase 3: Accept suspicious messages or requests reported by the user during call.
        Extracts structured parameters and immediately updates deterministic Trust Judge.
        """
        session = self.get_session(session_id, user_id)
        if not session:
            raise ValueError("Session not found or unauthorized")

        t = timestamp_s if timestamp_s is not None else float(len(session.transcript_segments) * 2)

        segment = TranscriptSegment(
            start=round(t, 2),
            end=round(t + 2.0, 2),
            speaker=speaker,
            text=text.strip(),
            is_final=True,
        )
        session.transcript_segments.append(segment)

        # Recompute score with deterministic Trust Judge
        await self._recompute_scoring(session, voice_ev=None)

        # Broadcast events
        await self.broadcast_event(
            session, "transcript_final",
            {
                "segment": {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "speaker": segment.speaker,
                    "is_final": True,
                }
            }
        )

        return self.get_state_response(session)

    # ── Deterministic Scoring Engine Integration ──────────────────────────────

    async def _recompute_scoring(self, session: LiveSession, voice_ev: Optional[VoiceEvidence] = None) -> None:
        """Run canonical parameter extraction and deterministic parameter scoring."""
        transcript_response = TranscriptResponse(
            call_id=session.session_id,
            language="en",
            transcription_status="streaming",
            segments=session.transcript_segments,
            is_mock=(settings.analysis_mode == "mock"),
        )

        # Tier1 evidence extraction
        evidence = extract_evidence_from_transcript(transcript_response, session.session_id)

        # Canonical CallParameters
        channel_status = "UNKNOWN"
        if session.caller_number:
            channel_status = "UNKNOWN"  # Unverified number by default

        call_params = build_call_parameters(
            transcript=transcript_response,
            call_id=session.session_id,
            evidence=evidence,
            voice_evidence=voice_ev,
            caller_number=session.caller_number,
            channel_status=channel_status,
        )

        # Autorun deterministic score
        score_breakdown = score_from_parameters(call_params)

        session.call_parameters = call_params
        session.score_breakdown = score_breakdown
        session.current_score = score_breakdown.final_score
        session.current_level = score_breakdown.risk_level.value
        session.fired_rules = score_breakdown.fired_rules
        session.reasons = score_breakdown.reasons

        # Recommended verification actions based on score
        if score_breakdown.final_score >= 75:
            session.recommended_actions = [
                "CRITICAL FRAUD SIGNAL: Do not disclose OTP, PIN, or passwords.",
                "Terminate call immediately and contact bank directly via official number.",
            ]
        elif score_breakdown.final_score >= 50:
            session.recommended_actions = [
                "HIGH RISK: Suspend financial transactions until caller identity is confirmed.",
                "Verify caller through independent channel or safe word.",
            ]
        elif score_breakdown.final_score >= 25:
            session.recommended_actions = [
                "MEDIUM RISK: Verify claims independently before proceeding.",
            ]
        else:
            session.recommended_actions = [
                "LOW RISK: Standard caution recommended.",
            ]

        # Broadcast real-time risk update
        await self.broadcast_event(
            session, "risk_update",
            {
                "score": session.current_score,
                "level": session.current_level,
                "category_scores": {
                    "identity": score_breakdown.identity,
                    "request": score_breakdown.request,
                    "behavior": score_breakdown.behavior,
                    "channel": score_breakdown.channel,
                    "voice": score_breakdown.voice,
                },
                "fired_rules": session.fired_rules,
                "reasons": session.reasons,
                "is_provisional": call_params.is_provisional,
            }
        )

    # ── State, Stop & Persistence ─────────────────────────────────────────────

    def get_state_response(self, session: LiveSession) -> LiveSessionStateResponse:
        """Construct the canonical LiveSessionStateResponse for this session."""
        cat_scores = None
        if session.score_breakdown:
            cat_scores = CategoryScores(
                identity=session.score_breakdown.identity,
                request=session.score_breakdown.request,
                behavior=session.score_breakdown.behavior,
                channel=session.score_breakdown.channel,
                voice=session.score_breakdown.voice,
            )

        is_prov = True
        if session.call_parameters:
            is_prov = session.call_parameters.is_provisional

        return LiveSessionStateResponse(
            session_id=session.session_id,
            mode=session.mode,
            state=session.state,
            audio_authorized=session.audio_authorized,
            caller_number=session.caller_number,
            transcript=session.transcript_segments,
            current_score=session.current_score,
            current_level=session.current_level,
            category_scores=cat_scores,
            fired_rules=session.fired_rules,
            reasons=session.reasons,
            warnings=session.warnings,
            recommended_actions=session.recommended_actions,
            voice_status=session.voice_status,  # type: ignore
            voice_spoof_prob=session.voice_spoof_prob,
            is_provisional=is_prov,
            parameters=session.call_parameters.model_dump() if session.call_parameters else None,
            call_id=session.persisted_call_id,
        )

    async def end_session(self, session_id: str, user_id: str) -> LiveSessionStateResponse:
        """
        Stop session, persist final report into database, and notify connected clients.
        """
        session = self.get_session(session_id, user_id)
        if not session:
            raise ValueError("Session not found or unauthorized")

        session.state = "finalizing"

        # Cancel background processing loop
        if session.processing_task and not session.processing_task.done():
            session.processing_task.cancel()

        # Final recompute
        voice_ev = None
        if session.audio_authorized and session.windows_analyzed > 0:
            voice_ev = VoiceEvidence(
                status="ok",
                spoof_prob=session.voice_spoof_prob,
                windows_analyzed=session.windows_analyzed,
            )
        await self._recompute_scoring(session, voice_ev)

        # Persist to DB using canonical CallRecord and AnalysisReport
        try:
            from app.database.session import SessionLocal
            from app.models.call import CallRecord, AnalysisReport

            db = SessionLocal()
            try:
                call_record = CallRecord(
                    id=session.session_id,
                    owner_id=session.user_id,
                    original_filename=f"live_{session.mode}_{session.session_id[:8]}.wav",
                    stored_filename=f"live_{session.session_id}.wav",
                    storage_reference=f"live://{session.session_id}",
                    status="completed",
                    analysis_mode=session.mode,
                    completed_at=datetime.now(timezone.utc),
                )
                db.add(call_record)

                cat_scores_dict = None
                if session.score_breakdown:
                    cat_scores_dict = {
                        "identity": session.score_breakdown.identity,
                        "request": session.score_breakdown.request,
                        "behavior": session.score_breakdown.behavior,
                        "channel": session.score_breakdown.channel,
                        "voice": session.score_breakdown.voice,
                    }

                transcript_dict = {
                    "call_id": session.session_id,
                    "language": "en",
                    "transcription_status": "completed",
                    "segments": [s.model_dump() for s in session.transcript_segments],
                    "is_mock": (session.mode == "non_audio"),
                }

                voice_dict = {
                    "status": session.voice_status,
                    "spoof_prob": session.voice_spoof_prob,
                    "windows_analyzed": session.windows_analyzed,
                    "model": "AASIST-v2" if session.audio_authorized else None,
                }

                verification_dict = {
                    "action": "verify_contact" if session.current_score >= 50 else None,
                    "target": session.caller_number,
                    "safe_word_prompt": session.current_score >= 50,
                    "recommended_steps": session.recommended_actions,
                }

                report = AnalysisReport(
                    call_id=session.session_id,
                    transcript_json=json.dumps(transcript_dict),
                    voice_json=json.dumps(voice_dict),
                    agent_findings_json="[]",
                    risk_level=session.current_level,
                    risk_score=float(session.current_score),
                    reasons_json=json.dumps(session.reasons),
                    recommended_actions_json=json.dumps(session.recommended_actions),
                    warnings_json=json.dumps(session.warnings),
                    analysis_mode=session.mode,
                    category_scores_json=json.dumps(cat_scores_dict) if cat_scores_dict else None,
                    fired_rules_json=json.dumps(session.fired_rules),
                    verification_json=json.dumps(verification_dict),
                    killchain_stage=None,
                )
                db.add(report)
                db.commit()
                session.persisted_call_id = session.session_id
                logger.info(f"[LiveSession {session_id}] Persisted CallRecord and AnalysisReport to database")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[LiveSession {session_id}] DB persistence failed: {e}", exc_info=True)
            session.warnings.append(f"Report persistence warning: {str(e)[:100]}")

        session.state = "completed"

        # Broadcast completion
        await self.broadcast_event(
            session, "session_finalized",
            {
                "call_id": session.session_id,
                "score": session.current_score,
                "level": session.current_level,
                "transcript_count": len(session.transcript_segments),
            }
        )

        # Disconnect sockets cleanly
        for ws in list(session.websockets):
            try:
                await ws.close(code=1000, reason="Session ended")
            except Exception:
                pass
        session.websockets.clear()

        return self.get_state_response(session)

    async def cancel_session(self, session_id: str, user_id: str) -> None:
        """Abort session and cleanup resources without creating report records."""
        session = self.get_session(session_id, user_id)
        if not session:
            return

        session.state = "cancelled"
        if session.processing_task and not session.processing_task.done():
            session.processing_task.cancel()

        for ws in list(session.websockets):
            try:
                await ws.close(code=1000, reason="Session cancelled")
            except Exception:
                pass
        session.websockets.clear()
        session.accumulated_pcm.clear()

        async with self._lock:
            self.sessions.pop(session_id, None)

        logger.info(f"[LiveSession {session_id}] Cancelled and cleaned up")


# Global singleton instance
live_session_manager = LiveSessionManager()
