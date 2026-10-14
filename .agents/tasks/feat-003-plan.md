# FEAT-003: Android Real-Time Voice Detection Implementation Plan

## Overview
Implement streaming voice detection in the Android app matching the completed React frontend functionality. Backend streaming API is live and verified working. This plan follows existing Android app patterns discovered during codebase exploration.

## Architecture Decisions

**Threading Model**: AudioRecord runs on a dedicated background thread. Audio chunks are emitted via Kotlin Flow to the ViewModel, which handles coroutine-based network calls. This prevents blocking the UI thread and matches Android best practices.

**Audio Configuration**: AudioRecord with 16kHz sample rate, CHANNEL_IN_MONO, ENCODING_PCM_16BIT. Buffer size calculated as `AudioRecord.getMinBufferSize() * 2` for smooth capture. Chunk size is 48000 bytes to exactly match backend expectations (~1.5 seconds at 16kHz mono PCM_16BIT).

**Session Lifecycle**: Start session → capture audio in background thread → send 48000-byte chunks via ViewModel → display live results → cleanup on stop (release AudioRecord, cancel coroutines, delete backend session). Session expiry (30 min TTL) is handled with 404 error detection.

**State Management**: Sealed class `StreamingVoiceState` with states: Idle, RequestingPermission, Listening, Analyzing, Complete, Error(message). ViewModel exposes StateFlow for Compose UI to observe.

**UI Design**: Match existing app patterns from HomeScreen.kt and RecordScreen.kt. Material Design 3 components, Cards for status display, circular progress indicator for spoof probability gauge (0-100%), waveform visualization using Canvas composable, status badges matching color scheme.

**API Integration**: Extend VishwasApiService with three new endpoints matching backend contract. All use existing JWT authentication from RetrofitClient. Paths are `/api/v1/voice-detection/stream/start`, `/api/v1/voice-detection/stream/{sessionId}/chunk`, `/api/v1/voice-detection/stream/{sessionId}` (DELETE).

---

## Implementation Plan

- [ ] 1. Create StreamingVoiceModels.kt with API response data classes
      - Path: `c:/Users/Vaishnavi/Desktop/Vishwas Kiro/VISHWAS/android-app/app/src/main/java/com/vishwas/app/models/StreamingVoiceModels.kt`
      - Add `StreamSessionResponse` with fields: `sessionId: String`, `status: String`, `chunkSizeBytes: Int`, `format: String`, `maxDurationMinutes: Int`, `ttlMinutes: Int`
      - Add `StreamChunkResponse` with fields: `status: String`, `label: String`, `spoofProb: Double?`, `confidence: String`, `durationAnalyzedMs: Int`, `chunksProcessed: Int`
      - Add `StreamDeleteResponse` with fields: `sessionId: String`, `status: String`, `message: String`
      - Use `@SerializedName` for snake_case backend fields (e.g., `@SerializedName("session_id") val sessionId: String`, `@SerializedName("spoof_prob") val spoofProb: Double?`, `@SerializedName("chunks_processed") val chunksProcessed: Int`)
      - Follow existing pattern in ApiModels.kt (same package, same annotation style)
      - **Verify**: File compiles without errors: `cd c:/Users/Vaishnavi/Desktop/Vishwas\ Kiro/VISHWAS/android-app && .\gradlew.bat compileDebugKotlin`

- [ ] 2. Extend VishwasApiService.kt with streaming voice detection endpoints
      - Path: `c:/Users/Vaishnavi/Desktop/Vishwas Kiro/VISHWAS/android-app/app/src/main/java/com/vishwas/app/network/VishwasApiService.kt`
      - Add `@POST("voice-detection/stream/start") suspend fun startVoiceStream(): Response<StreamSessionResponse>`
      - Add `@Multipart @POST("voice-detection/stream/{sessionId}/chunk") suspend fun sendVoiceChunk(@Path("sessionId") sessionId: String, @Part chunk: MultipartBody.Part): Response<StreamChunkResponse>`
      - Add `@DELETE("voice-detection/stream/{sessionId}") suspend fun deleteVoiceStream(@Path("sessionId") sessionId: String): Response<StreamDeleteResponse>`
      - All endpoints return `Response<T>` for manual status code handling (404 session expiry detection)
      - JWT authentication is automatic via existing RetrofitClient OkHttp interceptor
      - **Verify**: File compiles without errors: `cd c:/Users/Vaishnavi/Desktop/Vishwas\ Kiro/VISHWAS/android-app && .\gradlew.bat compileDebugKotlin`

