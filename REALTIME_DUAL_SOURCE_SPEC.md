# VISHWAS Real-Time Dual-Source Implementation Specification

**Status:** 📋 SPECIFICATION - Implementation Required  
**Priority:** CRITICAL  
**Complexity:** MAJOR SYSTEM EXTENSION (Est. 60-100 hours)  
**Last Updated:** October 14, 2026

---

## Executive Summary

This document specifies the complete architecture and implementation plan for adding **real-time scam analysis** to VISHWAS using dual audio sources:

1. **Normal cellular calls** (via authorized privileged system integration)
2. **VISHWAS/WebRTC calls** (in-app calling with accessible audio tracks)

**Core Principle:** Agents propose. Rules decide. Humans verify.

---

## Current System Analysis

### Existing Components ✅

**Backend (`/backend`):**
- ✅ FastAPI + uvicorn
- ✅ SQLite database with Phase 7-9 security (auth, integrity, privacy)
- ✅ Batch analysis flow: Upload → ASR → Evidence → Trust Judge → Report
- ✅ `extract_evidence_streaming()` function (exists but not wired to WebSocket)
- ✅ Tier1Classifier with deduplication support
- ✅ Deterministic Trust Judge with category caps and risk floors
- ✅ AASIST anti-spoof integration (Phase 4-5)
- ✅ Privacy service with PII masking
- ✅ JWT authentication

**Android App (`/android-app`):**
- ✅ Kotlin + Jetpack Compose + Material 3
- ✅ MVVM architecture (ViewModel + StateFlow)
- ✅ Retrofit API client
- ✅ File upload functionality
- ✅ Results display and history

**Frontend (`/vishwas-frontend`):**
- ✅ React + Vite + TypeScript
- ✅ Auth context and protected routes
- ✅ Report visualization
- ✅ Dashboard UI

### Missing Components ❌

**Backend:**
- ❌ WebSocket endpoint for real-time audio streaming
- ❌ Session management for live analysis
- ❌ Incremental ASR integration
- ❌ Real-time parameter updates
- ❌ Live event broadcasting

**Android:**
- ❌ Microphone capture
- ❌ WebRTC integration
- ❌ Cellular audio adapter
- ❌ WebSocket client
- ❌ Real-time UI

**Frontend:**
- ❌ Live analysis dashboard
- ❌ WebSocket event handling
- ❌ Real-time risk updates

---

## Architecture Overview

### High-Level Flow

```
┌─────────────────┐
│  Android App    │
│  Audio Sources  │
└────────┬────────┘
         │ WebSocket (authenticated)
         ▼
┌─────────────────────────────────────────────┐
│         FastAPI Backend                      │
│  ┌──────────────────────────────────────┐  │
│  │  WebSocket Session Manager           │  │
│  │  - Auth & ownership                  │  │
│  │  - Bounded queues                    │  │
│  │  - Backpressure                      │  │
│  └──────────────┬───────────────────────┘  │
│                 ▼                            │
│  ┌──────────────────────────────────────┐  │
│  │  Incremental ASR (faster-whisper)    │  │
│  │  - Rolling window                    │  │
│  │  - Partial/final segments            │  │
│  └──────────────┬───────────────────────┘  │
│                 ▼                            │
│  ┌──────────────────────────────────────┐  │
│  │  Streaming Evidence Extraction       │  │
│  │  - extract_evidence_streaming()      │  │
│  │  - Deduplication                     │  │
│  └──────────────┬───────────────────────┘  │
│                 ▼                            │
│  ┌──────────────────────────────────────┐  │
│  │  AASIST Voice Anti-Spoof             │  │
│  │  - Rolling window analysis           │  │
│  │  - Async inference                   │  │
│  └──────────────┬───────────────────────┘  │
│                 ▼                            │
│  ┌──────────────────────────────────────┐  │
│  │  Deterministic Trust Judge           │  │
│  │  - Category caps & floors            │  │
│  │  - Parameter-based scoring           │  │
│  └──────────────┬───────────────────────┘  │
│                 ▼                            │
│  ┌──────────────────────────────────────┐  │
│  │  Event Broadcaster                   │  │
│  │  - transcript_update                 │  │
│  │  - risk_update                       │  │
│  │  - warning                           │  │
│  └──────────────────────────────────────┘  │
└──────────────────┬──────────────────────────┘
                   │ WebSocket events
                   ▼
┌─────────────────────────────────────────────┐
│         React Live Dashboard                 │
│  - Real-time transcript                      │
│  - Live risk score                           │
│  - Category breakdown                        │
│  - Voice analysis status                     │
│  - Warnings & recommendations                │
└──────────────────────────────────────────────┘
```

---

## Phase 1: Android Audio Sources & Adapters

**Estimated Time:** 12-16 hours  
**Priority:** CRITICAL

### 1.1 Common Audio Source Interface

**File:** `android-app/app/src/main/java/com/vishwas/app/audio/AudioSourceAdapter.kt`

```kotlin
/**
 * Common interface for all audio sources in VISHWAS.
 */
sealed class AudioSourceType {
    object Microphone : AudioSourceType()
    object WebRTC : AudioSourceType()
    object Cellular : AudioSourceType()
}

data class AudioChunk(
    val sessionId: String,
    val streamId: String,           // "local", "remote", "uplink", "downlink"
    val sequenceNumber: Long,
    val timestampMs: Long,
    val sampleRate: Int,
    val channelCount: Int,
    val encoding: AudioEncoding,
    val audioData: ByteArray,       // PCM samples
    val sourceType: AudioSourceType
)

enum class AudioEncoding {
    PCM_16BIT,
    PCM_FLOAT
}

sealed class AudioSourceStatus {
    object Available : AudioSourceStatus()
    object Unavailable : AudioSourceStatus()
    data class Degraded(val reason: String) : AudioSourceStatus()
    data class Failed(val error: String) : AudioSourceStatus()
}

interface AudioSourceAdapter {
    val sourceType: AudioSourceType
    val status: StateFlow<AudioSourceStatus>
    
    suspend fun initialize(): Result<Unit>
    suspend fun start(sessionId: String): Result<Unit>
    fun getAudioFlow(): Flow<AudioChunk>
    suspend fun stop()
    suspend fun release()
}
```

### 1.2 Microphone Adapter Implementation

**File:** `android-app/app/src/main/java/com/vishwas/app/audio/MicrophoneAdapter.kt`

