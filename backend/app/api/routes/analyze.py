"""
Member 2 API routes — Audio upload, job status, transcript, voice enrollment.

Phase 7: Now requires authentication and enforces ownership.

Endpoints (§6 API Specification):
  POST /analyze/recording       — Upload audio, kick off background analysis (AUTHENTICATED)
  GET  /call/{id}/state         — Full state: transcript + voice + score + timeline (AUTHENTICATED + OWNERSHIP)
  GET  /call/{id}/status        — Lightweight job status poll (AUTHENTICATED + OWNERSHIP)
  GET  /calls                   — History list (paginated) (AUTHENTICATED - own records only)
  POST /contacts/{id}/voiceprint— Enroll a 10-15s clip, store the embedding (AUTHENTICATED + OWNERSHIP)

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

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models.user import User
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
from app.services.integrity_service import integrity_service
from app.services.privacy_service import get_privacy_service
from app.services.real_analysis_service import real_analysis_service
from app.services.mock_analysis_service import mock_analysis_service
from app.auth.dependencies import get_current_active_user

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Helper: pick analysis backend based on config ─────────────────────────────

def _analysis_service():
    if settings.analysis_mode == "real":
        return real_analysis_service
    return mock_analysis_service


def _check_call_ownership(call: CallRecord, user: User) -> None:
    """
    Verify that the user owns the specified call record.
    
    Raises:
        HTTPException: 404 if call doesn't belong to user (avoid information disclosure)
    """
    if call.owner_id != user.id:
        # Return 404 instead of 403 to avoid revealing that the call exists
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )


def _check_contact_ownership(contact: Contact, user: User) -> None:
    """
    Verify that the user owns the specified contact.
    
    Raises:
        HTTPException: 404 if contact doesn't belong to user
    """
    if contact.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )


# ── POST /analyze/recording ───────────────────────────────────────────────────

@router.post("/analyze/recording", response_model=UploadResponse, status_code=202)
async def upload_recording(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Upload a call recording (WAV/MP3/M4A) for analysis.

    **Authentication required.** The recording will be associated with the authenticated user.

    Returns a call_id to poll for status.
    The audio is converted → transcribed → voice-analysed in a background task.
    """
    logger.info(f"Upload received from user {current_user.email}: {file.filename} ({file.content_type})")

    # Validate + save + calculate SHA-256
    stored_filename, storage_reference, original_filename, sha256_hash, file_size = await file_service.save_upload(file)

    # Create DB record with owner_id
    call = CallRecord(
        owner_id=current_user.id,  # Attach authenticated user as owner
        original_filename=original_filename,
        stored_filename=stored_filename,
        storage_reference=storage_reference,
        status="queued",
        analysis_mode=settings.analysis_mode,
    )
    db.add(call)
    db.flush()  # Get call.id before recording integrity
    
    # Record file integrity (Phase 8)
    from app.services.integrity_service import integrity_service
    from pathlib import Path
    
    integrity_service.record_file_hash(
        db=db,
        call_id=call.id,
        artifact_type="original_upload",
        file_path=stored_filename,
        sha256_hash=sha256_hash,
        file_size_bytes=file_size,
    )
    
    db.commit()
    db.refresh(call)

    logger.info(
        f"CallRecord created: {call.id} (owner={current_user.email}, mode={settings.analysis_mode}, "
        f"hash={sha256_hash[:16]}...)"
    )

    # Queue background analysis (pass call_id only, not the db session)
    background_tasks.add_task(
        _analysis_service().analyze_call,
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Legacy alias for /analyze/recording (backward compat). **Authentication required.**"""
    return await upload_recording(background_tasks, file, current_user, db)


# ── GET /call/{id}/status ─────────────────────────────────────────────────────

@router.get("/call/{call_id}/status", response_model=CallStatusResponse)
async def get_call_status(
    call_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lightweight job status poll. **Authentication required + ownership check.**
    Returns: queued | processing | completed | failed
    """
    call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Verify ownership
    _check_call_ownership(call, current_user)

    return CallStatusResponse(
        call_id=call.id,
        status=call.status,
        created_at=call.created_at,
        updated_at=call.updated_at,
        completed_at=call.completed_at,
        error=call.error_message,
    )


# Keep old path for Android app
@router.get("/calls/{call_id}/status", response_model=CallStatusResponse)
async def get_call_status_legacy(
    call_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Legacy alias. **Authentication required + ownership check.**"""
    return await get_call_status(call_id, current_user, db)


# ── GET /call/{id}/state ──────────────────────────────────────────────────────

@router.get("/call/{call_id}/state", response_model=AnalysisReportResponse)
async def get_call_state(
    call_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Full call state: transcript, voice evidence, risk score, timeline, kill-chain.
    **Authentication required + ownership check.**

    Returns 425 if analysis is still running.
    """
    call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Verify ownership
    _check_call_ownership(call, current_user)

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
async def get_report_legacy(
    call_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Legacy alias. **Authentication required + ownership check.**"""
    return await get_call_state(call_id, current_user, db)


# ── GET /call/{id}/counterfactual ─────────────────────────────────────────────

@router.get("/call/{call_id}/counterfactual")
async def get_counterfactual(
    call_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Returns counterfactual: 'What would make this call score lower?'
    Placeholder — full implementation in M3 Judge module.
    **Authentication required + ownership check.**
    """
    call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Verify ownership
    _check_call_ownership(call, current_user)

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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Paginated call history. **Authentication required - returns only user's own calls.**
    """
    offset = (page - 1) * page_size
    
    # Filter by owner_id
    total = db.query(CallRecord).filter(CallRecord.owner_id == current_user.id).count()
    calls = (
        db.query(CallRecord)
        .filter(CallRecord.owner_id == current_user.id)
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
async def get_transcript(
    call_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Return just the transcript for a completed call. **Authentication required + ownership check.**"""
    call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Verify ownership
    _check_call_ownership(call, current_user)

    report = db.query(AnalysisReport).filter(AnalysisReport.call_id == call_id).first()

    if not report or not report.transcript_json:
        status_val = "not_available" if call.status in ("queued", "processing") else "not_implemented"
        return TranscriptResponse(
            call_id=call_id,
            language=None,
            transcription_status=status_val,
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Enroll a 10–15s audio clip as a voiceprint for a contact.
    **Authentication required + ownership check.**

    Privacy-first (§9): Only the embedding is stored, NOT the raw audio.
    The uploaded clip is deleted immediately after embedding extraction.

    Returns the contact record with enrollment status.
    """
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Verify ownership
    _check_contact_ownership(contact, current_user)

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
            f"({contact.name}) by user {current_user.email} — {len(contact.voiceprint_embedding)} bytes"
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a trusted contact entry for Trust Graph seeding. **Authentication required.**"""
    numbers_json = (
        json.dumps([n.strip() for n in saved_numbers.split(",")]) if saved_numbers else "[]"
    )
    contact = Contact(
        owner_id=current_user.id,
        name=name,
        relation=relation,
        saved_numbers=numbers_json,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    logger.info(f"Contact created: {contact.name} by user {current_user.email}")

    return {
        "contact_id": contact.id,
        "name": contact.name,
        "relation": contact.relation,
        "saved_numbers": json.loads(contact.saved_numbers or "[]"),
        "voiceprint_enrolled": contact.voiceprint_embedding is not None,
    }


# ── GET /contacts ──────────────────────────────────────────────────────────────

@router.get("/contacts")
async def list_contacts(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all enrolled contacts. **Authentication required - returns only user's own contacts.**"""
    contacts = db.query(Contact).filter(Contact.owner_id == current_user.id).all()
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
    """
    Deserialise DB JSON columns into the Pydantic response model.
    
    Phase 9: Applies PII masking to transcript and evidence before returning.
    """
    try:
        privacy_service = get_privacy_service()
        
        transcript_data = json.loads(report.transcript_json) if report.transcript_json else None
        agent_findings_data = json.loads(report.agent_findings_json) if report.agent_findings_json else []
        reasons_data = json.loads(report.reasons_json) if report.reasons_json else []
        recommended_actions_data = json.loads(report.recommended_actions_json) if report.recommended_actions_json else []
        warnings_data = json.loads(report.warnings_json) if report.warnings_json else []
        
        # Phase 5: Deserialize v3 Trust Engine fields
        category_scores_data = json.loads(report.category_scores_json) if report.category_scores_json else None
        fired_rules_data = json.loads(report.fired_rules_json) if report.fired_rules_json else []
        verification_data = json.loads(report.verification_json) if report.verification_json else None
        voice_data = json.loads(report.voice_json) if report.voice_json else None

        # Phase 9: Sanitize transcript data before creating response
        transcript = None
        if transcript_data:
            # Apply PII masking to segments
            sanitized_transcript_data = privacy_service.sanitize_transcript_response(transcript_data)
            if sanitized_transcript_data:
                segments = [TranscriptSegment(**s) for s in sanitized_transcript_data.get("segments", [])]
                transcript = TranscriptResponse(
                    call_id=sanitized_transcript_data.get("call_id", call.id),
                    language=sanitized_transcript_data.get("language"),
                    transcription_status=sanitized_transcript_data.get("transcription_status", "completed"),
                    segments=segments,
                    is_mock=sanitized_transcript_data.get("is_mock", False),
                )

        # Phase 9: Sanitize agent findings
        sanitized_findings = privacy_service.sanitize_agent_findings(agent_findings_data)
        agent_findings = [AgentFinding(**f) for f in sanitized_findings]
        
        # Phase 9: Sanitize reasons (may contain quoted PII)
        sanitized_reasons = []
        for reason in reasons_data:
            masked_reason, _ = privacy_service.pii_masker.mask_text(reason, audit=False)
            sanitized_reasons.append(masked_reason)
        
        # Import Pydantic models for validation
        from app.schemas.report import CategoryScores, Verification, VoiceEvidence
        
        category_scores = CategoryScores(**category_scores_data) if category_scores_data else None
        verification = Verification(**verification_data) if verification_data else None
        voice = VoiceEvidence(**voice_data) if voice_data else None

        return AnalysisReportResponse(
            call_id=call.id,
            status=call.status,
            analysis_mode=report.analysis_mode,
            language=transcript_data.get("language") if transcript_data else None,
            transcript=transcript,
            agent_findings=agent_findings,
            level=report.risk_level,
            score=int(report.risk_score) if report.risk_score is not None else 0,
            category_scores=category_scores,
            fired_rules=fired_rules_data,
            killchain_stage=report.killchain_stage,
            verification=verification,
            voice=voice,
            counterfactuals=[],
            reasons=sanitized_reasons,
            recommended_actions=recommended_actions_data,
            warnings=warnings_data,
            created_at=call.created_at,
            completed_at=call.completed_at,
        )
    except Exception as e:
        logger.error(f"Failed to build report response for {call.id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to parse report data")



# ── Phase 8: File Integrity Verification ──────────────────────────────────────

@router.get("/calls/{call_id}/integrity", status_code=200)
async def verify_file_integrity(
    call_id: str,
    artifact_type: str = Query("original_upload", description="Artifact type to verify"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Verify file integrity using SHA-256 hash comparison.
    
    **Authentication required.** Only the recording owner can verify integrity.
    
    Compares current file SHA-256 with recorded digest.
    
    Returns:
    - verified: File matches stored hash
    - mismatch: File bytes differ (SECURITY ISSUE)
    - unavailable: Hash or file not available for check
    
    LIMITATIONS:
    - Detects byte-level modifications only
    - Does not prove recording authenticity before upload
    - Not a legal-grade forensic chain of custody
    """
    # Get call record and check ownership
    call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
    _check_call_ownership(call, current_user)
    
    # Get file path
    file_path = Path(call.storage_reference)
    
    # Verify integrity
    status_result, message = integrity_service.verify_file_integrity(
        db=db,
        call_id=call_id,
        artifact_type=artifact_type,
        file_path=file_path,
    )
    
    # Get stored record for response
    stored_record = integrity_service.get_stored_hash(db, call_id, artifact_type)
    
    response = {
        "call_id": call_id,
        "artifact_type": artifact_type,
        "status": status_result,
        "message": message,
    }
    
    if stored_record:
        response["stored_hash"] = stored_record.sha256_hash
        response["stored_size"] = stored_record.file_size_bytes
        response["hash_algorithm"] = stored_record.hash_algorithm
        response["recorded_at"] = stored_record.created_at.isoformat()
    
    # Log security events
    if status_result == "mismatch":
        logger.error(
            f"SECURITY: File integrity violation detected! "
            f"call_id={call_id}, artifact={artifact_type}, user={current_user.email}"
        )
    
    return response


@router.get("/calls/{call_id}/integrity/all", status_code=200)
async def get_all_integrity_records(
    call_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get all integrity records for a call.
    
    **Authentication required.** Only the recording owner can access integrity records.
    
    Returns list of all file hashes associated with this call
    (original upload, processed audio, etc.).
    """
    # Get call record and check ownership
    call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
    _check_call_ownership(call, current_user)
    
    # Get all integrity records
    records = integrity_service.get_all_hashes_for_call(db, call_id)
    
    return {
        "call_id": call_id,
        "total_artifacts": len(records),
        "artifacts": [
            {
                "artifact_type": rec.artifact_type,
                "file_path": rec.file_path,
                "sha256_hash": rec.sha256_hash,
                "file_size_bytes": rec.file_size_bytes,
                "hash_algorithm": rec.hash_algorithm,
                "recorded_at": rec.created_at.isoformat(),
            }
            for rec in records
        ],
    }
