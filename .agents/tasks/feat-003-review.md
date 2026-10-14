# Android Streaming Voice Detection Implementation

Real-time voice spoofing detection integrated into the Android app using AudioRecord, Kotlin coroutines, and the existing streaming voice detection backend API. Audio captured from the device microphone is chunked into 48000-byte segments, transmitted to the backend via Retrofit, and analyzed incrementally with results displayed through a circular gauge, waveform visualization, and status cards.

The implementation threads AudioRecord capture on `Dispatchers.Default`, manages session lifecycle through the ViewModel, handles runtime permission requests, and cleans up resources on disposal, navigation, and stop. Backend session expiry (404), network failures, and permission denial are surfaced to the UI.

**Watch for**: Path parameter mismatch will cause 404 errors (confirmed) — Retrofit endpoints use `{sessionId}` but backend routes expect `{session_id}`. AudioRecord runs on background thread (confirmed). Permission requested at runtime (confirmed). Chunking sends 48000 bytes (confirmed). ViewModel.onCleared() missing (confirmed) — no override to cancel streaming or delete sessions when ViewModel is destroyed, leaking backend sessions until the 30-minute TTL. Stale waveform data persists across sessions (cosmetic, likely).

**Verdict**: CHANGES_REQUESTED

---

## High-level view

The ViewModel exposes StreamingVoiceState as a sealed class with six states and three suspend functions that delegate to the Repository. The Repository wraps API calls with `withContext(Dispatchers.IO)`, constructs MultipartBody.Part from raw bytes, and translates 404/503 to error messages. The API service defines three endpoints with Retrofit annotations, but the path parameters use `{sessionId}` (camelCase) while the backend routes expect `{session_id}` (snake_case), causing 404 routing failures.

The UI screen manages AudioRecord lifecycle in a `LaunchedEffect` coroutine on Dispatchers.Default, accumulating bytes to 48000-byte chunks. Permission is requested via `rememberLauncherForActivityResult`. Cleanup happens in DisposableEffect, button handlers, and back navigation. The waveform Canvas converts PCM_16BIT samples to normalized floats; the circular gauge colors spoof probability (green < 0.3, yellow < 0.6, red >= 0.6).

Two gaps: path parameters (`{sessionId}` vs `{session_id}`) will cause all chunk uploads and session deletes to return 404, and ViewModel.onCleared() is missing, leaking backend sessions when the ViewModel is destroyed.

---

<details>
<summary>Issues (4)</summary>

1. **Path parameter name mismatch breaks routing** — VishwasApiService.kt uses `{sessionId}` in `@POST("voice-detection/stream/{sessionId}/chunk")` and `@DELETE("voice-detection/stream/{sessionId}")`, but the backend routes expect `{session_id}`. Change both Retrofit paths to `{session_id}` to match the backend's FastAPI route definitions.

2. **ViewModel cleanup missing** — VishwasViewModel does not override onCleared() to cancel streaming coroutines or delete backend sessions. When the ViewModel is destroyed (process death, ViewModel scope cleared), active sessions leak until the 30-minute TTL. Override onCleared() and track the active sessionId to call stopVoiceStreaming() before clearing.

3. **Stale waveform persists across sessions** — `waveformData` state is not reset when transitioning from Complete/Error to a new session. The "Start New Session" button resets the state machine but not the waveform array. Reset `waveformData = FloatArray(100) { 0f }` in the same button handler or when starting recording.

4. **Partial chunk dropped at session end** — Accumulated bytes (0-47999) are discarded when recording stops. The plan documents this as intentional (matching React frontend), but the UI info card does not mention it. Users might expect the last 1-2 seconds to be analyzed. Add a note to the info card: "Audio is processed in ~1.5s chunks; the final partial chunk is not analyzed."

</details>

---

<details>
<summary>Details</summary>

## AudioRecord threading and lifecycle

AudioRecord runs on Dispatchers.Default (confirmed correct). The read loop checks `isRecording && isActive`. Cleanup happens in three places: stop button, back navigation, and DisposableEffect.onDispose. All paths release AudioRecord and delete the backend session.

If the ViewModel is destroyed while recording (process death, configuration change), the LaunchedEffect coroutine continues running (tied to Composable lifecycle, not ViewModel lifecycle). The ViewModel has no `onCleared()` override, so the backend session leaks until the 30-minute TTL.