- [ ] 3. Update VishwasViewModel.kt with streaming voice detection state and functions
      - Path: `c:/Users/Vaishnavi/Desktop/Vishwas Kiro/VISHWAS/android-app/app/src/main/java/com/vishwas/app/viewmodel/VishwasViewModel.kt`
      - Add sealed class `StreamingVoiceState` with: `Idle`, `RequestingPermission`, `Listening(sessionId: String, spoofProb: Double?, confidence: String, chunksProcessed: Int)`, `Analyzing(sessionId: String, spoofProb: Double, confidence: String, chunksProcessed: Int)`, `Complete(spoofProb: Double, confidence: String, totalChunks: Int)`, `Error(message: String)`
      - Add private `_streamingVoiceState = MutableStateFlow<StreamingVoiceState>(StreamingVoiceState.Idle)`
      - Add public `val streamingVoiceState: StateFlow<StreamingVoiceState> = _streamingVoiceState.asStateFlow()`
      - Add `suspend fun startVoiceStreaming(): Result<String>` that calls `repository.startVoiceStream()`, updates state to Listening on success, returns session_id or error
      - Add `suspend fun sendAudioChunk(sessionId: String, chunkBytes: ByteArray): Result<StreamChunkResponse>` that wraps bytes in MultipartBody.Part, calls `repository.sendVoiceChunk()`, updates state based on response label ("insufficient_data" → Listening, "uncertain"/"human"/"ai_generated" → Analyzing)
      - Add `suspend fun stopVoiceStreaming(sessionId: String)` that calls `repository.deleteVoiceStream()` and resets state to Idle
      - Handle 404 responses as session expiry (update state to Error("Session expired - please restart"))
      - Follow existing pattern: use `viewModelScope.launch` for async operations, emit state updates to `_streamingVoiceState.value`, log errors with TAG
      - **Verify**: File compiles without errors: `cd c:/Users/Vaishnavi/Desktop/Vishwas\ Kiro/VISHWAS/android-app && .\gradlew.bat compileDebugKotlin`

- [ ] 4. Extend VishwasRepository.kt with streaming voice detection methods
      - Path: `c:/Users/Vaishnavi/Desktop/Vishwas Kiro/VISHWAS/android-app/app/src/main/java/com/vishwas/app/data/VishwasRepository.kt`
      - Add `suspend fun startVoiceStream(): Result<StreamSessionResponse> = withContext(Dispatchers.IO) { ... }` that calls `api.startVoiceStream()`, returns success/failure Result
      - Add `suspend fun sendVoiceChunk(sessionId: String, chunkBytes: ByteArray): Result<StreamChunkResponse> = withContext(Dispatchers.IO) { ... }` that wraps chunkBytes in `MultipartBody.Part.createFormData("chunk", "audio.raw", requestBody)`, calls `api.sendVoiceChunk()`, handles 404 as session expiry error
      - Add `suspend fun deleteVoiceStream(sessionId: String): Result<StreamDeleteResponse> = withContext(Dispatchers.IO) { ... }` that calls `api.deleteVoiceStream()`, returns success/failure Result
      - Follow existing pattern: wrap in try-catch, log errors with TAG, check `response.isSuccessful`, handle 404/503 status codes explicitly
      - **Verify**: File compiles without errors: `cd c:/Users/Vaishnavi/Desktop/Vishwas\ Kiro/VISHWAS/android-app && .\gradlew.bat compileDebugKotlin`

