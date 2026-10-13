"""
Member 2 API routes — Audio upload, job status, transcript, voice enrollment.

Endpoints (§6 API Specification):
  POST /analyze/recording       — Upload audio, kick off background analysis
  GET  /call/{id}/state         — Full state: transcript + voice + score + timeline
  GET  /call/{id}/status        — Lightweight job status poll
  GET  /calls                   — History list (paginated)
  POST /contacts/{id}/voiceprint— Enroll a 10-15s clip, store the embedding

All audio goes through:
  1. Extension + size validation (FileService)
  2. ffmpeg → 16 kHz mono WAV   (AudioPreprocessor)
  3. faster-whisper ASR          (ASRService)
  4. Voice layer (parallel)      (VoiceLayer)
  5. Results saved to DB         (RealAnalysisService)
"""
import json
import logging
import math
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models.call import AnalysisReport, CallRecord, Contact
from app.schemas.call import (
    CallListItem,
    CallListResponse,
    CallStatusResponse,
    PaginationInfo,
    UploadResponse,
)
from app.schemas.report import AnalysisReportResponse, TranscriptResponse, TranscriptSegment, AgentFinding
from app.services.file_service import file_service
from app.services.real_analysis_service import real_analysis_service
from app.services.mock_analysis_service import mock_analysis_service

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Helper: pick analysis backend based on config ─────────────────────────────

def _analysis_service():
    if settings.analysis_mode == "real":
        return real_analysis_service
    return mock_analysis_service


# ── POST /analyze/recording ───────────────────────────────────────────────────