The buffer position concern from the plan is not relevant (each session creates a fresh AudioRecord instance). The `waveformData` state variable is not reset until the user taps "Start New Session," briefly showing stale data from the previous session when starting a new recording.

## Chunking and accumulation

The read loop accumulates bytes into a `ByteArray`, appending `bytesRead` bytes each iteration. When `accumulated.size >= 48000`, it extracts exactly 48000 bytes, sends via `viewModel.sendAudioChunk()`, and retains leftover bytes. Chunk size matches backend expectation (48000 bytes = 1.5s at 16kHz mono PCM_16BIT). Alignment logic is correct.

When recording stops, `accumulated` (0-47999 bytes) is discarded. The plan documents this as intentional (matching React frontend). The UI info card does not mention this behavior.

## Runtime permission flow

The screen checks `ContextCompat.checkSelfPermission` on composition. If denied, shows "Request Permission" button calling `permissionLauncher.launch()` (ActivityResult API, correct pattern). The manifest declares RECORD_AUDIO.

If the user denies twice, Android may set "Don't ask again" and `permissionLauncher.launch()` silently fails. The UI should detect this (`shouldShowRequestPermissionRationale`) and direct the user to app settings.

## API path parameter mismatch

Retrofit endpoints use `{sessionId}` (camelCase):

```kotlin
@POST("voice-detection/stream/{sessionId}/chunk")
@DELETE("voice-detection/stream/{sessionId}")
```

Backend routes expect `{session_id}` (snake_case):

```python
@router.post("/voice-detection/stream/{session_id}/chunk")
@router.delete("/voice-detection/stream/{session_id}")
```

FastAPI path matching is exact. The Retrofit URLs will be `/voice-detection/stream/{sessionId}/chunk` (literal placeholder substitution), which won't match the backend route pattern. All chunk uploads and session deletes will return 404. Change Retrofit paths to `{session_id}`.

## @SerializedName mappings

All `@SerializedName` annotations map Kotlin camelCase to backend snake_case correctly: `session_id`, `chunk_size_bytes`, `spoof_prob`, `chunks_processed`, `duration_analyzed_ms`, `max_duration_minutes`, `ttl_minutes`.

## State transitions and error handling

The ViewModel updates state based on `response.label`:

- `"insufficient_data"` → Listening
- `"uncertain"`, `"human"`, `"ai_generated"` → Analyzing

Backend emits these four labels based on confidence level and threshold. The Repository translates 404 to "Session expired" and 503 to "Voice detection service unavailable". Network failures are caught and converted to Error state.

## Waveform visualization

PCM_16BIT byte-to-short conversion reads little-endian 16-bit samples. Division by 32768f normalizes to [-1.0, 1.0]. Canvas draws a path connecting 100 downsampled points. The waveform updates every ~50ms (for bufferSize=6400).

</details>

---

<details>
<summary>File Map</summary>

- `.agents/tasks/feat-003-build-note.md` — Build verification note documenting manual verification due to Gradle network constraints
- `android-app/app/src/main/java/com/vishwas/app/models/StreamingVoiceModels.kt` — New data classes for streaming voice API responses (StreamSessionResponse, StreamChunkResponse, StreamDeleteResponse) with @SerializedName mappings
- `android-app/app/src/main/java/com/vishwas/app/network/VishwasApiService.kt` — Added three streaming endpoints (start, chunk upload, delete) with Retrofit annotations
- `android-app/app/src/main/java/com/vishwas/app/data/VishwasRepository.kt` — Added streaming methods with 404/503 error handling and MultipartBody construction
- `android-app/app/src/main/java/com/vishwas/app/viewmodel/VishwasViewModel.kt` — Added StreamingVoiceState sealed class and streaming methods (startVoiceStreaming, sendAudioChunk, stopVoiceStreaming, resetVoiceStreamingState)
- `android-app/app/src/main/java/com/vishwas/app/ui/screens/StreamingVoiceDetectionScreen.kt` — New Compose screen with AudioRecord capture, waveform visualization, circular gauge, runtime permission handling, and resource cleanup
- `android-app/app/src/main/java/com/vishwas/app/ui/Navigation.kt` — Added VOICE_DETECTION route, navigation drawer item, and composable registration
- `android-app/app/src/main/AndroidManifest.xml` — No changes (RECORD_AUDIO permission already present)

Full diff: `git diff main` (shows backend Python changes from a different commit; Android changes are in commit 5f52448)

</details>
