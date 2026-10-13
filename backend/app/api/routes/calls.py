"""
API routes for call recording operations.
"""
import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from datetime import datetime
import math

from app.database.session import get_db
from app.models.call import CallRecord, AnalysisReport
from app.schemas.call import UploadResponse, CallStatusResponse, CallListResponse, CallListItem, PaginationInfo
from app.schemas.report import TranscriptResponse, AnalysisReportResponse, TranscriptSegment, AgentFinding
from app.services.file_service import file_service
from app.services.mock_analysis_service import mock_analysis_service
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/calls", response_model=UploadResponse, status_code=202)
async def upload_recording(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a call recording for analysis.
    
    Accepts audio files (WAV, MP3, M4A) and queues them for analysis.
    Returns a call_id that can be used to track the analysis status.
    """
    logger.info(f"Received upload request: {file.filename}")
    
    # Save uploaded file
    stored_filename, storage_reference, original_filename = await file_service.save_upload(file)
    
    # Create call record
    call_record = CallRecord(
        original_filename=original_filename,
        stored_filename=stored_filename,
        storage_reference=storage_reference,
        status="queued",
        analysis_mode=settings.analysis_mode
    )
    
    db.add(call_record)
    db.commit()
    db.refresh(call_record)
    
    logger.info(f"Call record created: {call_record.id}")
    
    # Queue analysis in background
    background_tasks.add_task(
        mock_analysis_service.analyze_call,
        db=db,
        call_id=call_record.id
    )
    
    return UploadResponse(
        call_id=call_record.id,
        status="queued",
        message="Recording accepted for analysis",
        analysis_mode=settings.analysis_mode
    )


@router.get("/calls", response_model=CallListResponse)
async def list_calls(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    Retrieve a paginated list of call recordings.
    
    Returns all previously submitted calls with their current status.
    """
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Get total count
    total = db.query(CallRecord).count()
    
    # Get paginated results
    calls = db.query(CallRecord)\
        .order_by(CallRecord.created_at.desc())\
        .offset(offset)\
        .limit(page_size)\
        .all()
    
    # Convert to response format
    call_items = [
        CallListItem(
            call_id=call.id,
            original_filename=call.original_filename,
            status=call.status,
            created_at=call.created_at,
            updated_at=call.updated_at
        )
        for call in calls
    ]
    
    # Calculate pagination info
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    pagination = PaginationInfo(
        page=page,
        page_size=page_size,
        total=total,
        pages=total_pages
    )
    
    return CallListResponse(calls=call_items, pagination=pagination)


@router.get("/calls/{call_id}/status", response_model=CallStatusResponse)
async def get_call_status(call_id: str, db: Session = Depends(get_db)):
    """
    Check the processing status of a call.
    
    Returns the current status: queued, processing, completed, or failed.
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
        error=call.error_message
    )


@router.get("/calls/{call_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(call_id: str, db: Session = Depends(get_db)):
    """
    Retrieve the transcription of a call recording.
    
    In Phase 1, this returns mock transcript data for demonstration.
    """
    call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Get report if available
    report = db.query(AnalysisReport).filter(AnalysisReport.call_id == call_id).first()
    
    if not report:
        # If analysis not complete, return not available status
        if call.status in ["queued", "processing"]:
            return TranscriptResponse(
                call_id=call_id,
                language=None,
                transcription_status="not_available",
                segments=[],
                is_mock=True
            )
        else:
            # Analysis failed or completed without report
            return TranscriptResponse(
                call_id=call_id,
                language=None,
                transcription_status="not_implemented",
                segments=[],
                is_mock=True
            )
    
    # Parse transcript JSON
    try:
        transcript_data = json.loads(report.transcript_json)
        return TranscriptResponse(**transcript_data)
    except Exception as e:
        logger.error(f"Failed to parse transcript: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve transcript")


@router.get("/calls/{call_id}/report", response_model=AnalysisReportResponse)
async def get_report(call_id: str, db: Session = Depends(get_db)):
    """
    Retrieve the complete analysis report for a call.
    
    Returns the full analysis including transcript, findings, risk assessment,
    and recommended actions.
    """
    call = db.query(CallRecord).filter(CallRecord.id == call_id).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    # Check if analysis is complete
    if call.status in ["queued", "processing"]:
        raise HTTPException(
            status_code=425,
            detail=f"Analysis in progress. Current status: {call.status}"
        )
    
    if call.status == "failed":
        raise HTTPException(
            status_code=500,
            detail=call.error_message or "Analysis failed"
        )
    
    # Get report
    report = db.query(AnalysisReport).filter(AnalysisReport.call_id == call_id).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Parse JSON fields
    try:
        transcript_data = json.loads(report.transcript_json) if report.transcript_json else None
        agent_findings_data = json.loads(report.agent_findings_json) if report.agent_findings_json else []
        reasons_data = json.loads(report.reasons_json) if report.reasons_json else []
        recommended_actions_data = json.loads(report.recommended_actions_json) if report.recommended_actions_json else []
        warnings_data = json.loads(report.warnings_json) if report.warnings_json else []
        
        # Build transcript response
        transcript = None
        if transcript_data:
            segments = [TranscriptSegment(**seg) for seg in transcript_data.get("segments", [])]
            transcript = TranscriptResponse(
                call_id=transcript_data.get("call_id", call_id),
                language=transcript_data.get("language"),
                transcription_status=transcript_data.get("transcription_status", "completed"),
                segments=segments,
                is_mock=transcript_data.get("is_mock", True)
            )
        
        # Build agent findings
        agent_findings = [AgentFinding(**finding) for finding in agent_findings_data]
        
        # Build full response
        return AnalysisReportResponse(
            call_id=call.id,
            status=call.status,
            analysis_mode=report.analysis_mode,
            language=transcript_data.get("language") if transcript_data else None,
            transcript=transcript,
            agent_findings=agent_findings,
            level=report.risk_level,
            score=int(report.risk_score) if report.risk_score is not None else 0,
            reasons=reasons_data,
            recommended_actions=recommended_actions_data,
            warnings=warnings_data,
            created_at=call.created_at,
            completed_at=call.completed_at,
        )
        
    except Exception as e:
        logger.error(f"Failed to build report response: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve report")
