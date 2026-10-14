# Implementation Plan: FEAT-002 - Frontend Real-Time Voice Detection Integration

This plan implements real-time streaming voice detection in the React frontend, integrating with the backend endpoints completed in FEAT-001.

## Context

- **Backend APIs**: Three authenticated endpoints are live:
  - `POST /api/v1/voice-detection/stream/start` - Start session, returns session_id
  - `POST /api/v1/voice-detection/stream/{session_id}/chunk` - Stream audio chunk, returns {label, spoof_prob, confidence, chunks_processed}
  - `DELETE /api/v1/voice-detection/stream/{session_id}` - Cleanup session
- **Backend expects**: Raw PCM int16, 16kHz mono, 48000 bytes (~1.5s) per chunk
- **Frontend stack**: React 19 + TypeScript + Vite, Tailwind CSS, existing auth via JWT tokens
- **Existing patterns**: 
  - API client in `src/services/api.ts` with typed methods and JWT auth headers
  - Page components follow pattern: `AnalyseACall.tsx`, `Overview.tsx`, `TrustGraphPage.tsx`
  - Navigation via `App.tsx` switch statement with `NavItem` type and `Sidebar.tsx` nav items array
  - Styling uses Tailwind utility classes + custom CSS classes following `analyse-*`, `page-*`, `btn-*` patterns

## Implementation Steps

- [ ] 1. **Add TypeScript types and API client methods for streaming endpoints in `src/services/api.ts`**
      
      Add three TypeScript interfaces at the end of the types section (after `CallListResponse`):
      - `StreamSessionResponse` with fields: session_id, status, chunk_size_bytes, format, max_duration_minutes, ttl_minutes
      - `StreamChunkResponse` with fields: status, label, spoof_prob, confidence, duration_analyzed_ms, chunks_processed
      - `StreamDeleteResponse` with fields: session_id, status, message
      
      Add three methods to the `APIClient` class (before the health check method):
      - `async startVoiceStream(): Promise<StreamSessionResponse | null>` - POST to `/voice-detection/stream/start` with auth headers
      - `async sendVoiceChunk(sessionId: string, chunk: Blob): Promise<StreamChunkResponse | null>` - POST to `/voice-detection/stream/${sessionId}/chunk` with auth headers, send chunk as multipart form with key "chunk"
      - `async deleteVoiceStream(sessionId: string): Promise<StreamDeleteResponse | null>` - DELETE to `/voice-detection/stream/${sessionId}` with auth headers
      
      All methods use `this.getAuthHeaders()` for JWT authentication and follow existing error handling pattern (return null on failure, log errors).
      
      **Files**: `c:\Users\Vaishnavi\Desktop\Vishwas Kiro\VISHWAS\vishwas-frontend\src\services\api.ts`
      
      **Verify**: Run `npm run build` in `vishwas-frontend` directory — TypeScript compilation succeeds with no errors.

