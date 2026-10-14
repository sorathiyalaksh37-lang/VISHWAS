# Implementation Plan: Streaming Voice Detection for Vishwas

This plan integrates real-time streaming AI-generated voice detection into the existing Vishwas fraud detection platform. The work is decomposed into three sequential features covering backend, frontend, and Android implementations.

**Project Context**: The backend already has offline voice anti-spoof detection using Vansh180/deepfake-audio-wav2vec2 in `backend/app/audio/voice_layer.py` (VoiceLayer class with `_spoof_prob_for_window()` method). FastAPI backend uses JWT auth (get_current_active_user), SQLAlchemy ORM, 381 passing tests. React+Vite frontend uses Tailwind CSS, lucide-react icons, apiClient singleton. Android Kotlin app uses Jetpack Compose, Retrofit, coroutines/StateFlow in VishwasViewModel.

---

## FEAT-001: Backend Streaming Infrastructure

### What
Create backend streaming voice detection: StreamingVoiceDetector wrapping existing VoiceLayer, in-memory StreamingSessionManager with TTL cleanup, and three new endpoints appended to `backend/app/api/routes/analyze.py`.

### Files
- `backend/app/audio/streaming_voice_detector.py` (new)
- `backend/app/services/streaming_session_manager.py` (new)
- `backend/app/api/routes/analyze.py` (append routes)
- `backend/app/main.py` (register router if needed)
- `backend/tests/test_streaming_voice_detection.py` (new)
- `README_STREAMING_DETECTION.md` (new, at repo root)

### Verification
```bash
pytest tests/test_streaming_voice_detection.py -v
pytest tests/ --ignore=tests/test_m2_perception.py -v  # verify 381+ passing, 0 failed
```

---

## FEAT-002: Frontend React Streaming UI

### What
Create VoiceDetectionPage.tsx: Web Audio API microphone capture, real-time waveform, chunk-by-chunk transmission every ~3s, live spoof-probability gauge, start/stop controls, error/loading states, disclaimer. Integrate into App.tsx routing.

### Files
- `vishwas-frontend/src/services/api.ts` (extend with startStreamingDetection, sendAudioChunk, stopStreamingDetection)
- `vishwas-frontend/src/pages/VoiceDetectionPage.tsx` (new)
- `vishwas-frontend/src/App.tsx` (add route)

### Verification
```bash
npm run dev  # verify no build errors
# Manual test: navigate to Voice Detection, start recording, verify gauge updates every 3s, stop
```

---

## FEAT-003: Android Kotlin Streaming Integration

### What
Android streaming voice detection: StreamingVoiceModels.kt data classes, StreamingVoiceDetectionScreen.kt Compose UI with AudioRecord 16kHz PCM, VishwasApiService endpoint additions, VishwasViewModel extension. Handles RECORD_AUDIO permission.

### Files
- `android-app/app/src/main/java/com/vishwas/app/models/StreamingVoiceModels.kt` (new)
- `android-app/app/src/main/java/com/vishwas/app/network/VishwasApiService.kt` (extend)
- `android-app/app/src/main/java/com/vishwas/app/viewmodel/VishwasViewModel.kt` (extend, DO NOT modify existing methods)
- `android-app/app/src/main/java/com/vishwas/app/ui/screens/StreamingVoiceDetectionScreen.kt` (new)
- `android-app/app/src/main/java/com/vishwas/app/ui/Navigation.kt` (add route)

### Verification
```bash
./gradlew build  # or Android Studio build
# Manual emulator test: navigate to Streaming Voice Detection, start recording, verify label updates, stop
```

---

## Constraints

- **MUST NOT** modify existing `VoiceLayer.analyze()`, existing DB models, existing API endpoints unrelated to streaming
- **MUST** handle model unavailability gracefully (return 'unavailable' label, not crash)
- **Maximum session duration**: 5 minutes
- **Accept only**: WAV 16kHz mono PCM for chunk endpoints
- **Existing 381+ backend tests** must continue passing (no regressions)

---

## Design Decisions

1. **Temporal smoothing**: Exponential moving average (alpha=0.3) reduces jitter in streaming predictions
2. **Quality gate**: Requires >= 3s accumulated audio before confident result
3. **Session TTL**: 30 minutes, background cleanup task prevents memory leak
4. **Thread safety**: threading.Lock in session manager and detector
5. **Audio format**: 16kHz mono WAV PCM (matches VoiceLayer requirement)
6. **Model**: Reuses existing Vansh180/deepfake-audio-wav2vec2 (no new model download)
7. **Chunk size**: ~3s = 48000 bytes (16kHz * 2 bytes/sample * 1 channel * 3s)

---

## Integration Points

- Backend: Appends routes to `backend/app/api/routes/analyze.py` following existing auth/error patterns
- Frontend: Adds page to `src/pages/`, extends `api.ts`, updates `App.tsx` routing
- Android: Adds screen to `ui/screens/`, extends `VishwasApiService`, adds state to `VishwasViewModel`

All three features are independent after FEAT-001 completes (backend must exist before frontend/Android can test against it).