- [ ] 5. Create StreamingVoiceDetectionScreen.kt Compose UI with microphone capture
      - Path: `c:/Users/Vaishnavi/Desktop/Vishwas Kiro/VISHWAS/android-app/app/src/main/java/com/vishwas/app/ui/screens/StreamingVoiceDetectionScreen.kt`
      - **Signature**: `@OptIn(ExperimentalMaterial3Api::class) @Composable fun StreamingVoiceDetectionScreen(viewModel: VishwasViewModel, onNavigateBack: () -> Unit)`
      - **Layout**: Scaffold with TopAppBar (title "Live Voice Detection", back button), Column content with Cards for status display, circular progress indicator for spoof probability gauge, waveform Canvas, Start/Stop buttons
      - **Permission Handling**: Check RECORD_AUDIO permission with `ContextCompat.checkSelfPermission`, request with `rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission())`, show permission prompt UI if denied (match RecordScreen.kt pattern)
      - **Audio Capture Threading**: 
        - AudioRecord config: `AudioRecord(MediaRecorder.AudioSource.MIC, 16000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, bufferSize)` where `bufferSize = AudioRecord.getMinBufferSize(16000, CHANNEL_IN_MONO, ENCODING_PCM_16BIT) * 2`
        - Launch coroutine in `LaunchedEffect(recordingActive)` with `Dispatchers.Default` context
        - Read audio in loop: `audioRecord.read(buffer, 0, CHUNK_SIZE_BYTES)`, accumulate exactly 48000 bytes, call `viewModel.sendAudioChunk(sessionId, chunk)`, repeat
        - On stop: call `audioRecord.stop()`, `audioRecord.release()`, `viewModel.stopVoiceStreaming(sessionId)`
      - **Waveform Visualization**: Canvas composable drawing real-time waveform from last captured PCM buffer (convert Int16 to Float normalized to [-1, 1], draw line path), match React frontend blue/slate color scheme
      - **Spoof Probability Gauge**: CircularProgressIndicator with `progress = spoofProb.toFloat()` (0.0-1.0 range), display percentage inside circle, color gradient green→yellow→red based on probability, show confidence level text ("low"/"medium"/"high") below gauge
      - **Status Indicators**: Card components with icons and text: "Listening..." (blue, mic icon), "Analyzing..." (yellow, activity icon), "Complete" (green, check icon), "Error: {message}" (red, alert icon), match existing app color scheme
      - **Error Handling**: Observe `viewModel.streamingVoiceState`, display Error state messages in red Card, handle mic permission denied, network failures, session expiry (404), show "Retry" button on error
      - **Cleanup**: `DisposableEffect(Unit) { onDispose { /* stop recording, release AudioRecord, cancel session */ } }` to prevent resource leaks
      - Follow existing patterns: Material Design 3 components, MaterialTheme.colorScheme colors, Icons from Icons.Default, same padding/spacing as HomeScreen.kt and RecordScreen.kt
      - **Verify**: Build succeeds: `cd c:/Users/Vaishnavi/Desktop/Vishwas\ Kiro/VISHWAS/android-app && .\gradlew.bat assembleDebug`

- [ ] 6. Update Navigation.kt to add voice detection route
      - Path: `c:/Users/Vaishnavi/Desktop/Vishwas Kiro/VISHWAS/android-app/app/src/main/java/com/vishwas/app/ui/Navigation.kt`
      - Add `const val VOICE_DETECTION = "voice-detection"` to Routes object
      - Add `composable(Routes.VOICE_DETECTION) { StreamingVoiceDetectionScreen(viewModel = viewModel, onNavigateBack = { navController.popBackStack() }) }` to NavHost
      - Add navigation drawer item: `NavItem(Routes.VOICE_DETECTION, "Live Voice Detection", Icons.Default.MicVocal)` to navItems list (insert after RECORD item)
      - Import `com.vishwas.app.ui.screens.StreamingVoiceDetectionScreen`
      - **Verify**: Build succeeds: `cd c:/Users/Vaishnavi/Desktop/Vishwas\ Kiro/VISHWAS/android-app && .\gradlew.bat assembleDebug`

- [ ] 7. Verify AndroidManifest.xml has RECORD_AUDIO permission (already present, confirm only)
      - Path: `c:/Users/Vaishnavi/Desktop/Vishwas Kiro/VISHWAS/android-app/app/src/main/AndroidManifest.xml`
      - Confirm line exists: `<uses-permission android:name="android.permission.RECORD_AUDIO" />`
      - No changes needed (permission already declared for RecordScreen)
      - **Verify**: Read file and confirm permission is present

