# Real-time voice detection frontend implementation

Adds VoiceDetectionPage.tsx implementing Web Audio API-based microphone capture with 16kHz mono resampling, 48000-byte chunking, live waveform visualization, JWT-authenticated streaming API integration, and session lifecycle management. The page follows existing UI patterns from AnalyseACall.tsx and integrates cleanly into the routing and navigation structure.

Build verification in the commit message shows `npm run build` passed with no TypeScript errors in new files. Pre-existing errors (16 unrelated) remain in other files.

**Watch for:** Buffer position leak during rapid stop/start sequences (likely), ScriptProcessorNode deprecation with no AudioWorklet fallback (confirmed), missing error recovery when backend session expires mid-stream (confirmed), and TypeScript type mismatch for spoof_prob nullability (confirmed).

**Verdict**: CHANGES_REQUESTED

## High-level view

The Web Audio API capture pipeline resamples browser audio to 16kHz mono and buffers raw PCM int16 bytes until reaching exactly 48000 bytes before sending, matching the backend's chunk size expectation. Session lifecycle starts with POST to `/stream/start`, sends chunks via multipart form to `/stream/{id}/chunk`, and cleans up with DELETE on stop or unmount. The waveform canvas animates via requestAnimationFrame with latest audio data, and the probability gauge updates on every chunk response with color-coded feedback (green < 0.3, yellow < 0.7, red >= 0.7). The result badge only appears when confidence is 'medium' or 'high', leaving 'low' and 'uncertain' states silent. Error handling catches mic permission denial and device-not-found but doesn't handle 404 session-expired responses during active streaming. The buffer position counter isn't reset on session restart, so rapid stop/start sequences can send partial chunks or corrupt alignment.

<details>
<summary>Issues (5)</summary>

1. **Buffer position leak** — Reset `bufferPositionRef.current = 0` inside `stopRecording()` to prevent stale buffer state when restarting a session.
2. **ScriptProcessorNode deprecation** — Replace ScriptProcessorNode with AudioWorkletNode or add a comment acknowledging the trade-off (cross-browser compatibility vs. deprecation warnings).
3. **Missing session expiry handling** — Catch 404 responses in `processAudio()` when backend session expires mid-stream, display an error banner, and stop recording automatically.
4. **Nullable spoof_prob type mismatch** — Backend returns `spoof_prob: null` during insufficient_data phase; TypeScript interface declares `number`, causing runtime null handling without type safety. Change to `spoof_prob: number | null`.
5. **Partial chunk on stop** — When recording stops with 1-47999 bytes buffered, those bytes are dropped. Document this as expected (partial chunks are invalid) or send a final padded/truncated chunk if backend supports it.

</details>

<details>
<summary>Details</summary>

## Web Audio capture and 16kHz resampling

The AudioContext is instantiated with `{ sampleRate: 16000 }` and the getUserMedia constraint requests 16kHz directly. Browsers may or may not honor the exact rate, but the AudioContext construction forces resampling internally when browser hardware runs at a different rate (typically 48kHz). The Float32 PCM from `getChannelData(0)` is converted to Int16 in `float32ToInt16()` with proper clamping and signed range scaling. The buffer size is 4096 samples, meaning `onaudioprocess` fires every ~256ms at 16kHz.

## 48000-byte chunking and buffer management

`bufferRef.current` is a Uint8Array of 96000 bytes (double the chunk size) to hold overflow between process callbacks. Each `onaudioprocess` event receives 4096 samples (8192 bytes as int16), and those bytes are copied into the buffer at `bufferPositionRef.current`. When position reaches 48000, the first 48000 bytes are sliced into a Blob and sent via `sendVoiceChunk()`. The position counter resets to 0, but the buffer itself is reused.

**Confirmed issue:** `bufferPositionRef.current` is never reset in `stopRecording()`. If a user stops recording with 20000 bytes buffered, then starts a new session, the first chunk will concatenate old+new bytes and send a corrupted 48000-byte slice. The fix is trivial: add `bufferPositionRef.current = 0` in `stopRecording()` before clearing the session.

**Confirmed behavior:** Partial chunks (< 48000 bytes) remaining in the buffer when recording stops are silently dropped. This is correct if the backend rejects partial chunks, but there's no comment explaining the choice. If the backend's chunking strategy tolerates variable sizes, the implementation wastes the final 0-47999 bytes of every recording.

## Session lifecycle and resource cleanup

The session flow is:
1. `startRecording()` calls `apiClient.startVoiceStream()` → backend returns `session_id`
2. Every 48000 bytes triggers `apiClient.sendVoiceChunk(sessionId, blob)`
3. `stopRecording()` calls `apiClient.deleteVoiceStream(sessionId)` then stops the MediaStream and closes the AudioContext
4. `useEffect` cleanup on unmount calls `stopRecording()` if still recording

**Confirmed gap:** If the backend session expires (30 minutes idle, per backend docs) while the user is still recording, `sendVoiceChunk()` will receive a 404 response. The current code logs an error and calls `stopRecording()`, but the user sees a generic "Failed to send audio chunk" error without understanding the session expired. The backend also returns 503 (model unavailable) and 400 (invalid format), but those are also collapsed into the same error message.

**Confirmed gap:** Network errors return `null` from `sendVoiceChunk()`, which triggers `setErrorMsg('Network error - check backend connection')` and stops recording. No retry or resume mechanism exists; the user must restart from scratch.

## JWT authentication and TypeScript types

