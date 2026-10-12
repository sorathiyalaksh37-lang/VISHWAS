# VISHWAS Android Application

Android mobile client for the VISHWAS call fraud detection platform.

## Tech Stack

- **Language:** Kotlin
- **UI:** Jetpack Compose + Material 3
- **Architecture:** MVVM (ViewModel + StateFlow)
- **Networking:** Retrofit + OkHttp
- **Min SDK:** 24 (Android 7.0)
- **Target SDK:** 34 (Android 14)

## Setup

### Prerequisites

- Android Studio Arctic Fox or newer
- Java JDK 17+
- Android SDK with API 34

### Building

1. Open project in Android Studio
2. Sync Gradle
3. Build → Make Project

### Running

#### On Emulator
1. Create/start an AVD
2. Run → Run 'app'
3. Default backend URL: `http://10.0.2.2:8000/api/v1`

#### On Physical Device
1. Update backend URL in `app/build.gradle.kts`:
   ```kotlin
   buildConfigField("String", "API_BASE_URL", "\"http://YOUR_IP:8000/api/v1\"")
   ```
2. Ensure device and computer are on same network
3. Enable USB debugging on device
4. Connect via USB
5. Run → Run 'app'

## Features

- Upload audio recordings (WAV, MP3, M4A)
- Real-time analysis status polling
- View detailed fraud analysis reports
- Browse analysis history
- Backend health monitoring

## Architecture

```
UI Layer (Composables)
    ↓
ViewModel (StateFlow)
    ↓
Repository
    ↓
API Service (Retrofit)
    ↓
Backend API
```

## Project Structure

```
app/src/main/java/com/vishwas/app/
├── data/
│   └── VishwasRepository.kt       # Data layer
├── models/
│   └── ApiModels.kt                # Data classes
├── network/
│   ├── RetrofitClient.kt           # HTTP client
│   └── VishwasApiService.kt        # API interface
├── ui/
│   ├── screens/                    # Composable screens
│   ├── theme/                      # Material theme
│   └── Navigation.kt               # Navigation setup
├── viewmodel/
│   └── VishwasViewModel.kt         # UI state management
└── MainActivity.kt                 # App entry point
```

## Configuration

Backend URL is configured in `app/build.gradle.kts`:

```kotlin
buildConfigField("String", "API_BASE_URL", "\"YOUR_URL\"")
```

- Emulator: `http://10.0.2.2:8000/api/v1`
- Physical Device: `http://<YOUR_IP>:8000/api/v1`

## Permissions

Required permissions (already in `AndroidManifest.xml`):
- `INTERNET` - Network access
- `READ_EXTERNAL_STORAGE` - File access (SDK ≤ 32)
- `READ_MEDIA_AUDIO` - Audio file access (SDK ≥ 33)

## Testing

The app connects to a real backend server for testing. Ensure the backend is running before testing.

Manual test workflow:
1. Launch app
2. Check backend status shows "Connected"
3. Tap "Upload Recording"
4. Select audio file
5. Tap "Upload and Analyze"
6. Wait for completion
7. View report
8. Check "Analysis History"

## Troubleshooting

### Backend Disconnected

**Emulator:**
- Verify backend running on host
- Use `http://10.0.2.2:8000/api/v1`
- Check backend logs

**Physical Device:**
- Verify same WiFi network
- Check firewall allows port 8000
- Test backend URL in phone browser
- Verify IP address is correct

### Upload Fails

- Check file size (max 50MB)
- Verify file format (WAV, MP3, M4A)
- Check backend logs
- Verify storage permissions granted

### App Crashes

- Check logcat output
- Verify Gradle sync successful
- Clean and rebuild project
- Check for network connectivity

## Development

### Adding New Features

1. Update API models in `models/ApiModels.kt`
2. Add repository methods in `VishwasRepository.kt`
3. Update ViewModel state and logic
4. Create/update UI screens
5. Test end-to-end

### Code Style

- Follow Kotlin coding conventions
- Use Jetpack Compose best practices
- Keep composables small and focused
- Use StateFlow for reactive UI
- Handle errors gracefully

## Phase 1 Limitations

- Mock analysis only (not real AI detection)
- No authentication
- HTTP only (no HTTPS)
- Single user (no user accounts)
- Local backend only

## Future Enhancements

- User authentication
- HTTPS support
- Push notifications for completed analyses
- Offline support with local database
- Audio recording within app
- Multiple language support
- Detailed visualization of findings
- Export reports as PDF

## License

Copyright © 2026 VISHWAS Team. All rights reserved.