```kotlin
class MicrophoneAdapter(
    private val context: Context
) : AudioSourceAdapter {
    
    override val sourceType = AudioSourceType.Microphone
    private val _status = MutableStateFlow<AudioSourceStatus>(AudioSourceStatus.Unavailable)
    override val status: StateFlow<AudioSourceStatus> = _status.asStateFlow()
    
    private val audioChunks = Channel<AudioChunk>(Channel.BUFFERED)
    private var audioRecord: AudioRecord? = null
    private var recordingJob: Job? = null
    private var sequenceNumber = 0L
    
    // Configuration
    private val sampleRate = 16000
    private val channelConfig = AudioFormat.CHANNEL_IN_MONO
    private val audioFormat = AudioFormat.ENCODING_PCM_16BIT
    private val bufferSize = AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat)
    
    override suspend fun initialize(): Result<Unit> {
        // Check permission
        if (!hasRecordPermission()) {
            _status.value = AudioSourceStatus.Failed("Missing RECORD_AUDIO permission")
            return Result.failure(SecurityException("Missing permission"))
        }
        
        try {
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.VOICE_COMMUNICATION,
                sampleRate,
                channelConfig,
                audioFormat,
                bufferSize
            )
            
            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                _status.value = AudioSourceStatus.Failed("AudioRecord initialization failed")
                return Result.failure(IllegalStateException("Failed to init"))
            }
            
            _status.value = AudioSourceStatus.Available
            return Result.success(Unit)
        } catch (e: Exception) {
            _status.value = AudioSourceStatus.Failed(e.message ?: "Unknown error")
            return Result.failure(e)
        }
    }
    
    override suspend fun start(sessionId: String): Result<Unit> {
        if (audioRecord == null) {
            return Result.failure(IllegalStateException("Not initialized"))
        }
        
        try {
            audioRecord?.startRecording()
            sequenceNumber = 0L
            
            recordingJob = CoroutineScope(Dispatchers.IO).launch {
                val buffer = ShortArray(bufferSize / 2)
                
                while (isActive && audioRecord?.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    val samplesRead = audioRecord?.read(buffer, 0, buffer.size) ?: 0
                    
                    if (samplesRead > 0) {
                        val chunk = AudioChunk(
                            sessionId = sessionId,
                            streamId = "microphone",
                            sequenceNumber = sequenceNumber++,
                            timestampMs = System.currentTimeMillis(),
                            sampleRate = sampleRate,
                            channelCount = 1,
                            encoding = AudioEncoding.PCM_16BIT,
                            audioData = shortArrayToByteArray(buffer, samplesRead),
                            sourceType = AudioSourceType.Microphone
                        )
                        
                        audioChunks.send(chunk)
                    }
                }
            }
            
            return Result.success(Unit)
        } catch (e: Exception) {
            _status.value = AudioSourceStatus.Failed(e.message ?: "Recording failed")
            return Result.failure(e)
        }
    }
    
    override fun getAudioFlow(): Flow<AudioChunk> = audioChunks.receiveAsFlow()
    
    override suspend fun stop() {
        recordingJob?.cancel()
        audioRecord?.stop()
    }
    
    override suspend fun release() {
        stop()
        audioRecord?.release()
        audioRecord = null
        audioChunks.close()
        _status.value = AudioSourceStatus.Unavailable
    }
    
    private fun hasRecordPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
    }
    
    private fun shortArrayToByteArray(shorts: ShortArray, count: Int): ByteArray {
        val bytes = ByteArray(count * 2)
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().put(shorts, 0, count)
        return bytes
    }
}
```

**Required Permissions:** `AndroidManifest.xml`

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.INTERNET" />
```

### 1.3 WebRTC Adapter (Skeleton)

**File:** `android-app/app/src/main/java/com/vishwas/app/audio/WebRTCAdapter.kt`

```kotlin
/**
 * Adapter for WebRTC calls made inside VISHWAS app.
 * 
 * Accesses local and remote audio tracks separately for 
 * speaker-aware analysis.
 */
class WebRTCAdapter : AudioSourceAdapter {
    override val sourceType = AudioSourceType.WebRTC
    private val _status = MutableStateFlow<AudioSourceStatus>(AudioSourceStatus.Unavailable)
    override val status: StateFlow<AudioSourceStatus> = _status.asStateFlow()
    
    // TODO: Integration with WebRTC PeerConnection
    // - Capture local audio track
    // - Capture remote audio track
    // - Separate streams with streamId "local" and "remote"
    
    override suspend fun initialize(): Result<Unit> {
        _status.value = AudioSourceStatus.Unavailable
        return Result.failure(NotImplementedError("WebRTC integration pending"))
    }
    
    // ... rest of interface implementation
}
```

### 1.4 Cellular Adapter (Capability Check Only)

**File:** `android-app/app/src/main/java/com/vishwas/app/audio/CellularAdapter.kt`

```kotlin
/**
 * Adapter for cellular call audio.
 * 
 * CRITICAL: Standard Android apps cannot access both sides of a cellular call.
 * This requires:
 * - Custom AOSP build with telephony hooks
 * - OEM-provided privileged system service
 * - Authorized platform signature
 * 
 * This adapter checks capability and reports honest status.
 */
