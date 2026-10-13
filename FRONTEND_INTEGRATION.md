# VISHWAS Frontend Integration Guide

Complete guide for integrating the React frontend dashboard with the backend API.

## 🎯 Overview

The VISHWAS system now has **two frontend options**:

1. **Streamlit Dashboard** (`web-dashboard/`) - Python-based, rapid prototyping
2. **React Dashboard** (`vishwas-frontend/`) - Production-ready TypeScript + Vite + Tailwind

This guide covers the **React Dashboard** integration.

## 📋 Prerequisites

### Required Software
- **Node.js 18+** (includes npm)
- **Python 3.9+** (for backend)
- **Git** (for version control)

### Check Installations
```powershell
node --version    # Should be v18.x.x or higher
npm --version     # Should be 9.x.x or higher
python --version  # Should be 3.9.x or higher
```

## 🚀 Quick Start

### Option 1: Automated Startup (Recommended)

```powershell
.\start-vishwas-full.ps1
```

This script will:
1. Check Node.js and Python installations
2. Install frontend dependencies (if needed)
3. Configure backend (.env file)
4. Start backend API on port 8000
5. Start React frontend on port 5173
6. Monitor both services

**Access the application:**
- Frontend Dashboard: http://localhost:5173
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Option 2: Manual Startup

#### 1. Start Backend
```powershell
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Start Frontend (in new terminal)
```powershell
cd vishwas-frontend
npm install          # First time only
npm run dev
```

### Stop Services

**With automation:**
```powershell
.\stop-vishwas-full.ps1
```

**Manual:**
- Press `Ctrl+C` in each terminal window

## 🏗️ Architecture

### Frontend Structure
```
vishwas-frontend/
├── src/
│   ├── components/         # Reusable UI components
│   │   ├── layout/        # Shell, Sidebar, Header
│   │   ├── overview/      # Dashboard widgets
│   │   ├── shared/        # Buttons, cards, uploads
│   │   └── trustgraph/    # Trust graph visualization
│   ├── pages/             # Main application pages
│   │   ├── Overview.tsx           # Dashboard home
│   │   ├── TrustGraphPage.tsx     # Trust network view
│   │   ├── AnalyseACall.tsx       # Upload & analyze
│   │   ├── AnalysisReport.tsx     # Results display
│   │   ├── CallHistory.tsx        # Past analyses
│   │   └── PrivacySettings.tsx    # Settings & health
│   ├── services/          # API integration layer
│   │   └── api.ts         # Backend HTTP client
│   ├── data/              # Mock data (for demo)
│   │   └── sampleData.ts
│   ├── App.tsx            # Root component
│   ├── App.css            # Global styles
│   └── main.tsx           # Entry point
├── .env                   # Configuration (API URL)
├── package.json           # Dependencies
└── vite.config.ts         # Build configuration
```

### API Client Architecture

The `src/services/api.ts` module provides:

```typescript
// Health check
apiClient.checkHealth() → HealthResponse

// Upload & analysis
apiClient.uploadRecording(file) → UploadResponse
apiClient.getCallStatus(callId) → CallStatusResponse
apiClient.getReport(callId) → AnalysisReportResponse

// History
apiClient.listCalls(page, pageSize) → CallListResponse
```

## 🔧 Configuration

### Environment Variables

Create `.env` in `vishwas-frontend/`:

```env
# Backend API URL
VITE_API_URL=http://localhost:8000/api/v1
```

**Production:** Update `VITE_API_URL` to your deployed backend URL.

### Backend Configuration

The backend should have `backend/.env` configured:

```env
# Analysis mode
ANALYSIS_MODE=mock          # Use 'mock' for testing without models
# ANALYSIS_MODE=real        # Use 'real' for production (requires dependencies)

# CORS Origins (must include frontend URL)
CORS_ORIGINS=http://localhost:5173,http://localhost:8501
```

## 📡 API Integration Details

### 1. Upload Audio File

**Frontend:**
```typescript
const result = await apiClient.uploadRecording(file)
// Returns: { call_id, status: 'queued', message, analysis_mode }
```

**Backend Endpoint:**
```
POST /api/v1/calls
Content-Type: multipart/form-data
```

### 2. Poll Analysis Status

**Frontend:**
```typescript
const status = await apiClient.getCallStatus(callId)
// Returns: { call_id, status: 'queued'|'processing'|'completed'|'failed' }
```

**Backend Endpoint:**
```
GET /api/v1/calls/{call_id}/status
```

**Status Flow:**
```
queued → processing → completed
                   → failed (on error)
