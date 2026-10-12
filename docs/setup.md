# VISHWAS Setup Guide

Complete setup instructions for the VISHWAS Phase 1 platform.

## Prerequisites

### Backend & Dashboard
- Python 3.11 or higher
- pip package manager
- Virtual environment (recommended)

### Android Application
- Android Studio Arctic Fox (2020.3.1) or newer
- Java JDK 17+
- Android SDK API 24+ (minimum)
- Android SDK API 34 (target)

## Backend Setup

### 1. Navigate to Backend Directory

```bash
cd backend
```

### 2. Create Virtual Environment

```bash
python -m venv venv
```

### 3. Activate Virtual Environment

**macOS/Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```cmd
venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` if you need to change default settings (optional for local development).

### 6. Initialize Database

```bash
python -m app.database.init_db
```

### 7. Run the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will be available at:
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 8. Test the Backend

In a new terminal:

```bash
cd backend
source venv/bin/activate  # Activate venv
pytest tests/ -v
```

## Web Dashboard Setup

### 1. Navigate to Dashboard Directory

```bash
cd web-dashboard
```

### 2. Create Virtual Environment

```bash
python -m venv venv
```

### 3. Activate Virtual Environment

**macOS/Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```cmd
venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Backend URL (Optional)

By default, the dashboard connects to `http://localhost:8000/api/v1`.

To use a different URL, set the environment variable:

```bash
export VISHWAS_API_URL=http://your-backend-url:8000/api/v1
```

### 6. Run the Dashboard

```bash
streamlit run app.py
```

The dashboard will be available at: http://localhost:8501

## Android Application Setup

### 1. Open Project in Android Studio

1. Launch Android Studio
2. Select "Open an Existing Project"
3. Navigate to `android-app` directory
4. Click "OK"

### 2. Sync Gradle

Android Studio will automatically start syncing Gradle. If not:
- Click "File" → "Sync Project with Gradle Files"

### 3. Configure Backend URL

#### For Android Emulator

The default configuration (`http://10.0.2.2:8000/api/v1`) works out of the box with the emulator, pointing to your host machine's localhost.

#### For Physical Device

1. Find your computer's local IP address:

**macOS:**
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

**Linux:**
```bash
hostname -I
```

**Windows:**
```cmd
ipconfig
```

2. Edit `android-app/app/build.gradle.kts`:

Find this line:
```kotlin
buildConfigField("String", "API_BASE_URL", "\"http://10.0.2.2:8000/api/v1\"")
```

Replace with your computer's IP:
```kotlin
buildConfigField("String", "API_BASE_URL", "\"http://192.168.1.XXX:8000/api/v1\"")
```

3. Ensure your firewall allows connections on port 8000

4. Make sure both your computer and phone are on the same network

### 4. Run the Application

#### On Emulator

1. Create a new emulator (if needed):
   - Tools → Device Manager → Create Device
   - Select a device (e.g., Pixel 5)
   - Select system image (API 34 recommended)
   - Click "Finish"

2. Start the emulator

3. Click "Run" (green play button) or press Shift+F10

#### On Physical Device

1. Enable Developer Options on your phone:
   - Settings → About Phone → Tap "Build Number" 7 times

2. Enable USB Debugging:
   - Settings → Developer Options → USB Debugging

3. Connect your phone via USB

4. Click "Run" and select your device

### 5. Test the Application

1. The app should launch on your device
2. Check that "Backend Status" shows "Connected"
3. Upload a test audio file
4. Verify that analysis completes and report displays

## Complete Workflow Test

### 1. Start Backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Start Dashboard (in new terminal)

```bash
cd web-dashboard
source venv/bin/activate
streamlit run app.py
```

### 3. Test Web Dashboard

1. Open http://localhost:8501
2. Go to "Upload Recording"
3. Upload a sample audio file
4. Wait for analysis to complete
5. View the report

### 4. Test Android App

1. Launch app on emulator/device
2. Tap "Upload Recording"
3. Select an audio file
4. Tap "Upload and Analyze"
5. Wait for completion
6. View the report

### 5. Verify Both Clients Show Same Data

1. Check "Analysis History" in both clients
2. The same recordings should appear in both
3. Reports should be identical

## Troubleshooting

### Backend Won't Start

**Error: `ModuleNotFoundError`**
- Solution: Activate virtual environment and reinstall dependencies

**Error: `Address already in use`**
- Solution: Port 8000 is busy. Either stop the other process or change port:
  ```bash
  uvicorn app.main:app --reload --port 8001
  ```

### Dashboard Shows "Backend Unavailable"

1. Check backend is running: http://localhost:8000/api/v1/health
2. Check firewall settings
3. Verify `VISHWAS_API_URL` environment variable (if set)

### Android App Shows "Disconnected"

**Using Emulator:**
- Verify backend is running on host machine
- Use `http://10.0.2.2:8000/api/v1` as backend URL

**Using Physical Device:**
- Verify both devices are on same WiFi network
- Check computer's firewall allows incoming connections on port 8000
- Ping your computer's IP from phone browser
- Try accessing `http://YOUR_IP:8000/docs` from phone browser

**Error: `cleartext traffic not permitted`**
- This is handled in `AndroidManifest.xml` with `usesCleartextTraffic="true"`
- For production, use HTTPS

### Tests Fail

**Database errors:**
- Delete `vishwas.db` and re-run `init_db`

**File permission errors:**
- Ensure `backend/storage/uploads` directory is writable

### Upload Fails

**File too large:**
- Default max: 50MB
- Change in `.env`: `MAX_UPLOAD_SIZE_MB=100`

**Unsupported format:**
- Only WAV, MP3, M4A supported in Phase 1
- Check file extension and MIME type

## Network Configuration for Development

### For Local Development (Single Machine)

- Backend: `http://localhost:8000`
- Dashboard: `http://localhost:8501`
- Android Emulator: `http://10.0.2.2:8000`

### For LAN Development (Multiple Devices)

1. Find your machine's IP (e.g., 192.168.1.100)

2. Update configurations:
   - Dashboard: `export VISHWAS_API_URL=http://192.168.1.100:8000/api/v1`
   - Android: Update `API_BASE_URL` in `build.gradle.kts`

3. Update backend CORS in `.env`:
   ```
   CORS_ORIGINS=http://localhost:8501,http://192.168.1.100:8501
   ```

4. Restart backend after changing CORS settings

## Production Deployment Notes

⚠️ **Phase 1 is NOT production-ready**

Before deploying to production, you must implement:

1. **Authentication & Authorization**
   - User accounts
   - API authentication (JWT, OAuth, etc.)
   - Per-user data isolation

2. **Security**
   - HTTPS/TLS encryption
   - Secrets management (not in .env files)
   - Database encryption at rest
   - Input sanitization
   - Rate limiting

3. **Infrastructure**
   - Production-grade database (PostgreSQL, MySQL)
   - Object storage for recordings (S3, etc.)
   - Load balancing
   - Monitoring and logging
   - Backup and disaster recovery

4. **Compliance**
   - Data retention policy
   - User consent management
   - Privacy policy
   - Terms of service
   - GDPR/privacy law compliance

## Support

For issues or questions:
1. Check this documentation
2. Review API documentation: `docs/api_contract.md`
3. Check backend logs
4. Review Android logcat output

## Next Steps

Once Phase 1 is running successfully:
- Phase 2: Implement real speech-to-text transcription
- Phase 3: Add evidence detection agents
- Phase 4: Integrate knowledge graph
- Phase 5: Deploy advanced fraud detection models