- [ ] 2. **Create VoiceDetectionPage.tsx with Web Audio API microphone capture and 16kHz resampling**
      
      Create `c:\Users\Vaishnavi\Desktop\Vishwas Kiro\VISHWAS\vishwas-frontend\src\pages\VoiceDetectionPage.tsx` with:
      
      **Component structure**:
      - State: `recording` (boolean), `sessionId` (string | null), `status` ('idle' | 'requesting-mic' | 'listening' | 'analyzing' | 'error'), `spoofProb` (number | null), `confidence` (string), `chunksProcessed` (number), `errorMsg` (string), `waveformData` (Float32Array for visualization)
      
      **Web Audio API capture logic** (using hooks):
      - Request microphone via `navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: false } })`
      - If browser doesn't support 16kHz natively, create `AudioContext` with default sample rate, then use `OfflineAudioContext` to resample to 16kHz
      - Use `ScriptProcessorNode` or `AudioWorkletNode` (prefer worklet if available) to capture PCM data
      - Convert Float32 PCM from Web Audio API to Int16 (multiply by 32767, clamp to [-32768, 32767])
      - Buffer audio until 48000 bytes accumulated, then call `apiClient.sendVoiceChunk()`
      
      **Session lifecycle**:
      - On "Start Listening" button: call `apiClient.startVoiceStream()`, store session_id, request mic, start buffering
      - On chunk ready: send to backend, update UI with response (spoof_prob, confidence, label)
      - On "Stop" button or component unmount: call `apiClient.deleteVoiceStream(sessionId)`, stop mic, cleanup AudioContext
      
      **UI layout** (following existing page patterns from `AnalyseACall.tsx` and `Overview.tsx`):
      - Page heading with `MicVocalIcon`, title "Real-Time Voice Detection", subtitle explaining live streaming analysis
      - Main card with Start/Stop button (big primary button, disabled states)
      - Live waveform visualization: canvas element showing last 1-2 seconds of audio waveform (simple oscilloscope style)
      - Spoof probability gauge: circular or linear progress bar showing 0-100%, color-coded (green 0-30%, yellow 30-70%, red 70-100%)
      - Status indicator badges: "Listening...", "Analyzing...", "Complete", error states
      - Info text showing chunks processed, confidence level, current label
      - Error handling UI for mic permission denied, network failures, backend errors
      
      **Styling**: Use Tailwind utilities + existing CSS class patterns (`btn-primary`, `page-heading`, `analyse-dropzone` style cards). Match color scheme and spacing from `AnalyseACall.tsx`.
      
      **Files**: `c:\Users\Vaishnavi\Desktop\Vishwas Kiro\VISHWAS\vishwas-frontend\src\pages\VoiceDetectionPage.tsx`
      
      **Verify**: Run `npm run dev` in `vishwas-frontend`, navigate to `/voice-detection` (after step 3), verify component renders, Start button requests mic permission, waveform displays when mic is active. TypeScript compilation succeeds.

- [ ] 3. **Update App.tsx routing and Sidebar.tsx navigation to add /voice-detection route and nav link**
      
      **In `src\App.tsx`**:
      - Import `VoiceDetectionPage` at top: `import { VoiceDetectionPage } from './pages/VoiceDetectionPage'`
      - Add `'voice-detection'` to the `NavItem` type definition (line 8): change to `type NavItem = 'overview' | 'trust-graph' | 'analyse' | 'history' | 'settings' | 'voice-detection'`
      - In `renderPage()` function, add case before `case 'settings'`: 
        ```typescript
        case 'voice-detection':
          return <VoiceDetectionPage />
        ```
      
      **In `src\components\layout\Sidebar.tsx`**:
      - Update `NavItem` type export (line 14) to include `'voice-detection'`: change to `export type NavItem = 'overview' | 'trust-graph' | 'analyse' | 'history' | 'settings' | 'voice-detection'`
      - Add entry to `NAV_ITEMS` array after the 'history' entry (around line 44):
        ```typescript
        {
          id: 'voice-detection',
          label: 'Live Voice Detection',
          icon: <MicVocalIcon size={18} aria-hidden="true" />,
        },
        ```
      - Import `MicVocalIcon` is already present, no import changes needed
      
      **Files**: 
      - `c:\Users\Vaishnavi\Desktop\Vishwas Kiro\VISHWAS\vishwas-frontend\src\App.tsx`
      - `c:\Users\Vaishnavi\Desktop\Vishwas Kiro\VISHWAS\vishwas-frontend\src\components\layout\Sidebar.tsx`
      
      **Verify**: Run `npm run dev` in `vishwas-frontend`, verify "Live Voice Detection" appears in sidebar navigation, clicking it navigates to the voice detection page, URL shows `/voice-detection`. No console errors. TypeScript compilation succeeds.

