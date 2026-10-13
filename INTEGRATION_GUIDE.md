# VISHWAS Frontend-Backend Integration Guide

**Date:** 2026-10-13  
**Status:** ✅ Ready for Integration Testing

---

## Architecture Overview

```
┌─────────────────────────┐
│   Web Dashboard         │
│   (Streamlit)           │
│   Port: 8501            │
└───────────┬─────────────┘
            │ HTTP REST API
            │ (JSON)
            ▼
┌─────────────────────────┐
│   Backend API           │
│   (FastAPI)             │
│   Port: 8000            │
└─────────────────────────┘
```

---

## Quick Start

### Option 1: Automated Startup (Recommended)

**Windows PowerShell:**
```powershell
.\start-vishwas.ps1
```

This script will:
1. Check Python installation
2. Create `.env` from template if needed
3. Start backend server (port 8000)
4. Wait for backend to be ready
5. Start frontend dashboard (port 8501)
6. Display access URLs

**To Stop:**
```powershell
.\stop-vishwas.ps1
```

### Option 2: Manual Startup

**Terminal 1 - Backend:**
```powershell
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Frontend:**
```powershell
cd web-dashboard
$env:VISHWAS_API_URL = "http://localhost:8000/api/v1"
streamlit run app.py --server.port 8501
```

---

## Prerequisites

### Backend Dependencies
```bash
cd backend
pip install -r requirements.txt
```

**Core packages:**
- `fastapi` - API framework
- `uvicorn` - ASGI server
- `sqlalchemy` - Database ORM
- `pydantic` - Data validation

**Optional (for real mode):**
- `faster-whisper` - ASR transcription
- `torch` - Deep learning
- `speechbrain` - Voiceprint matching

### Frontend Dependencies
```bash
cd web-dashboard
pip install -r requirements.txt
```

**Required packages:**
- `streamlit` - Dashboard framework
- `requests` - HTTP client
- `plotly` - Interactive charts
- `python-dotenv` - Environment config

---

## Configuration

### Backend Configuration

**File:** `backend/.env`

```env
# Analysis Mode
ANALYSIS_MODE=mock              # Use "real" for actual transcription

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=true

# CORS (Required for frontend access)
CORS_ORIGINS=http://localhost:8501,http://localhost:3000

# Database
DATABASE_URL=sqlite:///./vishwas.db

# Storage
UPLOAD_DIR=./storage/uploads
MAX_UPLOAD_SIZE_MB=50
ALLOWED_EXTENSIONS=wav,mp3,m4a

# ASR (if ANALYSIS_MODE=real)
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8

# Voice Layer
ENABLE_VOICE_LAYER=true

# Tier 2 Agents (Phase 3)
TIER2_ENABLED=false
```

### Frontend Configuration

**Environment Variable:**
```powershell
$env:VISHWAS_API_URL = "http://localhost:8000/api/v1"
```

**Default:** If not set, frontend uses `http://localhost:8000/api/v1`

---

## API Endpoints Used by Frontend

### Health Check
```
GET /api/v1/health
```
**Purpose:** Check backend status  
**Frontend Use:** Sidebar health indicator

### Upload Recording
```
POST /api/v1/calls
```
**Body:** Multipart form with audio file  
**Returns:** `{ "call_id": "...", "status": "queued" }`  
**Frontend Use:** Upload page

### Get Call Status
```
GET /api/v1/calls/{call_id}/status
```
**Returns:** `{ "status": "queued|processing|completed|failed" }`  
**Frontend Use:** Progress polling

### Get Analysis Report
```
GET /api/v1/calls/{call_id}/report
```
**Returns:** Complete analysis with transcript, risk level, findings  
**Frontend Use:** Results display  
**Status 425:** Analysis still in progress

### List Calls
```
GET /api/v1/calls?page=1&page_size=20
```
**Returns:** Paginated call history  
**Frontend Use:** History page

### Get Transcript
```
GET /api/v1/calls/{call_id}/transcript
```
**Returns:** Timestamped transcript segments  
**Frontend Use:** Transcript viewer