```

### 3. Get Analysis Report

**Frontend:**
```typescript
const report = await apiClient.getReport(callId)
// Returns: Full analysis with risk level, reasons, transcript, etc.
```

**Backend Endpoint:**
```
GET /api/v1/calls/{call_id}/report
```

### 4. List Call History

**Frontend:**
```typescript
const history = await apiClient.listCalls(page, pageSize)
// Returns: { calls: [...], total, page, page_size }
```

**Backend Endpoint:**
```
GET /api/v1/calls?page=1&page_size=20
```

## 🎨 UI Components

### Analysis Flow (AnalyseACall.tsx)

```
User selects file
      ↓
Validates format (WAV, MP3, M4A)
      ↓
User clicks "Start Analysis"
      ↓
Frontend uploads to backend
      ↓
Frontend polls status every 1 second
      ↓
Shows: "Uploading..." → "Processing..." → "Complete!"
      ↓
User clicks "View Report"
```

### Call History (CallHistory.tsx)

**Features:**
- Real-time data from backend
- Filters: All / Completed / High Risk / Failed
- Sortable table with timestamps
- Status badges (queued, processing, completed, failed)
- Risk level badges (low, medium, high, critical)
- Refresh button

### Privacy & Settings (PrivacySettings.tsx)

**Features:**
- Backend health check (with live connection test)
- Interface preferences (compact layout toggle)
- Data handling transparency
- Connection status indicator

## 🧪 Testing

### Test Backend Health

```powershell
curl http://localhost:8000/api/v1/health
# Should return: {"status":"ok","service":"vishwas-api","version":"0.1.0"}
```

### Test File Upload

```powershell
curl -X POST http://localhost:8000/api/v1/calls `
  -F "file=@sample.wav" `
  -H "accept: application/json"
```

### Test Frontend

1. Open http://localhost:5173
2. Go to "Privacy & Settings"
3. Click "Check Backend Connection"
4. Should show "Backend connected • vishwas-api v0.1.0"

### End-to-End Test

1. **Upload:** Go to "Analyse a Call" → Select audio file → Click "Start Analysis"
2. **Monitor:** Watch status change: Uploading → Processing → Complete
3. **View:** Click "View Report" to see risk analysis
4. **History:** Go to "Call History" → See the uploaded file in the list
5. **Verify:** Check risk level badge matches the report

## 🐛 Troubleshooting

### Frontend can't connect to backend

**Symptoms:**
- "Connection failed" in Privacy Settings
- Upload fails immediately
- History page shows error

**Solutions:**
1. Verify backend is running: http://localhost:8000/api/v1/health
2. Check CORS configuration in `backend/.env`:
   ```env
   CORS_ORIGINS=http://localhost:5173,http://localhost:8501
   ```
3. Restart backend after changing CORS
4. Check browser console for CORS errors

### Upload succeeds but analysis fails

**Symptoms:**
- Status changes to "failed"
- Error message: "Analysis failed: Unknown error"

**Solutions:**
1. Check backend logs for errors
2. Verify file format is supported (WAV, MP3, M4A)
3. Check `ANALYSIS_MODE` in `backend/.env`
4. If using real mode, ensure dependencies are installed:
   ```powershell
   cd backend
   pip install -r requirements.txt
   ```

### Frontend shows old data after upload

**Solutions:**
1. Click the "Refresh" button in Call History
2. The frontend caches calls - refresh updates the list

### Port already in use

**Backend (port 8000):**
```powershell
# Find process
Get-NetTCPConnection -LocalPort 8000
# Kill it
Stop-Process -Id <PID> -Force
```

**Frontend (port 5173):**
```powershell
# Find process
Get-NetTCPConnection -LocalPort 5173
# Kill it
Stop-Process -Id <PID> -Force
```

### npm install fails

**Solutions:**
1. Clear npm cache: `npm cache clean --force`
2. Delete `node_modules`: `Remove-Item -Recurse -Force node_modules`
3. Delete `package-lock.json`: `Remove-Item package-lock.json`
4. Reinstall: `npm install`

## 📊 Analysis Modes

### Mock Mode (Default)

**Configuration:**
```env
ANALYSIS_MODE=mock
```

