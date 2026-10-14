# VISHWAS Android App

Kotlin + Jetpack Compose Android client for VISHWAS call fraud detection.

## Setup

### 1. Backend

Run backend with:
- SECRET_KEY=<random-64-chars>
- ANALYSIS_MODE=real
- WHISPER_MODEL=tiny
- ENABLE_VOICE_LAYER=false

### 2. Get Dev Token

POST /api/v1/auth/login with {"email":"...","password":"..."}
Copy the access_token from response.

### 3. RetrofitClient.kt

File: app/src/main/java/com/vishwas/app/network/RetrofitClient.kt

Replace DEV_TOKEN placeholder with your token.

DO NOT commit real token.

### 4. Build

Requires JDK 17:
.\gradlew.bat assembleDebug

### 5. Install

adb install -r app/build/outputs/apk/debug/app-debug.apk
adb reverse tcp:8000 tcp:8000