All three API methods call `getAuthHeaders()` which injects `Authorization: Bearer <token>`. The `/chunk` endpoint constructs its own header object and appends the token manually (instead of calling `getAuthHeaders()`) because it uses FormData and needs to avoid setting `Content-Type`.

TypeScript interfaces in `api.ts`:

```typescript
export interface StreamChunkResponse {
  status: string
  label: string
  spoof_prob: number
  confidence: string
  duration_analyzed_ms: number
  chunks_processed: number
}
```

**Confirmed type mismatch:** Backend returns `spoof_prob: null` when `label === 'insufficient_data'`, but the interface declares `number`. The component handles this with `spoofProb !== null` checks, so runtime behavior is safe, but TypeScript loses the nullability constraint. Change to `spoof_prob: number | null` for type safety.

The `label` field is typed as `string` but the backend contract specifies `'human' | 'ai_generated' | 'uncertain' | 'insufficient_data'`. Using a string union would catch typos in the rendering logic.

## Live waveform and probability gauge

The waveform canvas is 800×120 logical pixels (scaled to 100% width via CSS). `drawWaveform()` runs every frame via `requestAnimationFrame`, reading the latest `waveformData` array (a Float32Array of 16000 samples = 1 second at 16kHz). Each `onaudioprocess` callback overwrites this array with the current 4096-sample buffer via `setWaveformData(new Float32Array(audioData))`.

This means the waveform displays the most recent 4096 samples (~256ms), not a rolling 1-second window. The visualization is mislabeled by the variable name.

The probability gauge is a horizontal progress bar with width `${spoofProb * 100}%` and background color from `getSpoofColor()`: green < 0.3, amber 0.3-0.7, red >= 0.7. The percentage text is rendered above the bar with the same color.

The result badge (CheckCircle2 for human, AlertCircle for AI) only renders when `confidence === 'high' || confidence === 'medium'`. This leaves 'low' and 'uncertain' responses without feedback. The design choice is defensible (don't show a verdict when confidence is weak), but there's no note explaining it.

## Error handling: mic permissions, network, session timeout

Mic permission denial is caught in the `getUserMedia` try-catch and identified via `error.name === 'NotAllowedError'` → "Microphone permission denied". Device-not-found is caught via `error.name === 'NotFoundError'` → "No microphone found". Generic errors display "Failed to access microphone".

Network failures in `sendVoiceChunk()` return `null`, which triggers `setErrorMsg('Network error - check backend connection')` and stops recording. The `startVoiceStream()` and `deleteVoiceStream()` methods also handle null returns, but those failures are logged to console without user-visible feedback (start failure shows "Failed to start session - backend unavailable", delete failure is silent).

**Confirmed gap:** Backend 404 responses (session expired or not found) during chunk upload are caught in the try-catch as network errors and display the generic "Failed to send audio chunk" message. The backend's 404 detail field (`"Session not found or expired"`) is never read or shown. The user can't distinguish between session expiry, network failure, and invalid session ID.

## Routing and navigation integration

`App.tsx` adds `case 'voice-detection': return <VoiceDetectionPage />` to the page router. `Sidebar.tsx` adds the nav item with `ActivityIcon` and `id: 'voice-detection'`. `Shell.tsx` adds page metadata (title + subtitle). The nav item appears between "Call History" and "Privacy & Settings".

**Merge conflict artifact:** The App.tsx diff shows `<<<<<<< HEAD` and `>>>>>>> 3fa6a05` markers around the authentication loading spinner. These are resolved in the final code (the spinner block is intact), but the diff was generated from a branch with an unresolved merge. The commit message doesn't mention this. The conflict was resolved correctly — the markers don't appear in the working tree — but it's unclear if the resolution was manual or automatic.

## UI/UX pattern consistency

The page uses `analyse-pipeline-card`, `risk-badge`, `analysis-status`, and `info-card` matching the existing theme. Button style `btn-primary` with consistent icon sizing (16px) and gap (8px). The disabled state during `'requesting-mic'` uses the spinner from AnalyseACall.tsx (`RefreshCwIcon` with `analysis-status__spinner` class).

## ScriptProcessorNode deprecation

ScriptProcessorNode has been deprecated since 2014 in favor of AudioWorkletNode. Modern browsers still support it but log console warnings. AudioWorklet requires a separate worklet module file (not just inline code), which adds build complexity but runs audio processing off the main thread.

The implementation uses ScriptProcessorNode without a fallback or comment. For a real-time audio app, the main-thread blocking from ScriptProcessorNode can cause glitches under CPU load.

**Not tested:** The build evidence mentions "no TypeScript errors in new files", but there's no indication that the microphone capture or chunking was manually tested with a real backend. The commit message lists what was built, not what was verified to work at runtime.

</details>

<details>
<summary>File map</summary>

- **vishwas-frontend/src/pages/VoiceDetectionPage.tsx** — New page component implementing microphone capture, audio resampling, chunking, waveform visualization, streaming API integration, and session lifecycle
- **vishwas-frontend/src/services/api.ts** — Added `startVoiceStream()`, `sendVoiceChunk()`, `deleteVoiceStream()` methods and corresponding TypeScript interfaces (StreamSessionResponse, StreamChunkResponse, StreamDeleteResponse)
- **vishwas-frontend/src/App.tsx** — Added route case for 'voice-detection' and imported VoiceDetectionPage
- **vishwas-frontend/src/components/layout/Sidebar.tsx** — Added 'voice-detection' nav item with ActivityIcon
- **vishwas-frontend/src/components/layout/Shell.tsx** — Added page metadata (title + subtitle) for 'voice-detection'

[Full diff](https://github.com/user/repo/commit/0f94c40)

</details>