- [ ] 8. Build and install app on emulator/device for end-to-end verification
      - Build debug APK: `cd c:/Users/Vaishnavi/Desktop/Vishwas\ Kiro/VISHWAS/android-app && .\gradlew.bat assembleDebug`
      - Install on device/emulator: `.\gradlew.bat installDebug`
      - **Manual Test Steps**:
        1. Start backend server (port 8000) if not running
        2. Launch Android app on emulator (backend accessible at 10.0.2.2:8000)
        3. Login with test user: Shubham21@gmail.com / Shubham
        4. Navigate to "Live Voice Detection" from drawer menu
        5. Grant microphone permission if prompted
        6. Tap "Start Detection" button
        7. Speak continuously for 5-10 seconds (vary pitch/tone)
        8. Observe: waveform animates, spoof probability updates every ~1.5s, confidence level progresses from "insufficient_data" → "low" → "medium" → "high"
        9. Tap "Stop Detection" button
        10. Check Logcat for no errors: `adb logcat | grep -E "(VishwasViewModel|StreamingVoice)"`
      - **Expected Results**: 
        - Waveform displays live audio visualization
        - Spoof probability gauge updates smoothly (EMA smoothing visible)
        - Confidence level increases with more audio processed
        - Status transitions: Listening → Analyzing → Complete
        - No crashes, no AudioRecord errors, no 404/503 API errors
      - **Verify**: All manual test steps pass without errors

---

## Technical Details

### AudioRecord Configuration
```kotlin
val sampleRate = 16000
val channelConfig = AudioFormat.CHANNEL_IN_MONO
val audioFormat = AudioFormat.ENCODING_PCM_16BIT
val minBufferSize = AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat)
val bufferSize = minBufferSize * 2 // Double for smooth capture

val audioRecord = AudioRecord(
    MediaRecorder.AudioSource.MIC,
    sampleRate,
    channelConfig,
    audioFormat,
    bufferSize
)
```

### Chunking Logic
```kotlin
val CHUNK_SIZE_BYTES = 48000 // Matches backend expectation
val buffer = ByteArray(bufferSize)

while (isRecording) {
    val bytesRead = audioRecord.read(buffer, 0, buffer.size)
    if (bytesRead > 0) {
        accumulateBytes(buffer, bytesRead)
        if (accumulated.size >= CHUNK_SIZE_BYTES) {
            val chunk = accumulated.copyOfRange(0, CHUNK_SIZE_BYTES)
            viewModel.sendAudioChunk(sessionId, chunk)
            accumulated = accumulated.copyOfRange(CHUNK_SIZE_BYTES, accumulated.size)
        }
    }
}
```

### Backend API Response Examples
```json
// POST /voice-detection/stream/start
{
  "session_id": "abc123",
  "status": "ready",
  "chunk_size_bytes": 48000,
  "format": "wav_16khz_mono",
  "max_duration_minutes": 5,
  "ttl_minutes": 30
}

// POST /voice-detection/stream/{sessionId}/chunk
{
  "status": "processing",
  "label": "uncertain",
  "spoof_prob": 0.67,
  "confidence": "medium",
  "duration_analyzed_ms": 4500,
  "chunks_processed": 3
}

// DELETE /voice-detection/stream/{sessionId}
{
  "session_id": "abc123",
  "status": "deleted",
  "message": "Session deleted successfully"
}
```

### Error Handling Scenarios
- **404 on chunk upload**: Session expired (30 min TTL) → show "Session expired - please restart" error
- **503 on chunk upload**: Voice detection model unavailable → show "Voice detection unavailable" error
- **Permission denied**: User denied RECORD_AUDIO → show "Microphone permission required" with retry button
- **Network failure**: Backend unreachable → show "Network error - check backend connection"
- **AudioRecord init failure**: Device microphone unavailable → show "Microphone unavailable"

### UI/UX Design Notes
- Match existing app theme: Material Design 3, MaterialTheme.colorScheme colors
- Status badge colors: Listening (blue), Analyzing (yellow), Complete (green), Error (red)
- Circular gauge: 0-30% green, 30-60% yellow, 60-100% red (spoof probability)
- Waveform: blue when recording, gray when idle, matches React frontend styling
- Layout: Top status card → spoof probability gauge → waveform canvas → control buttons (Start/Stop)
- Spacing: 16.dp padding, 16.dp arrangement spacing, match HomeScreen.kt and RecordScreen.kt

---

## Dependencies
No new dependencies required. All functionality uses existing Android SDK and Retrofit/OkHttp libraries already in the project.

---

## Notes
- Backend streaming API is live and tested (FEAT-001 complete)
- React frontend implementation is reference for UI/UX (FEAT-002 complete)
- Android emulator uses 10.0.2.2:8000 to reach localhost backend
- Test user credentials: Shubham21@gmail.com / Shubham
- Session TTL is 30 minutes on backend (enforced)
- Partial chunks (< 48000 bytes) at recording stop are intentionally dropped (matches React frontend behavior)
- ScriptProcessorNode deprecation note from React applies to Android too: AudioRecord is the standard Android API and not deprecated