**Behavior:**
- No real AI/ML processing
- Returns sample data instantly
- Good for UI testing and development
- Simulates 2-second processing delay

**Sample Results:**
- Risk levels: Low / Medium / High
- Mock transcript with demo dialogue
- Sample fraud indicators

### Real Mode (Production)

**Configuration:**
```env
ANALYSIS_MODE=real
```

**Requirements:**
```powershell
cd backend
pip install -r requirements.txt
# Install ffmpeg separately (system dependency)
```

**Behavior:**
- Real audio transcription (faster-whisper)
- Voice analysis (speechbrain)
- PII masking (automatic)
- Processing time: 5-30 seconds depending on file size

## 🚀 Production Deployment

### Frontend Build

```powershell
cd vishwas-frontend
npm run build
# Output: dist/ folder (static files)
```

**Deploy to:**
- Vercel: `vercel --prod`
- Netlify: `netlify deploy --prod --dir=dist`
- AWS S3: Upload `dist/` folder
- Nginx: Serve `dist/` as static files

### Environment Variables (Production)

**Frontend `.env.production`:**
```env
VITE_API_URL=https://api.yourbackend.com/api/v1
```

**Backend `.env`:**
```env
CORS_ORIGINS=https://yourfrontend.com
ANALYSIS_MODE=real
TIER2_ENABLED=true
```

### Security Checklist

- [ ] Enable HTTPS for both frontend and backend
- [ ] Set proper CORS origins (no wildcards)
- [ ] Use API keys or JWT for authentication
- [ ] Rate limit file uploads
- [ ] Validate file sizes (MAX_UPLOAD_SIZE_MB=50)
- [ ] Enable audit logging
- [ ] Set up monitoring and alerts

## 📚 Additional Resources

### Frontend Development
- React: https://react.dev/
- Vite: https://vitejs.dev/
- Tailwind CSS: https://tailwindcss.com/
- TypeScript: https://www.typescriptlang.org/

### Backend API
- FastAPI: https://fastapi.tiangolo.com/
- API Documentation: http://localhost:8000/docs (when running)

### VISHWAS Documentation
- `README.md` - Project overview
- `backend/SETUP_REAL_MODE.md` - Real mode configuration
- `INTEGRATION_GUIDE.md` - Streamlit integration (legacy)

## 🔄 Migration from Streamlit

If you're currently using the Streamlit dashboard (`web-dashboard/`):

**Advantages of React Dashboard:**
- ✅ Faster performance (no page reloads)
- ✅ Modern UI with Tailwind CSS
- ✅ Better mobile responsiveness
- ✅ TypeScript type safety
- ✅ Production-ready build process
- ✅ Easier to customize and extend

**Coexistence:**
Both dashboards can run simultaneously:
- Streamlit: http://localhost:8501
- React: http://localhost:5173

Choose whichever fits your needs!

## 💡 Tips & Best Practices

### Development
1. Use `npm run dev` for hot-reload during development
2. Check browser console for errors
3. Use React DevTools for debugging
4. Monitor Network tab for API calls

### Performance
1. React dashboard is faster than Streamlit
2. API calls are cached where appropriate
3. File uploads stream directly to backend
4. History refreshes on demand, not automatic

### Accessibility
- All interactive elements have proper ARIA labels
- Keyboard navigation supported
- Screen reader compatible
- High contrast mode compatible

### Code Style
- TypeScript strict mode enabled
- ESLint for code quality
- Component-based architecture
- CSS follows BEM methodology

## 🆘 Getting Help

### Common Issues

**Q: Frontend compiles but shows blank page**
A: Check browser console for errors. Usually a component import issue.

**Q: Backend health check works but upload fails**
A: Verify `CORS_ORIGINS` includes your frontend URL.

**Q: Analysis stuck in "processing" forever**
A: Check backend logs. Database session bug might have returned.

**Q: Want to add a new feature**
A: Follow the component pattern in `src/components/` and `src/pages/`

### Contact

For VISHWAS-specific issues:
1. Check backend logs: `Get-Process | Where-Object {$_.Name -eq "python"}`
2. Check frontend console: Browser DevTools → Console
3. Review API docs: http://localhost:8000/docs

---

**Last Updated:** 2026-10-13  
**VISHWAS Version:** 0.1.0  
**Frontend Framework:** React 19 + Vite + TypeScript + Tailwind CSS