class CellularAdapter(
    private val context: Context
) : AudioSourceAdapter {
    override val sourceType = AudioSourceType.Cellular
    private val _status = MutableStateFlow<AudioSourceStatus>(AudioSourceStatus.Unavailable)
    override val status: StateFlow<AudioSourceStatus> = _status.asStateFlow()
    
    override suspend fun initialize(): Result<Unit> {
        // Check if privileged telephony API is available
        val hasPrivilegedAccess = checkPrivilegedTelephonyAccess()
        
        if (!hasPrivilegedAccess) {
            _status.value = AudioSourceStatus.Unavailable
            Log.w(TAG, "Cellular audio requires privileged system integration")
            return Result.failure(SecurityException(
                "Cellular audio access requires system-level permissions. " +
                "Deploy as privileged system app or use custom AOSP build."
            ))
        }
        
        // If we reach here, attempt to initialize actual telephony hooks
        // ... (implementation depends on platform integration)
        
        return Result.success(Unit)
    }
    
    private fun checkPrivilegedTelephonyAccess(): Boolean {
        // Check for platform signature
        val packageManager = context.packageManager
        val packageInfo = packageManager.getPackageInfo(
            context.packageName,
            PackageManager.GET_SIGNATURES
        )
        
        // Check if app has MODIFY_PHONE_STATE (requires system signature)
        val hasModifyPhone = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.MODIFY_PHONE_STATE
        ) == PackageManager.PERMISSION_GRANTED
        
        return hasModifyPhone // Simplified check
    }
    
    override suspend fun start(sessionId: String): Result<Unit> {
        return Result.failure(NotImplementedError("Cellular audio not implemented"))
    }
    
    override fun getAudioFlow(): Flow<AudioChunk> = emptyFlow()
    
    override suspend fun stop() {}
    override suspend fun release() {}
    
    companion object {
        private const val TAG = "CellularAdapter"
    }
}
```

### 1.5 Android UI for Source Selection

**File:** `android-app/app/src/main/java/com/vishwas/app/ui/screens/LiveAnalysisScreen.kt`

```kotlin
@Composable
fun LiveAnalysisScreen(
    viewModel: LiveAnalysisViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        // Audio source selector
        AudioSourceSelector(
            selectedSource = uiState.selectedSource,
            microphoneStatus = uiState.microphoneStatus,
            webrtcStatus = uiState.webrtcStatus,
            cellularStatus = uiState.cellularStatus,
            onSourceSelected = { viewModel.selectSource(it) }
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        // Start/Stop controls
        if (!uiState.isAnalyzing) {
            Button(
                onClick = { viewModel.startAnalysis() },
                modifier = Modifier.fillMaxWidth(),
                enabled = uiState.canStart
            ) {
                Icon(Icons.Default.PlayArrow, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text("Start Live Analysis")
            }
        } else {
            Button(
                onClick = { viewModel.stopAnalysis() },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
            ) {
                Icon(Icons.Default.Stop, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text("Stop Analysis")
            }
        }
        
        // Live status
        if (uiState.isAnalyzing) {
            LiveAnalysisDisplay(
                transcript = uiState.transcript,
                riskScore = uiState.riskScore,
                warnings = uiState.warnings
            )
        }
    }
}
```

### Phase 1 Acceptance Criteria

- [ ] MicrophoneAdapter captures PCM audio on physical device
- [ ] Permission request/denial handled correctly
- [ ] Audio chunks have valid session ID, sequence, timestamp
- [ ] WebRTCAdapter interface defined (implementation can be pending)
- [ ] CellularAdapter reports honest unavailable status
- [ ] Android app builds without errors
- [ ] Existing file upload functionality still works

---

## Phase 2: WebSocket Transport & Session Management

**Estimated Time:** 14-18 hours  
**Priority:** CRITICAL

### 2.1 Backend WebSocket Endpoint

**File:** `backend/app/api/routes/live_analysis.py`

```python
"""
Real-time audio analysis WebSocket endpoint.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from typing import Dict
import asyncio
import logging
import struct
from datetime import datetime

from app.models.user import User
from app.auth.dependencies import get_current_active_user_websocket
from app.services.live_session_manager import LiveSessionManager

router = APIRouter(prefix="/live", tags=["live"])
logger = logging.getLogger(__name__)

# Singleton session manager
session_manager = LiveSessionManager()

@router.websocket("/ws/analyze")
async def websocket_audio_analysis(
    websocket: WebSocket,
    token: str,
):
    """
    WebSocket endpoint for real-time audio streaming and analysis.
    
    Protocol:
    1. Client sends: {"type": "auth", "token": "JWT_TOKEN"}
    2. Server responds: {"type": "auth_ok", "session_id": "..."}
    3. Client sends binary audio chunks with header
    4. Server sends JSON events: transcript, risk_update, warning, etc.
    
    Binary chunk format:
    - 4 bytes: sequence number (uint32, little-endian)
    - 8 bytes: timestamp_ms (uint64, little-endian)  
    - 2 bytes: sample_rate (uint16, little-endian)
    - 1 byte: channel_count (uint8)
    - 1 byte: encoding (0=PCM_16BIT)
    - N bytes: audio data
    """
    await websocket.accept()
    
    session_id = None
    user = None
    
    try:
        # Wait for authentication
        auth_msg = await websocket.receive_json()
        
        if auth_msg.get("type") != "auth":
            await websocket.send_json({"type": "error", "message": "Auth required"})
            await websocket.close(code=1008)
            return
        
        # Verify JWT token
        try:
            user = await get_current_active_user_websocket(auth_msg.get("token"))
        except Exception as e:
            await websocket.send_json({"type": "error", "message": "Invalid token"})
            await websocket.close(code=1008)
            return
        
        # Create session
        session = await session_manager.create_session(
            user_id=user.id,
            source_type=auth_msg.get("source_type", "microphone")
        )
        session_id = session.session_id
        
        await websocket.send_json({
            "type": "auth_ok",
            "session_id": session_id
        })
        
        logger.info(f"Live session {session_id} started for user {user.id}")
        
        # Start processing pipeline
        process_task = asyncio.create_task(
            session_manager.process_session(session_id, websocket)
        )
        
        # Receive loop
        while True:
            try:
                data = await websocket.receive_bytes()
                
                # Parse binary chunk
                if len(data) < 16:
                    logger.warning(f"Chunk too small: {len(data)} bytes")
                    continue
                
                seq_num, timestamp_ms, sample_rate, channel_count, encoding = struct.unpack(
                    '<IQHHB', data[:16]
                )
                audio_data = data[16:]
                
                # Submit to session
                await session_manager.submit_audio_chunk(
                    session_id=session_id,
                    sequence_number=seq_num,
                    timestamp_ms=timestamp_ms,
                    sample_rate=sample_rate,
                    channel_count=channel_count,
                    audio_data=audio_data
                )
                
            except WebSocketDisconnect:
                logger.info(f"Client disconnected from session {session_id}")
                break
            except Exception as e:
                logger.error(f"Error in receive loop: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)[:200]
                })
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        
    finally:
        if session_id:
            await session_manager.end_session(session_id)
            logger.info(f"Session {session_id} ended")
        
        try:
            await websocket.close()
        except:
            pass
```

### 2.2 Live Session Manager

**File:** `backend/app/services/live_session_manager.py`

```python
"""
Manages live analysis sessions with bounded queues and backpressure.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional
from collections import deque
import uuid

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Configuration
MAX_CONCURRENT_SESSIONS = 100
MAX_QUEUE_SIZE_PER_SESSION = 500  # ~10 seconds at 50 chunks/sec
CHUNK_TIMEOUT_SECONDS = 30

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
    user_id: int
    source_type: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Bounded queue
    audio_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=MAX_QUEUE_SIZE_PER_SESSION))
    
    # Processing state
    last_sequence: Optional[int] = None
    total_chunks_received: int = 0
    total_chunks_processed: int = 0
    is_processing: bool = False
    
    # Analysis state
    accumulated_audio: bytes = b''
    transcript_segments: list = field(default_factory=list)
    current_parameters: Optional[dict] = None
    current_risk_score: int = 0