- [ ] 4. **Implement 48000-byte chunking and backend integration with error handling**
      
      **In `VoiceDetectionPage.tsx`** (created in step 2), refine the audio processing:
      
      - Maintain a `Uint8Array` buffer for incoming PCM int16 data
      - When buffer reaches 48000 bytes (24000 samples of int16), extract chunk and send
      - Wrap `apiClient.sendVoiceChunk()` call in try-catch
      - Handle response cases:
        - Success with `label: 'insufficient_data'` → show "Analyzing..." status, don't update gauge yet
        - Success with `label: 'uncertain'` → show confidence level, update gauge with current spoof_prob
        - Success with `label: 'human'` or `'ai_generated'` → show final result prominently, update gauge, consider auto-stopping after 5-10 chunks for demo purposes (optional)
        - Network error → show error banner "Network error - check backend connection", stop recording
        - 404 (session expired) → show error "Session expired", allow restart
        - 503 (model unavailable) → show error "Voice detection model unavailable", disable feature
      
      - Add timeout handling: if no successful response within 10 seconds of chunk send, show warning "Backend slow or unreachable"
      - Implement cleanup on errors: always call `deleteVoiceStream` if session exists before showing error
      
      **Files**: `c:\Users\Vaishnavi\Desktop\Vishwas Kiro\VISHWAS\vishwas-frontend\src\pages\VoiceDetectionPage.tsx`
      
      **Verify**: 
      - With backend running (`uvicorn app.main:app --reload` in backend directory), run `npm run dev` in frontend
      - Click "Start Listening", grant mic permission
      - Speak into microphone for 3-5 seconds
      - Verify chunks are sent (check browser DevTools Network tab for POST requests to `/voice-detection/stream/{session_id}/chunk`)
      - Verify spoof_prob gauge updates with each successful response
      - Verify status changes from "Listening..." to "Analyzing..." to final result
      - Click "Stop", verify DELETE request sent to cleanup session
      - Test error case: stop backend, click Start, verify error message appears

- [ ] 5. **Implement waveform visualization canvas with real-time audio rendering**
      
      **In `VoiceDetectionPage.tsx`**, add waveform visualization:
      
      - Create a `<canvas>` element with ref, size approximately 600x100px (responsive via Tailwind classes)
      - In the Web Audio API processing callback (ScriptProcessorNode or AudioWorkletNode), capture the last 1-2 seconds of PCM float32 samples for display
      - Store in state: `waveformData: Float32Array` (e.g., 16000 samples = 1 second at 16kHz)
      - Use `useEffect` or `requestAnimationFrame` to draw waveform every 50-100ms:
        - Clear canvas with background color matching card background
        - Draw waveform as line graph or filled area, centered vertically
        - Use stroke color matching theme (blue/accent color when listening, gray when idle)
      
      - Position canvas prominently in the UI, above or beside the spoof probability gauge
      
      **Files**: `c:\Users\Vaishnavi\Desktop\Vishwas Kiro\VISHWAS\vishwas-frontend\src\pages\VoiceDetectionPage.tsx`
      
      **Verify**: 
      - Run `npm run dev`, navigate to voice detection page, click Start
      - Speak into microphone, verify waveform animates in real-time showing audio signal
      - Verify waveform stops updating when Stop is clicked
      - Verify waveform is visually clear and matches existing page aesthetic