@router.post("/analyze/recording", response_model=UploadResponse, status_code=202)
async def upload_recording(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a call recording (WAV/MP3/M4A) for analysis.

    Returns a call_id to poll for status.
    The audio is converted → transcribed → voice-analysed in a background task.
    """
    logger.info(f"Upload received: {file.filename} ({file.content_type})")

    # Validate + save
    stored_filename, storage_reference, original_filename = await file_service.save_upload(file)

    # Create DB record
    call = CallRecord(
        original_filename=original_filename,
        stored_filename=stored_filename,
        storage_reference=storage_reference,
        status="queued",
        analysis_mode=settings.analysis_mode,
    )
    db.add(call)
    db.commit()
    db.refresh(call)

    logger.info(f"CallRecord created: {call.id} (mode={settings.analysis_mode})")

    # Queue background analysis
    background_tasks.add_task(
        _analysis_service().analyze_call,
        db=db,
        call_id=call.id,
    )

    return UploadResponse(
        call_id=call.id,
        status="queued",
        message=f"Recording accepted for analysis (mode: {settings.analysis_mode})",
        analysis_mode=settings.analysis_mode,
    )


# Keep the old /calls POST for backward compat (Android app uses it)
@router.post("/calls", response_model=UploadResponse, status_code=202)
async def upload_recording_legacy(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Legacy alias for /analyze/recording (backward compat)."""
    return await upload_recording(background_tasks, file, db)


# ── GET /call/{id}/status ─────────────────────────────────────────────────────

@router.get("/call/{call_id}/status", response_model=CallStatusResponse)
async def get_call_status(call_id: str, db: Session = Depends(get_db)):
    """
    Lightweight job status poll.
    Returns: queued | processing | completed | failed
    """
    call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    return CallStatusResponse(
        call_id=call.id,
        status=call.status,
        created_at=call.created_at,
        updated_at=call.updated_at,
        completed_at=call.completed_at,
        error_message=call.error_message,
    )


# Keep old path for Android app
@router.get("/calls/{call_id}/status", response_model=CallStatusResponse)
async def get_call_status_legacy(call_id: str, db: Session = Depends(get_db)):
    return await get_call_status(call_id, db)


# ── GET /call/{id}/state ──────────────────────────────────────────────────────

@router.get("/call/{call_id}/state", response_model=AnalysisReportResponse)
async def get_call_state(call_id: str, db: Session = Depends(get_db)):
    """
    Full call state: transcript, voice evidence, risk score, timeline, kill-chain.

    Returns 425 if analysis is still running.
    """
    call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    if call.status in ("queued", "processing"):
        raise HTTPException(
            status_code=425,
            detail=f"Analysis still in progress. Status: {call.status}",
        )

    if call.status == "failed":
        raise HTTPException(
            status_code=500,
            detail=call.error_message or "Analysis failed",
        )

    report = db.query(AnalysisReport).filter(AnalysisReport.call_id == call_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return _build_report_response(call, report)


# Keep old /calls/{id}/report path for Streamlit dashboard
@router.get("/calls/{call_id}/report", response_model=AnalysisReportResponse)
async def get_report_legacy(call_id: str, db: Session = Depends(get_db)):
    return await get_call_state(call_id, db)


# ── GET /call/{id}/counterfactual ─────────────────────────────────────────────

@router.get("/call/{call_id}/counterfactual")
async def get_counterfactual(call_id: str, db: Session = Depends(get_db)):
    """
    Returns counterfactual: 'What would make this call score lower?'
    Placeholder — full implementation in M3 Judge module.
    """
    call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    report = db.query(AnalysisReport).filter(AnalysisReport.call_id == call_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Placeholder counterfactuals (M3 Judge will fill these properly)
    return {
        "call_id": call_id,
        "current_score": report.risk_score,
        "current_level": report.risk_level,
        "counterfactuals": [
            {
                "change": "Call came from Mom's saved number",
                "new_score": 15,
                "new_level": "low",
            },
            {
                "change": "No OTP/money request made",
                "new_score": max(0, (report.risk_score or 0) - 30),
                "new_level": "low",
            },
        ],
        "note": "Full counterfactual computation pending M3 Judge module.",
    }


# ── GET /calls ────────────────────────────────────────────────────────────────

@router.get("/calls", response_model=CallListResponse)
async def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Paginated call history."""
    offset = (page - 1) * page_size
    total = db.query(CallRecord).count()
    calls = (
        db.query(CallRecord)
        .order_by(CallRecord.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items = [
        CallListItem(
            call_id=c.id,
            original_filename=c.original_filename,
            status=c.status,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in calls
    ]

    return CallListResponse(
        calls=items,
        pagination=PaginationInfo(
            page=page,
            page_size=page_size,
            total=total,
            pages=math.ceil(total / page_size) if total > 0 else 0,
        ),
    )


# ── GET /calls/{id}/transcript ────────────────────────────────────────────────

@router.get("/calls/{call_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(call_id: str, db: Session = Depends(get_db)):
    """Return just the transcript for a completed call."""
    call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    report = db.query(AnalysisReport).filter(AnalysisReport.call_id == call_id).first()

    if not report or not report.transcript_json:
        status = "not_available" if call.status in ("queued", "processing") else "not_implemented"
        return TranscriptResponse(
            call_id=call_id,
            language=None,
            transcription_status=status,
            segments=[],
            is_mock=call.analysis_mode == "mock",
        )

    try:
        data = json.loads(report.transcript_json)
        segments = [TranscriptSegment(**s) for s in data.get("segments", [])]
        return TranscriptResponse(
            call_id=call_id,
            language=data.get("language"),
            transcription_status=data.get("transcription_status", "completed"),
            segments=segments,
            is_mock=data.get("is_mock", False),
        )
    except Exception as e:
        logger.error(f"Failed to parse transcript for {call_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse transcript")


# ── POST /contacts/{id}/voiceprint ────────────────────────────────────────────

@router.post("/contacts/{contact_id}/voiceprint", status_code=200)
async def enroll_voiceprint(
    contact_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Enroll a 10–15s audio clip as a voiceprint for a contact.

    Privacy-first (§9): Only the embedding is stored, NOT the raw audio.
    The uploaded clip is deleted immediately after embedding extraction.

    Returns the contact record with enrollment status.
    """
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Save clip to temp file
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    try:
        # Write upload to disk
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file")

        tmp_path.write_bytes(content)

        # Convert to 16 kHz mono WAV
        from app.audio.preprocessor import convert_to_wav, validate_audio
        wav_path = convert_to_wav(tmp_path)

        # Validate
        is_valid, reason = validate_audio(wav_path)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Audio invalid: {reason}")

        # Extract embedding
        from app.audio.voice_layer import get_voice_layer
        voice_layer = get_voice_layer()
        embedding = voice_layer.get_embedding(wav_path)

        if embedding is None:
            return {
                "contact_id": contact_id,
                "enrolled": False,
                "message": "Voice model unavailable — install speechbrain for voiceprint enrollment.",
            }

        # Store embedding bytes (numpy float32 → bytes)
        import numpy as np
        contact.voiceprint_embedding = embedding.astype(np.float32).tobytes()
        contact.voiceprint_model = "speechbrain/spkrec-ecapa-voxceleb"
        contact.voiceprint_enrolled_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            f"Voiceprint enrolled for contact {contact_id} "
            f"({contact.name}) — {len(contact.voiceprint_embedding)} bytes"
        )

        return {
            "contact_id": contact_id,
            "name": contact.name,
            "enrolled": True,
            "enrolled_at": contact.voiceprint_enrolled_at.isoformat(),
            "model": contact.voiceprint_model,
            "message": "Voiceprint enrolled successfully. Audio deleted — only embedding stored.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voiceprint enrollment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Enrollment failed: {e}")
    finally:
        # Always delete temp files — privacy first
        for p in [tmp_path]:
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass


# ── POST /contacts ─────────────────────────────────────────────────────────────

@router.post("/contacts", status_code=201)
async def create_contact(
    name: str = Query(..., description="Contact name"),
    relation: Optional[str] = Query(None, description="Relation (e.g. mother, bank)"),
    saved_numbers: Optional[str] = Query(None, description="Comma-separated phone numbers"),
    db: Session = Depends(get_db),
):
    """Create a trusted contact entry for Trust Graph seeding."""
    numbers_json = (
        json.dumps([n.strip() for n in saved_numbers.split(",")]) if saved_numbers else "[]"
    )
    contact = Contact(
        name=name,
        relation=relation,
        saved_numbers=numbers_json,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    return {
        "contact_id": contact.id,
        "name": contact.name,
        "relation": contact.relation,
        "saved_numbers": json.loads(contact.saved_numbers or "[]"),
        "voiceprint_enrolled": contact.voiceprint_embedding is not None,
    }


# ── GET /contacts ──────────────────────────────────────────────────────────────

@router.get("/contacts")
async def list_contacts(db: Session = Depends(get_db)):
    """List all enrolled contacts."""
    contacts = db.query(Contact).all()
    return [
        {
            "contact_id": c.id,
            "name": c.name,
            "relation": c.relation,
            "saved_numbers": json.loads(c.saved_numbers or "[]"),
            "voiceprint_enrolled": c.voiceprint_embedding is not None,
            "voiceprint_enrolled_at": (
                c.voiceprint_enrolled_at.isoformat() if c.voiceprint_enrolled_at else None
            ),
        }
        for c in contacts
    ]


# ── Internal helper ───────────────────────────────────────────────────────────

def _build_report_response(call: CallRecord, report: AnalysisReport) -> AnalysisReportResponse:
    """Deserialise DB JSON columns into the Pydantic response model."""
    try:
        transcript_data = json.loads(report.transcript_json) if report.transcript_json else None
        agent_findings_data = json.loads(report.agent_findings_json) if report.agent_findings_json else []
        reasons_data = json.loads(report.reasons_json) if report.reasons_json else []
        recommended_actions_data = json.loads(report.recommended_actions_json) if report.recommended_actions_json else []
        warnings_data = json.loads(report.warnings_json) if report.warnings_json else []

        transcript = None
        if transcript_data:
            segments = [TranscriptSegment(**s) for s in transcript_data.get("segments", [])]
            transcript = TranscriptResponse(
                call_id=transcript_data.get("call_id", call.id),
                language=transcript_data.get("language"),
                transcription_status=transcript_data.get("transcription_status", "completed"),
                segments=segments,
                is_mock=transcript_data.get("is_mock", False),
            )

        agent_findings = [AgentFinding(**f) for f in agent_findings_data]

        return AnalysisReportResponse(
            call_id=call.id,
            status=call.status,
            analysis_mode=report.analysis_mode,
            language=transcript_data.get("language") if transcript_data else None,
            transcript=transcript,
            agent_findings=agent_findings,
            risk_level=report.risk_level,
            risk_score=report.risk_score,
            reasons=reasons_data,
            recommended_actions=recommended_actions_data,
            warnings=warnings_data,
            created_at=call.created_at,
            completed_at=call.completed_at,
            is_mock=report.analysis_mode == "mock",
        )
    except Exception as e:
        logger.error(f"Failed to build report response for {call.id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to parse report data")