class LiveSessionManager:
    """Manages all active live analysis sessions."""
    
    def __init__(self):
        self.sessions: Dict[str, LiveSession] = {}
        self.session_lock = asyncio.Lock()
    
    async def create_session(self, user_id: int, source_type: str) -> LiveSession:
        """Create a new live analysis session."""
        async with self.session_lock:
            if len(self.sessions) >= MAX_CONCURRENT_SESSIONS:
                raise ValueError(f"Maximum concurrent sessions ({MAX_CONCURRENT_SESSIONS}) reached")
            
            session_id = str(uuid.uuid4())
            session = LiveSession(
                session_id=session_id,
                user_id=user_id,
                source_type=source_type
            )
            
            self.sessions[session_id] = session
            logger.info(f"Created session {session_id} for user {user_id}")
            
            return session
    
    async def submit_audio_chunk(
        self,
        session_id: str,
        sequence_number: int,
        timestamp_ms: int,
        sample_rate: int,
        channel_count: int,
        audio_data: bytes
    ):
        """Submit an audio chunk to the session queue."""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Validate sequence
        if session.last_sequence is not None:
            if sequence_number <= session.last_sequence:
                logger.warning(f"Out-of-order chunk: {sequence_number} <= {session.last_sequence}")
                return  # Skip duplicate/old chunk
            
            if sequence_number > session.last_sequence + 1:
                logger.warning(
                    f"Missing chunks: jumped from {session.last_sequence} to {sequence_number}"
                )
        
        chunk = AudioChunkData(
            sequence_number=sequence_number,
            timestamp_ms=timestamp_ms,
            sample_rate=sample_rate,
            channel_count=channel_count,
            audio_data=audio_data
        )
        
        try:
            # Non-blocking put with timeout
            await asyncio.wait_for(
                session.audio_queue.put(chunk),
                timeout=0.1
            )
            session.last_sequence = sequence_number
            session.total_chunks_received += 1
        except asyncio.TimeoutError:
            logger.warning(f"Session {session_id} queue full, dropping chunk")
            # Backpressure: tell client to slow down via event
    
    async def process_session(self, session_id: str, websocket: WebSocket):
        """Process audio chunks for a session and send events."""
        session = self.sessions.get(session_id)
        if not session:
            return
        
        session.is_processing = True
        
        try:
            while True:
                try:
                    # Get chunk with timeout
                    chunk = await asyncio.wait_for(
                        session.audio_queue.get(),
                        timeout=CHUNK_TIMEOUT_SECONDS
                    )
                    
                    # Accumulate audio
                    session.accumulated_audio += chunk.audio_data
                    session.total_chunks_processed += 1
                    
                    # Process when we have enough audio (e.g., 1 second)
                    if len(session.accumulated_audio) >= chunk.sample_rate * 2:  # 1 sec of 16-bit PCM
                        await self._process_accumulated_audio(session, websocket)
                        
                except asyncio.TimeoutError:
                    logger.info(f"Session {session_id} timed out waiting for audio")
                    break
                except Exception as e:
                    logger.error(f"Error processing chunk: {e}", exc_info=True)
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Processing error: {str(e)[:100]}"
                    })
                    
        finally:
            session.is_processing = False
    
    async def _process_accumulated_audio(self, session: LiveSession, websocket: WebSocket):
        """Process accumulated audio: ASR → Evidence → Score → Events."""
        # TODO: Integration points for Phase 3
        
        # 1. Run incremental ASR
        # partial_transcript = await self._run_incremental_asr(session.accumulated_audio)
        
        # 2. Extract parameters
        # parameters = await self._extract_parameters(partial_transcript)
        
        # 3. Run voice anti-spoof (async)
        # voice_result = await self._analyze_voice(session.accumulated_audio)
        
        # 4. Calculate risk
        # risk_assessment = await self._calculate_risk(parameters)
        
        # 5. Send events
        await websocket.send_json({
            "type": "transcript_partial",
            "text": "TODO: actual transcript",
            "timestamp_ms": datetime.now(timezone.utc).timestamp() * 1000
        })
        
        # Clear accumulated audio after processing
        session.accumulated_audio = b''
    
    async def end_session(self, session_id: str):
        """End a session and cleanup resources."""
        async with self.session_lock:
            session = self.sessions.pop(session_id, None)
            if session:
                logger.info(
                    f"Ended session {session_id}: "
                    f"received={session.total_chunks_received}, "
                    f"processed={session.total_chunks_processed}"
                )
```

### 2.3 Android WebSocket Client

**File:** `android-app/app/src/main/java/com/vishwas/app/network/LiveAnalysisClient.kt`

```kotlin
/**
 * WebSocket client for real-time audio streaming.
 */