- [ ] 6. **Polish UI: responsive design, loading states, accessibility, and final styling**
      
      **In `VoiceDetectionPage.tsx`**, add final polish:
      
      - **Responsive design**: Use Tailwind breakpoints to stack layout vertically on mobile (waveform above gauge, full width buttons)
      - **Loading states**: Show spinner on Start button during "requesting-mic" status, disable button during recording
      - **Accessibility**: Add ARIA labels to canvas ("Audio waveform visualization"), gauge ("Spoof probability: X%"), buttons (clear labels), status indicators (aria-live regions)
      - **Empty state**: When idle, show placeholder text "Click Start to begin live voice analysis"
      - **Success state**: When high confidence result received, show prominent badge with result (green "Human Voice Detected" or red "AI-Generated Voice Detected")
      - **Styling refinement**: Ensure colors, spacing, typography match existing pages (`AnalyseACall.tsx`, `Overview.tsx`). Use consistent card backgrounds, borders, shadows.
      
      **Files**: `c:\Users\Vaishnavi\Desktop\Vishwas Kiro\VISHWAS\vishwas-frontend\src\pages\VoiceDetectionPage.tsx`
      
      **Verify**: 
      - Run `npm run build` in `vishwas-frontend` directory — build succeeds, no warnings
      - Run `npm run dev`, test on desktop browser at various window sizes
      - Test on mobile viewport (DevTools responsive mode)
      - Verify keyboard navigation works (Tab to Start/Stop button, Enter to activate)
      - Verify screen reader announcements (test with browser's accessibility inspector)
      - Verify visual consistency with rest of app (colors, fonts, spacing)

## Design Decisions

1. **Web Audio API resampling strategy**: The browser's native `getUserMedia` may not support 16kHz directly (most browsers default to 48kHz). We'll request 16kHz in constraints, but implement fallback resampling using `OfflineAudioContext` to ensure backend receives correct sample rate. This adds ~50-100ms latency but guarantees compatibility.

2. **Chunking approach**: Buffer raw PCM int16 bytes in a `Uint8Array` and send exactly 48000 bytes per chunk. This matches backend expectation (~1.5s at 16kHz mono int16). Chunks are sent immediately when buffer fills, maintaining low latency (~1.5s behind real-time).

3. **Session lifecycle**: Start session on "Start" button, keep alive during recording, explicit cleanup on Stop or component unmount. Backend auto-expires sessions after 30 minutes, so no server-side cleanup logic needed for page refresh (session orphaned but auto-cleaned).

4. **Visualization choice**: Simple oscilloscope-style waveform (time-domain plot) rather than frequency spectrum because it's easier to implement, lower CPU overhead, and sufficient for showing "audio is being captured". Real-time spoof probability gauge is the primary feedback mechanism.

5. **Error handling philosophy**: Fail gracefully with clear user messaging. Never leave orphaned sessions — always call DELETE on errors. Show actionable error messages ("Check microphone permissions", "Start backend server", etc.) rather than technical error codes.

6. **Responsive layout**: Desktop: waveform and gauge side-by-side, large Start/Stop button. Mobile: vertical stack, full-width button. Follows existing responsive patterns in `Overview.tsx` and `AnalyseACall.tsx`.

## Verification Strategy

Each step includes inline verification commands. Final end-to-end verification after all steps complete:

1. **Build verification**: `npm run build` in `vishwas-frontend` succeeds with no TypeScript errors
2. **Integration test**: 
   - Start backend: `cd backend && uvicorn app.main:app --reload`
   - Start frontend: `cd vishwas-frontend && npm run dev`
   - Navigate to http://localhost:5173/voice-detection
   - Login if needed, click "Start Listening", grant mic permission
   - Speak for 5 seconds, verify waveform animates and spoof probability updates
   - Click "Stop", verify session cleanup
   - Check browser console for errors (should be clean)
   - Check backend logs for session creation, chunk processing, deletion (should show successful requests)
3. **Cross-browser test**: Verify in Chrome, Firefox, Edge (if available) — Web Audio API has slight differences
4. **Mobile test**: Verify in mobile browser or responsive DevTools mode

## Notes

- The backend EMA smoothing (alpha=0.3) is handled server-side, so frontend doesn't need to implement additional smoothing
- Backend returns spoof_prob as float [0-1], UI converts to percentage (0-100%) for display
- Confidence levels: "insufficient_data" (< 1.5s analyzed), "low" (1.5-3s), "medium" (3-4.5s), "high" (4.5s+) — these thresholds are backend-determined
- Audio privacy: Raw audio is processed client-side and sent to backend in 1.5s chunks, never stored permanently (backend processes and discards immediately)