---

## CORS Configuration

**Why needed:** Browser security prevents frontend (localhost:8501) from calling backend (localhost:8000) without CORS headers.

**Backend CORS settings:**
```python
# app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,  # From .env
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**To add new frontend origins:**
```env
# backend/.env
CORS_ORIGINS=http://localhost:8501,http://localhost:3000,https://your-domain.com
```

---

## Integration Testing Checklist

### 1. Backend Health Check
```powershell
# Start backend
cd backend
python -m uvicorn app.main:app --reload

# Test in browser
http://localhost:8000/
http://localhost:8000/api/v1/health
http://localhost:8000/docs  # API documentation
```

**Expected:** JSON responses, no errors

### 2. Frontend Connection
```powershell
# Start frontend
cd web-dashboard
streamlit run app.py
```

**Check in browser (http://localhost:8501):**
- ✅ Sidebar shows "✅ Backend: HEALTHY"
- ✅ Backend version displayed
- ✅ No connection errors

### 3. File Upload Test
1. Navigate to "📤 Upload Recording"
2. Upload a test audio file (WAV/MP3/M4A)
3. Verify progress indicator appears
4. Wait for analysis to complete

**Expected:**
- Upload succeeds
- call_id returned
- Status polling works
- Results display after completion

### 4. Analysis History
1. Navigate to "📋 Analysis History"
2. Verify uploaded files appear
3. Click "View Report" on a completed call

**Expected:**
- Paginated list of calls
- Timestamps correct
- Status badges display
- Reports load properly

### 5. CORS Verification
**Open browser console (F12) while testing**

**✅ Good:** No CORS errors  
**❌ Bad:** `Access-Control-Allow-Origin` errors

**Fix if needed:** Add frontend URL to `CORS_ORIGINS` in backend `.env`

---

## Common Integration Issues

### Issue 1: Frontend shows "❌ Backend Unavailable"

**Cause:** Backend not running or wrong URL

**Solution:**
```powershell
# Check backend is running
curl http://localhost:8000/api/v1/health

# Check URL matches
$env:VISHWAS_API_URL
# Should be: http://localhost:8000/api/v1
```

### Issue 2: CORS Errors in Browser Console

**Error:**
```
Access to fetch at 'http://localhost:8000/api/v1/health' from origin 
'http://localhost:8501' has been blocked by CORS policy
```

**Solution:**
```env
# backend/.env
CORS_ORIGINS=http://localhost:8501,http://localhost:3000
```
Restart backend after changing `.env`

### Issue 3: Upload Fails with 413 Error

**Cause:** File too large

**Solution:**
```env
# backend/.env
MAX_UPLOAD_SIZE_MB=100  # Increase limit
```

### Issue 4: Analysis Stuck at "Processing"

**Mock Mode:** Should complete in ~2 seconds  
**Real Mode:** Can take 30-60 seconds for first run (model downloads)

**Check backend logs:**
```powershell
# Backend terminal shows processing logs
# Look for errors or "Analysis complete"
```

### Issue 5: Frontend Doesn't Refresh Status

**Solution:** Frontend polls every 2 seconds automatically. Check:
1. Browser console for errors
2. Backend health status in sidebar
3. Network tab shows polling requests

---

## Testing Workflow

### End-to-End Test (Mock Mode)

1. **Start Services:**
   ```powershell
   .\start-vishwas.ps1
   ```

2. **Open Frontend:**
   - Browser: http://localhost:8501
   - Verify backend health: ✅ HEALTHY

3. **Upload Test File:**
   - Use `backend/tests/fixtures/test_audio.wav` (if exists)
   - Or any WAV/MP3/M4A file

4. **Monitor Progress:**
   - Status changes: queued → processing → completed
   - Takes ~2-3 seconds in mock mode

5. **View Results:**
   - Risk level displayed
   - Transcript segments shown
   - Fraud indicators listed
   - Recommendations provided

6. **Check History:**
   - Navigate to Analysis History
   - Verify call appears in list
   - Click "View Report" works

### Real Mode Test (After Setup)

**Prerequisites:**
```powershell
# Install dependencies
cd backend
pip install faster-whisper torch speechbrain