class LiveAnalysisClient(
    private val baseUrl: String,
    private val authToken: String
) {
    private var webSocket: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)  // No timeout for streaming
        .build()
    
    private val _events = MutableSharedFlow<LiveAnalysisEvent>()
    val events: SharedFlow<LiveAnalysisEvent> = _events.asSharedFlow()
    
    suspend fun connect(): Result<String> = suspendCancellableCoroutine { continuation ->
        val request = Request.Builder()
            .url("$baseUrl/live/ws/analyze?token=$authToken")
            .build()
        
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d(TAG, "WebSocket opened")
                // Send auth message
                val authMsg = JSONObject()
                    .put("type", "auth")
                    .put("token", authToken)
                    .put("source_type", "microphone")
                webSocket.send(authMsg.toString())
            }
            
            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = JSONObject(text)
                    val type = json.getString("type")
                    
                    when (type) {
                        "auth_ok" -> {
                            val sessionId = json.getString("session_id")
                            if (continuation.isActive) {
                                continuation.resume(Result.success(sessionId))
                            }
                        }
                        "transcript_partial" -> {
                            _events.tryEmit(LiveAnalysisEvent.TranscriptUpdate(
                                text = json.getString("text"),
                                isFinal = false
                            ))
                        }
                        "risk_update" -> {
                            _events.tryEmit(LiveAnalysisEvent.RiskUpdate(
                                score = json.getInt("score"),
                                level = json.getString("level")
                            ))
                        }
                        "warning" -> {
                            _events.tryEmit(LiveAnalysisEvent.Warning(
                                message = json.getString("message")
                            ))
                        }
                        "error" -> {
                            _events.tryEmit(LiveAnalysisEvent.Error(
                                message = json.getString("message")
                            ))
                        }
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Error parsing message", e)
                }
            }
            
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket failed", t)
                if (continuation.isActive) {
                    continuation.resume(Result.failure(t))
                }
                _events.tryEmit(LiveAnalysisEvent.Disconnected)
            }
            
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket closed: $reason")
                _events.tryEmit(LiveAnalysisEvent.Disconnected)
            }
        })
    }
    
    suspend fun sendAudioChunk(chunk: AudioChunk) {
        // Pack binary format: seq_num + timestamp + sample_rate + channels + encoding + data
        val buffer = ByteBuffer.allocate(16 + chunk.audioData.size)
            .order(ByteOrder.LITTLE_ENDIAN)
        
        buffer.putInt(chunk.sequenceNumber.toInt())
        buffer.putLong(chunk.timestampMs)
        buffer.putShort(chunk.sampleRate.toShort())
        buffer.put(chunk.channelCount.toByte())
        buffer.put(0) // encoding: PCM_16BIT
        buffer.put(chunk.audioData)
        
        webSocket?.send(ByteString.of(*buffer.array()))
    }
    
    fun disconnect() {
        webSocket?.close(1000, "Client disconnect")
        webSocket = null
    }
    
    companion object {
        private const val TAG = "LiveAnalysisClient"
    }
}

sealed class LiveAnalysisEvent {
    data class TranscriptUpdate(val text: String, val isFinal: Boolean) : LiveAnalysisEvent()
    data class RiskUpdate(val score: Int, val level: String) : LiveAnalysisEvent()
    data class Warning(val message: String) : LiveAnalysisEvent()
    data class Error(val message: String) : LiveAnalysisEvent()
    object Disconnected : LiveAnalysisEvent()
}
```

### Phase 2 Acceptance Criteria

- [ ] WebSocket endpoint accepts authenticated connections
- [ ] Binary audio chunks are received and queued
- [ ] Session ownership verified via JWT
- [ ] Bounded queues prevent memory overflow
- [ ] Backpressure handled gracefully
- [ ] Android client connects and sends test chunks
- [ ] Disconnect/reconnect works without leaks
- [ ] Session cleanup releases resources

---

## Phase 3: Incremental ASR, Parameters & AASIST

**Estimated Time:** 18-24 hours  
**Priority:** CRITICAL

### 3.1 Incremental ASR Integration

**Challenge:** faster-whisper doesn't natively support streaming. Options:

1. **Rolling window with overlap** (Recommended for MVP)
2. **faster-whisper-server** with streaming API
3. **Alternative streaming ASR** (e.g., Vosk, Whisper.cpp streaming fork)

**Approach: Rolling Window**

**File:** `backend/app/audio/incremental_asr.py`

```python
"""
Incremental ASR using rolling window approach.
"""
import logging
from dataclasses import dataclass
from typing import List, Optional
import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

@dataclass
class PartialTranscript:
    text: str
    start_time: float
    end_time: float
    is_final: bool
    confidence: Optional[float] = None

class IncrementalASR:
    """
    Incremental ASR using overlapping windows.
    
    Strategy:
    - Maintain rolling buffer of audio
    - Transcribe every N seconds with overlap
    - Detect and remove duplicate text
    - Mark segments as provisional or final
    """
    
    def __init__(
        self,
        model_size: str = "base",
        window_duration_sec: float = 10.0,
        overlap_duration_sec: float = 2.0,
        sample_rate: int = 16000
    ):
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        self.window_duration = window_duration_sec
        self.overlap_duration = overlap_duration_sec
        self.sample_rate = sample_rate
        
        # Rolling buffer
        self.audio_buffer: np.ndarray = np.array([], dtype=np.float32)
        self.buffer_start_time: float = 0.0
        
        # Transcript tracking
        self.last_transcript: str = ""
        self.finalized_segments: List[PartialTranscript] = []
    
    def add_audio(self, audio_chunk: bytes, timestamp_ms: int):
        """Add new audio chunk to rolling buffer."""
        # Convert bytes to float32 PCM
        audio_array = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Append to buffer
        self.audio_buffer = np.concatenate([self.audio_buffer, audio_array])
        
        # Trim buffer if too long (keep window + overlap)
        max_samples = int((self.window_duration + self.overlap_duration) * self.sample_rate)
        if len(self.audio_buffer) > max_samples:
            trim_amount = len(self.audio_buffer) - max_samples
            self.audio_buffer = self.audio_buffer[trim_amount:]
            self.buffer_start_time += trim_amount / self.sample_rate
    
    def transcribe_current_window(self) -> List[PartialTranscript]:
        """Transcribe current audio window."""
        if len(self.audio_buffer) < self.sample_rate:  # Less than 1 second
            return []
        
        # Run faster-whisper
        segments, info = self.model.transcribe(
            self.audio_buffer,
            language="en",
            beam_size=1,  # Fast decoding
            vad_filter=True
        )
        
        # Convert to partial transcripts
        results = []
        full_text = ""
        
        for segment in segments:
            partial = PartialTranscript(
                text=segment.text.strip(),
                start_time=self.buffer_start_time + segment.start,
                end_time=self.buffer_start_time + segment.end,
                is_final=False,  # Rolling window results are provisional
                confidence=segment.avg_logprob
            )
            results.append(partial)
            full_text += " " + partial.text
        
        # Detect new text (not in previous transcript)
        new_text = self._extract_new_text(full_text.strip())
        
        # Update last transcript
        self.last_transcript = full_text.strip()
        
        return results
    
    def _extract_new_text(self, current_text: str) -> str:
        """Extract only the new portion of text not in last transcript."""
        if not self.last_transcript:
            return current_text
        
        # Simple approach: find where they diverge
        # More sophisticated: use difflib or edit distance
        if current_text.startswith(self.last_transcript):
            return current_text[len(self.last_transcript):].strip()
        
        return current_text
    
    def finalize_segments(self) -> List[PartialTranscript]:
        """Mark segments as final when sufficient time has passed."""
        # Simple heuristic: segments older than window duration are final
        cutoff_time = self.buffer_start_time
        
        for segment in self.finalized_segments:
            if segment.end_time < cutoff_time and not segment.is_final:
                segment.is_final = True
        
        return [s for s in self.finalized_segments if s.is_final]
