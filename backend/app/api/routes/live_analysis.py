"""
API routes for real-time live fraud detection sessions and WebSocket transport.
Includes REST session controls, non-audio message submission, and streaming WebSocket endpoint.
"""
from __future__ import annotations

import json
import logging
import struct
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_active_user,
    get_current_active_user_websocket,
)
from app.database.session import get_db
from app.models.user import User
from app.schemas.live_session import (
    LiveSessionStartRequest,
    LiveSessionStartResponse,
    LiveSessionStateResponse,
    SubmitNonAudioMessageRequest,
)
from app.services.live_session_manager import (
    MAX_PAYLOAD_SIZE,
    live_session_manager,
)

router = APIRouter(prefix="/live", tags=["Live Analysis"])
logger = logging.getLogger(__name__)


# ── REST Session Endpoints ───────────────────────────────────────────────────

@router.post("/sessions", response_model=LiveSessionStartResponse, status_code=status.HTTP_201_CREATED)
async def create_live_session(
    request: LiveSessionStartRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Start a new live scam analysis session.
    Modes:
      - 'non_audio': User manual/companion statement reporting (safe fallback).
      - 'webrtc': Internet calling with authorized microphone and remote tracks.
      - 'cellular': Cellular call analysis via authorized adapter.
    """
    try:
        session = await live_session_manager.create_session(
            user_id=current_user.id,
            request=request,
        )
        return LiveSessionStartResponse(
            session_id=session.session_id,
            mode=session.mode,
            state=session.state,
            audio_authorized=session.audio_authorized,
            voice_analysis_status=session.voice_status,  # type: ignore
            created_at=session.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))


@router.get("/sessions/{session_id}", response_model=LiveSessionStateResponse)
async def get_live_session_state(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Get the current live state, transcript, parameters, and risk score for a session."""
    session = live_session_manager.get_session(session_id, user_id=current_user.id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Live session not found")
    return live_session_manager.get_state_response(session)


@router.post("/sessions/{session_id}/message", response_model=LiveSessionStateResponse)
async def submit_non_audio_message(
    session_id: str,
    request: SubmitNonAudioMessageRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Phase 3: Submit a suspicious statement, request, or claim heard during the call.
    Extracts structured parameters and immediately updates the deterministic Trust Judge.
    Does NOT claim voice was analyzed.
    """
    session = live_session_manager.get_session(session_id, user_id=current_user.id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Live session not found")

    return await live_session_manager.submit_non_audio_message(
        session_id=session_id,
        user_id=current_user.id,
        text=request.text,
        speaker=request.speaker or "caller",
        timestamp_s=request.timestamp_s,
    )


@router.post("/sessions/{session_id}/stop", response_model=LiveSessionStateResponse)
async def stop_live_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Finalize the live session and persist the final report and call record to the database.
    """
    session = live_session_manager.get_session(session_id, user_id=current_user.id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Live session not found")

    return await live_session_manager.end_session(session_id, user_id=current_user.id)


@router.post("/sessions/{session_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_live_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Abort the live session and discard temporary audio/buffers without persisting a report.
    """
    session = live_session_manager.get_session(session_id, user_id=current_user.id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Live session not found")

    await live_session_manager.cancel_session(session_id, user_id=current_user.id)
    return None


# ── WebSocket Streaming Endpoint ─────────────────────────────────────────────

@router.websocket("/ws/analyze")
async def websocket_live_analysis(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
):
    """
    Real-time bidirectional WebSocket transport.
    Supports binary audio chunk streaming, non-audio message events, and real-time alerts.

    Handshake:
      1. Connect with ?token=...&session_id=... OR send {"type":"auth","token":"...","session_id":"..."}.
      2. Server responds with {"type": "auth_ok", "session_id": "..."}.
      3. Client streams binary audio chunks (<IQHHB header) or JSON messages.
      4. Server pushes real-time 'risk_update', 'transcript_final', 'warning', etc.
    """
    await websocket.accept()

    current_session = None
    user = None

    try:
        # Step 1: Authenticate
        auth_token = token
        sid = session_id

        if not auth_token:
            auth_msg = await websocket.receive_json()
            if auth_msg.get("type") != "auth" or not auth_msg.get("token"):
                await websocket.send_json({"type": "error", "message": "Authentication token required"})
                await websocket.close(code=1008)
                return
            auth_token = auth_msg["token"]
            sid = auth_msg.get("session_id") or sid

        try:
            user = await get_current_active_user_websocket(auth_token)
        except Exception as exc:
            await websocket.send_json({"type": "error", "message": f"Auth failed: {str(exc)}"})
            await websocket.close(code=1008)
            return

        # If session_id not passed, create one automatically
        if not sid:
            req = LiveSessionStartRequest(mode="non_audio", audio_authorized=False)
            current_session = await live_session_manager.create_session(user_id=user.id, request=req)
            sid = current_session.session_id
        else:
            current_session = live_session_manager.get_session(sid, user_id=user.id)
            if not current_session:
                await websocket.send_json({"type": "error", "message": "Session not found or unauthorized"})
                await websocket.close(code=1008)
                return

        # Register socket with session
        await live_session_manager.register_websocket(sid, websocket, user_id=user.id)

        await websocket.send_json({
            "type": "auth_ok",
            "session_id": sid,
            "mode": current_session.mode,
            "audio_authorized": current_session.audio_authorized,
            "voice_status": current_session.voice_status,
        })

        # Step 2: Main receive loop
        while True:
            message = await websocket.receive()

            if "bytes" in message and message["bytes"]:
                raw_bytes = message["bytes"]
                if len(raw_bytes) < 16:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Malformed audio chunk: header must be at least 16 bytes",
                    })
                    continue

                if len(raw_bytes) > MAX_PAYLOAD_SIZE:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Chunk exceeds maximum size ({MAX_PAYLOAD_SIZE} bytes)",
                    })
                    continue

                # Unpack 16-byte binary header:
                # 4 bytes: sequence_number (uint32)
                # 8 bytes: timestamp_ms (uint64)
                # 2 bytes: sample_rate (uint16)
                # 1 byte:  channel_count (uint8)
                # 1 byte:  encoding (uint8, 0=PCM_16BIT)
                seq_num, ts_ms, s_rate, ch_count, _ = struct.unpack("<IQHHB", raw_bytes[:16])
                audio_payload = raw_bytes[16:]

                await live_session_manager.submit_audio_chunk(
                    session_id=sid,
                    user_id=user.id,
                    sequence_number=seq_num,
                    timestamp_ms=ts_ms,
                    sample_rate=s_rate,
                    channel_count=ch_count,
                    audio_data=audio_payload,
                )

            elif "text" in message and message["text"]:
                try:
                    payload = json.loads(message["text"])
                    msg_type = payload.get("type")

                    if msg_type == "submit_message":
                        txt = payload.get("text", "")
                        spk = payload.get("speaker", "caller")
                        ts = payload.get("timestamp_s")
                        await live_session_manager.submit_non_audio_message(
                            session_id=sid,
                            user_id=user.id,
                            text=txt,
                            speaker=spk,
                            timestamp_s=ts,
                        )

                    elif msg_type == "stop":
                        await live_session_manager.end_session(session_id=sid, user_id=user.id)
                        break

                    elif msg_type == "cancel":
                        await live_session_manager.cancel_session(session_id=sid, user_id=user.id)
                        break

                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Unknown event type: {msg_type}",
                        })
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "message": "Invalid JSON text message"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from session {sid}")
    except Exception as e:
        logger.error(f"WebSocket error in session {sid}: {e}", exc_info=True)
    finally:
        if sid and websocket:
            live_session_manager.unregister_websocket(sid, websocket)