# Configure
# Edit backend/.env: ANALYSIS_MODE=real
```

**Process:**
- Same as mock mode but takes 30-90 seconds
- First run downloads models (~600MB)
- Subsequent runs faster (models cached)

---

## Production Deployment

### Backend

**Requirements:**
- Python 3.9+
- PostgreSQL (recommended) or SQLite
- ffmpeg (for real mode)
- 2GB RAM minimum, 4GB recommended
- GPU optional (faster transcription)

**Environment:**
```env
DEBUG=false
DATABASE_URL=postgresql://user:pass@host:5432/vishwas
CORS_ORIGINS=https://your-frontend-domain.com
ANALYSIS_MODE=real
```

**Run with Gunicorn:**
```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### Frontend

**Requirements:**
- Python 3.9+
- 512MB RAM minimum

**Environment:**
```env
VISHWAS_API_URL=https://api.your-domain.com/api/v1
```

**Run:**
```bash
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

**Reverse Proxy (Nginx):**
```nginx
# Backend
location /api {
    proxy_pass http://localhost:8000;
}

# Frontend
location / {
    proxy_pass http://localhost:8501;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

---

## Security Considerations

### Backend

1. **CORS:** Only allow trusted frontend domains
2. **File Upload:** Validate file types and sizes
3. **Rate Limiting:** Add rate limiter middleware
4. **Authentication:** Add JWT tokens for production
5. **HTTPS:** Always use HTTPS in production

### Frontend

1. **API Keys:** Don't expose backend API keys
2. **Input Validation:** Validate before sending to backend
3. **Error Handling:** Don't expose stack traces to users
4. **Session Management:** Implement user sessions

---

## Monitoring

### Health Checks

**Backend:**
```bash
curl http://localhost:8000/api/v1/health
# Expected: {"status": "healthy", "version": "0.1.0"}
```

**Frontend:**
- Check sidebar indicator
- Should show green "✅ Backend: HEALTHY"

### Logs

**Backend Logs:**
```
INFO:     Started server process
INFO:     Waiting for application startup
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Frontend Logs:**
```
You can now view your Streamlit app in your browser.
Local URL: http://localhost:8501
Network URL: http://192.168.x.x:8501
```

---

## Development Tips

### Hot Reload

**Backend:** Add `--reload` flag
```bash
uvicorn app.main:app --reload
```
Changes to Python files auto-restart server

**Frontend:** Streamlit auto-reloads on file changes

### API Testing

**Interactive Docs:**
- http://localhost:8000/docs (Swagger UI)
- http://localhost:8000/redoc (ReDoc)

**Test endpoints without frontend:**
```bash
curl -X POST http://localhost:8000/api/v1/calls \
  -F "file=@test.wav"
```

### Database Inspection

```bash
cd backend
sqlite3 vishwas.db
.tables
SELECT * FROM call_records;
```

---

## Next Steps

1. ✅ **Integration Complete**
2. ⏭️ **Test with Real Audio** (after installing dependencies)
3. ⏭️ **Add Authentication** (JWT tokens)
4. ⏭️ **Deploy to Staging** (Docker/cloud)
5. ⏭️ **Production Deployment**

---

## Support

**Issues:**
- Backend errors: Check `backend/logs/` directory
- Frontend errors: Check Streamlit terminal output
- CORS issues: Verify CORS_ORIGINS in backend/.env

**Documentation:**
- Backend API: http://localhost:8000/docs
- Streamlit docs: https://docs.streamlit.io
- FastAPI docs: https://fastapi.tiangolo.com

**Testing:**
- Run backend tests: `cd backend && pytest tests/`
- Test PII masking: `pytest tests/test_pii_masking.py -v`
- Test M2 perception: `pytest tests/test_m2_perception.py -v`