```

### 3.2 Streaming Evidence Extraction Integration

**File:** `backend/app/services/live_session_manager.py` (additions)

```python
async def _process_accumulated_audio(self, session: LiveSession, websocket: WebSocket):
    """Process accumulated audio: ASR → Evidence → Score → Events."""
    from app.audio.incremental_asr import IncrementalASR
    from app.extractors import extract_evidence_streaming
    from app.schemas.report import TranscriptSegment
    
    # Initialize ASR if needed
    if not hasattr(session, 'asr'):
        session.asr = IncrementalASR()
    
    # Add audio to ASR
    session.asr.add_audio(session.accumulated_audio, timestamp_ms=int(datetime.now(timezone.utc).timestamp() * 1000))
    
    # Get partial transcripts
    partial_transcripts = session.asr.transcribe_current_window()
    
    if partial_transcripts:
        # Convert to TranscriptSegment
        new_segments = [
            TranscriptSegment(
                start=pt.start_time,
                end=pt.end_time,
                text=pt.text,
                language="en",
                speaker="spk_0",  # TODO: Speaker diarization
                is_final=pt.is_final,
                confidence=pt.confidence
            )
            for pt in partial_transcripts
        ]
        
        session.transcript_segments.extend(new_segments)
        
        # Extract evidence using streaming mode
        if not hasattr(session, 'classifier'):
            from app.extractors.tier1_classifier import Tier1Classifier
            session.classifier = Tier1Classifier()
        
        evidence_result = extract_evidence_streaming(
            segments=new_segments,
            call_id=session.session_id,
            classifier=session.classifier
        )
        
        # Send transcript event
        await websocket.send_json({
            "type": "transcript_partial",
            "segments": [
                {
                    "text": seg.text,
                    "start": seg.start,
                    "end": seg.end,
                    "is_final": seg.is_final
                }
                for seg in new_segments
            ]
        })
        
        # If critical signals detected, send warning
        if evidence_result.has_critical_signal:
            await websocket.send_json({
                "type": "warning",
                "message": "Critical fraud signal detected",
                "signals": [
                    {
                        "type": sig.signal,
                        "severity": sig.severity,
                        "text": sig.evidence_text[:100]
                    }
                    for sig in evidence_result.signals
                ]
            })
    
    # Clear accumulated audio
    session.accumulated_audio = b''
```

### 3.3 AASIST Anti-Spoof Integration

**File:** `backend/app/audio/aasist_streaming.py`

```python
"""
AASIST anti-spoof analysis for streaming audio.
"""
import asyncio
import logging
from typing import Optional
import numpy as np
import torch

logger = logging.getLogger(__name__)

class AASISTStreamingAnalyzer:
    """
    AASIST anti-spoof analysis for live audio.
    
    Runs inference asynchronously to avoid blocking transcript updates.
    """
    
    def __init__(self, model_path: str, device: str = "cpu"):
        self.device = torch.device(device)
        # Load AASIST model
        # self.model = torch.load(model_path)
        # self.model.eval()
        
        # Configuration
        self.sample_rate = 16000
        self.min_window_duration = 4.0  # seconds
        self.inference_interval = 5.0    # Run inference every 5 seconds
        
        self.last_inference_time = 0.0
    
    async def analyze_window(
        self,
        audio_data: np.ndarray,
        current_time: float
    ) -> Optional[dict]:
        """
        Analyze audio window for spoof detection.
        
        Returns None if insufficient audio or too soon since last inference.
        """
        # Check if enough time has passed
        if current_time - self.last_inference_time < self.inference_interval:
            return None
        
        # Check if enough audio
        if len(audio_data) < self.sample_rate * self.min_window_duration:
            return None
        
        # Run inference in thread pool to avoid blocking
        result = await asyncio.to_thread(self._run_inference, audio_data)
        
        self.last_inference_time = current_time
        
        return result
    
    def _run_inference(self, audio_data: np.ndarray) -> dict:
        """Run AASIST inference (synchronous)."""
        try:
            # Prepare input
            # audio_tensor = torch.from_numpy(audio_data).float().to(self.device)
            
            # Run model
            # with torch.no_grad():
            #     output = self.model(audio_tensor)
            #     spoof_prob = torch.sigmoid(output).item()
            
            # PLACEHOLDER
            spoof_prob = 0.15  # Mock value
            
            return {
                "spoof_probability": spoof_prob,
                "model": "AASIST",
                "version": "1.0",
                "windows_analyzed": 1,
                "analysis_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"AASIST inference failed: {e}", exc_info=True)
            return {
                "error": str(e),
                "model": "AASIST",
                "analysis_timestamp": datetime.now(timezone.utc).isoformat()
            }
```

### Phase 3 Acceptance Criteria

- [ ] Incremental ASR produces partial transcripts
- [ ] Duplicate text from overlapping windows is removed
- [ ] `extract_evidence_streaming()` detects critical signals in real-time
- [ ] AASIST runs asynchronously without blocking transcript updates
- [ ] Voice spoof results have correct semantics and timestamps
- [ ] Memory usage remains bounded during long sessions
- [ ] Transcript updates visible in Android app within 2-3 seconds

---

## Phase 4: Live Dashboard & Trust Judge

**Estimated Time:** 12-16 hours  
**Priority:** HIGH

### 4.1 React Live Analysis Page

**File:** `vishwas-frontend/src/pages/LiveAnalysisPage.tsx`

```typescript
/**
 * Real-time analysis dashboard
 */
import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';

interface TranscriptSegment {
  text: string;
  start: number;
  end: number;
  is_final: boolean;
}

interface RiskUpdate {
  score: number;
  level: string;
  category_scores?: {
    identity: number;
    request: number;
    behavior: number;
    channel: number;
    voice: number;
  };
}

export function LiveAnalysisPage() {
  const { token } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<TranscriptSegment[]>([]);
  const [riskScore, setRiskScore] = useState<number>(0);
  const [riskLevel, setRiskLevel] = useState<string>('LOW');
  const [warnings, setWarnings] = useState<string[]>([]);
  const [voiceStatus, setVoiceStatus] = useState<string>('unavailable');
  
  const wsRef = useRef<WebSocket | null>(null);
  
  const connect = () => {
    const wsUrl = `ws://localhost:8001/live/ws/analyze?token=${token}`;
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log('WebSocket connected');
      // Send auth
      ws.send(JSON.stringify({
        type: 'auth',
        token: token,
        source_type: 'microphone'
      }));
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'auth_ok':
          setSessionId(data.session_id);
          setIsConnected(true);
          setIsAnalyzing(true);
          break;
          
        case 'transcript_partial':
          if (data.segments) {
            setTranscript(prev => [...prev, ...data.segments]);
          }
          break;
          
        case 'risk_update':
          setRiskScore(data.score);
          setRiskLevel(data.level);
          break;
          
        case 'warning':
          setWarnings(prev => [...prev, data.message]);
          break;
          
        case 'voice_update':
          setVoiceStatus(data.status);
          break;
          
        case 'error':
          console.error('Server error:', data.message);
          setWarnings(prev => [...prev, `Error: ${data.message}`]);
          break;
      }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };
    
    ws.onclose = () => {
      console.log('WebSocket closed');
      setIsConnected(false);
      setIsAnalyzing(false);
    };
    
    wsRef.current = ws;
  };
  
  const disconnect = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  };
  
  const getRiskColor = (level: string) => {
    switch (level) {
      case 'CRITICAL': return 'red';
      case 'HIGH': return 'orange';
      case 'MEDIUM': return 'yellow';
      default: return 'green';
    }
  };
  
  return (
    <div className="live-analysis-page">
      <h1>Live Scam Analysis</h1>
      
      {/* Connection controls */}
      <div className="controls">
        {!isAnalyzing ? (
          <button onClick={connect} className="btn-primary">
            Start Live Analysis
          </button>
        ) : (
          <button onClick={disconnect} className="btn-danger">
            Stop Analysis
          </button>
        )}
        
        <div className="status">
          Status: {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
          {sessionId && <span> | Session: {sessionId.slice(0, 8)}</span>}
        </div>
      </div>
      
      {/* Live transcript */}
      <div className="transcript-panel">
        <h2>Live Transcript</h2>
        <div className="transcript-content">
          {transcript.map((seg, idx) => (
            <p key={idx} className={seg.is_final ? 'final' : 'provisional'}>
              <span className="timestamp">[{seg.start.toFixed(1)}s]</span>
              {' '}
              {seg.text}
              {!seg.is_final && <span className="provisional-indicator"> ⏳</span>}
            </p>
          ))}
        </div>
      </div>
      
      {/* Risk score */}
      <div className="risk-panel">
        <h2>Risk Assessment</h2>
        <div className="risk-score" style={{ borderColor: getRiskColor(riskLevel) }}>
          <div className="score-value">{riskScore}</div>
          <div className="score-level" style={{ color: getRiskColor(riskLevel) }}>
            {riskLevel}
          </div>
        </div>
        
        <div className="voice-status">
          Voice Analysis: {voiceStatus}
        </div>
      </div>
      
      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="warnings-panel">
          <h2>⚠️ Warnings</h2>
          {warnings.map((warning, idx) => (
            <div key={idx} className="warning-item">
              {warning}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

### 4.2 Trust Judge Integration

**File:** `backend/app/services/live_session_manager.py` (additions)

```python
async def _calculate_risk_from_session(self, session: LiveSession) -> dict:
    """Calculate risk score from current session state."""
    from app.trust_engine.judge import TrustJudge
    from app.trust_engine.trust_graph import TrustGraph
    from app.adapters.evidence_to_parameters import convert_evidence_to_parameters
    
    # Get database session
    from app.database.session import SessionLocal
    db = SessionLocal()
    
    try:
        # Convert accumulated evidence to parameters
        # (This requires full evidence extraction, not just signals)
        from app.extractors import extract_evidence_from_transcript
        from app.schemas.report import TranscriptResponse
        
        transcript = TranscriptResponse(
            call_id=session.session_id,
            language="en",
            transcription_status="streaming",
            segments=session.transcript_segments,
            is_mock=False
        )
        
        evidence = extract_evidence_from_transcript(transcript, session.session_id)
        
        # Get Trust Judge assessment
        trust_graph = TrustGraph(db)
        judge = TrustJudge()
        
        assessment = judge.evaluate(
            call_id=session.session_id,
            evidence=evidence,
            trust_graph=trust_graph,
            caller_number=None
        )
        
        return {
            "score": assessment.score,
            "level": assessment.risk_level,
            "category_scores": assessment.category_scores,
            "reasons": assessment.reasons,
            "fired_rules": assessment.fired_rules,
            "verification": assessment.verification_details
        }
        
    finally:
        db.close()
```

### Phase 4 Acceptance Criteria

- [ ] React dashboard displays live transcript
- [ ] Risk score updates without page refresh
- [ ] Provisional vs final segments visually distinguished
- [ ] Warnings appear in real-time
- [ ] Deterministic Trust Judge reused (no duplicate scoring)
- [ ] Category breakdown matches existing batch analysis
- [ ] Risk floors apply correctly (OTP + unverified → 75 CRITICAL)
- [ ] Final report matches live analysis state

---

## Phase 5: Testing, Security & Documentation

**Estimated Time:** 16-20 hours  
**Priority:** HIGH

### 5.1 Integration Tests

**File:** `backend/tests/test_live_analysis_integration.py`

```python
"""
Integration tests for live analysis.
"""
import pytest
import asyncio
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket

@pytest.mark.asyncio
async def test_websocket_connection_requires_auth():
    """Unauthenticated connection should be rejected."""
    # TODO: Implement

@pytest.mark.asyncio
async def test_audio_chunk_sequence_validation():
    """Out-of-order chunks should be handled."""
    # TODO: Implement

@pytest.mark.asyncio
async def test_session_queue_backpressure():
    """Full queue should trigger backpressure."""
    # TODO: Implement

@pytest.mark.asyncio
async def test_transcript_deduplication():
    """Overlapping windows should not duplicate text."""
    # TODO: Implement

@pytest.mark.asyncio
async def test_risk_floor_otp_unverified():
    """OTP request on unverified channel → 75 CRITICAL."""
    # TODO: Implement

@pytest.mark.asyncio
async def test_voice_analysis_async():
    """Voice analysis should not block transcript updates."""
    # TODO: Implement
```

### 5.2 Android Tests

**File:** `android-app/app/src/androidTest/java/com/vishwas/app/MicrophoneAdapterTest.kt`

```kotlin
@RunWith(AndroidJUnit4::class)
class MicrophoneAdapterTest {
    
    @Test
    fun testMicrophonePermissionRequest() {
        // TODO: Test permission flow
    }
    
    @Test
    fun testAudioChunkGeneration() {
        // TODO: Verify chunk format
    }
    
    @Test
    fun testSessionCleanup() {
        // TODO: Verify resource cleanup
    }
}
```

### 5.3 Performance Benchmarks

**File:** `backend/tests/benchmark_live_analysis.py`

```python
"""
Performance benchmarks for live analysis.
"""
import pytest
import time
import numpy as np

def test_asr_latency():
    """Measure ASR processing latency."""
    # Target: < 500ms for 1 second of audio
    pass

def test_parameter_extraction_latency():
    """Measure evidence extraction latency."""
    # Target: < 100ms per segment
    pass

def test_trust_judge_latency():
    """Measure Trust Judge evaluation latency."""
    # Target: < 50ms
    pass

def test_voice_inference_latency():
    """Measure AASIST inference latency."""
    # Target: < 1000ms for 4-second window
    pass

def test_concurrent_session_capacity():
    """Measure maximum concurrent sessions."""
    # Target: 50 sessions on 4-core CPU
    pass
```

### 5.4 Security Audit

**Checklist:**

- [ ] JWT authentication on WebSocket endpoint
- [ ] Session ownership verified for every operation
- [ ] Rate limiting on session creation
- [ ] Maximum concurrent sessions enforced
- [ ] Bounded queue sizes prevent DoS
- [ ] PII masking before any external service
- [ ] Audio data not logged
- [ ] Temporary audio cleaned up
- [ ] User can terminate session anytime
- [ ] No cross-user session access

### 5.5 Implementation Report

**File:** `REALTIME_DUAL_SOURCE_IMPLEMENTATION_REPORT.md`

```markdown
# Real-Time Dual-Source Implementation Report

## Status

### Phase 1: Android Audio Sources ✅
- Microphone adapter: IMPLEMENTED
- WebRTC adapter: INTERFACE_DEFINED
- Cellular adapter: CAPABILITY_CHECK_ONLY

### Phase 2: WebSocket Transport ✅
- Backend endpoint: IMPLEMENTED
- Session manager: IMPLEMENTED
- Android client: IMPLEMENTED

### Phase 3: ASR & Parameters ✅
- Incremental ASR: IMPLEMENTED (rolling window)
- Streaming evidence extraction: INTEGRATED
- AASIST integration: ASYNC_IMPLEMENTATION

### Phase 4: Live Dashboard ✅
- React WebSocket client: IMPLEMENTED
- Real-time UI: IMPLEMENTED
- Trust Judge integration: VERIFIED

### Phase 5: Testing & Security ⏳
- Unit tests: IN_PROGRESS
- Integration tests: IN_PROGRESS
- Security audit: PENDING

## Measured Performance

- ASR latency: TBD
- Parameter extraction: TBD
- End-to-end warning latency: TBD

## Known Limitations

1. Cellular audio requires privileged system integration
2. faster-whisper rolling window has ~2s latency
3. AASIST requires 4-second windows
4. No speaker diarization yet

## Next Steps

1. Complete security audit
2. Performance optimization
3. Cellular adapter implementation on authorized platform
4. Voice model evaluation on held-out data
```

### Phase 5 Acceptance Criteria

- [ ] 50+ automated tests passing
- [ ] Security audit checklist complete
- [ ] Performance benchmarks measured and documented
- [ ] Physical device testing completed
- [ ] Implementation report accurate and honest
- [ ] Known limitations clearly documented

---

## Critical Cellular Audio Constraint

### Android Security Model

**Standard third-party apps CANNOT:**
- Access both sides of cellular calls
- Read call audio from default phone app
- Use `CallScreeningService` for raw audio
- Bypass telephony security via root alone

**Required for cellular audio:**
1. **Platform signature** (`android:sharedUserId="android.uid.system"`)
2. **System app installation** in `/system/priv-app/`
3. **Custom AOSP build** with telephony hooks, OR
4. **OEM-provided API** with vendor authorization

### Implementation Strategy

**Development Phase:**
- Implement interface and capability checks
- Build and test with microphone/WebRTC
- Document cellular requirements

**Production Phase (Device-Specific):**
- Partner with OEM for privileged API access, OR
- Build custom AOSP with telephony integration, OR
- Deploy as system app with platform signature

**Do NOT:**
- Claim cellular support without verification
- Fake cellular audio with microphone
- Bypass security without authorization
- Deploy to Play Store claiming cellular access

---

## Success Metrics

### Functional Requirements
- [ ] Android app streams audio continuously
- [ ] Backend receives and processes chunks in order
- [ ] Partial transcripts update within 2-3 seconds
- [ ] Critical warnings (OTP request) trigger immediately
- [ ] Risk score matches deterministic rules
- [ ] Final report consistent with live state

### Performance Requirements
- [ ] ASR latency < 2 seconds
- [ ] Risk update latency < 500ms after transcript
- [ ] Memory usage < 500MB per session
- [ ] Support 10+ concurrent sessions
- [ ] No memory leaks in 1-hour session

### Security Requirements
- [ ] Authentication required for all operations
- [ ] Session ownership enforced
- [ ] PII protected in transit and storage
- [ ] Explicit user consent for recording
- [ ] User can terminate anytime

---

## Timeline Estimate

| Phase | Time | Priority | Blocking? |
|---|---:|---|---|
| 1. Android Audio Sources | 12-16h | CRITICAL | No |
| 2. WebSocket Transport | 14-18h | CRITICAL | Yes (blocks 3) |
| 3. ASR & Parameters | 18-24h | CRITICAL | Yes (blocks 4) |
| 4. Live Dashboard | 12-16h | HIGH | No (parallel with 5) |
| 5. Testing & Security | 16-20h | HIGH | No |
| **Total** | **72-94h** | | |

**Recommended Approach:**
- 2-week sprint for Phases 1-3
- 1-week sprint for Phases 4-5
- Additional time for cellular integration on authorized platform

---

## Conclusion

This specification provides a complete roadmap for adding real-time fraud analysis to VISHWAS. The implementation preserves existing batch analysis, reuses the deterministic Trust Judge, and integrates with current security infrastructure.

**Key Decisions:**
- Rolling window ASR (faster-whisper compatible)
- Reuse existing parameter extraction and Trust Judge
- WebSocket transport with bounded queues
- Cellular audio requires explicit platform authorization

**Ready for Implementation:** Yes, with clear acceptance criteria for each phase.

---

**Document Version:** 1.0  
**Created:** October 14, 2026  
**Author:** Kiro AI  
**Status:** SPECIFICATION - READY FOR IMPLEMENTATION
