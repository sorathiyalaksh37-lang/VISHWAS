# VISHWAS - AI-Powered Voice Fraud Detection Platform

**VISHWAS** (Voice Intelligence System for Heightened Warning Against Scams) is an intelligent system designed to analyze authorized call recordings and help identify potential fraud, suspicious requests, impersonation attempts, threats, urgency tactics, and attempts to obtain sensitive information.

## 🎯 Current Status: Phase 6 Complete ✅

**All phases 1-6 integrated into a fully operational application:**

- ✅ **React + Vite TypeScript frontend** (modern web dashboard)
- ✅ **FastAPI backend** with real ASR and voice anti-spoof detection
- ✅ **Complete audio analysis pipeline** (Upload → ASR → Evidence → Trust Judge → Report)
- ✅ **v3 Trust Engine** with category scores, fired rules, and verification decisions
- ✅ **Voice anti-spoof detection** using deepfake-audio-wav2vec2 model
- ✅ **PII masking** for 7 data types (phone, email, account, etc.)
- ✅ **381 passing backend tests** (100% pass rate)
- ✅ **Deterministic Trust Judge** with hard safety floors
- ✅ **Android mobile application** (Kotlin + Jetpack Compose)
- ✅ **Database persistence** with backward compatibility

**See [PHASE6_INTEGRATION_REPORT.md](./PHASE6_INTEGRATION_REPORT.md) for complete documentation.**

---

## 🏗️ Architecture Overview

```
Recording Upload → Audio Preprocessing → ASR (Whisper) → PII Masking →
Evidence Extraction → Trust Graph → Voice Anti-Spoof → Trust Judge →
Database → API Response → React Dashboard
```

**Core Principle**: *"Agents propose. Rules decide. Humans verify."*

The deterministic Trust Judge has final authority. AI models provide evidence; rule-based scoring produces explainable risk assessments.

---

## 📁 Repository Structure

```
VISHWAS/
├── backend/                    # FastAPI backend (Python)
│   ├── app/
│   │   ├── api/routes/        # REST API endpoints
│   │   ├── audio/             # ASR + voice anti-spoof
│   │   ├── extractors/        # Evidence extraction + PII masking
│   │   ├── trust/             # Trust Graph + Trust Judge
│   │   ├── services/          # Real/mock analysis services
│   │   └── models/            # SQLAlchemy database models
│   ├── tests/                 # 381 passing tests
│   └── requirements.txt
├── vishwas-frontend/          # React + Vite web app (TypeScript)
│   ├── src/
│   │   ├── pages/             # Dashboard, Report, History
│   │   ├── services/          # API client
│   │   └── components/        # Reusable UI components
│   └── package.json
├── android-app/               # Android Kotlin application
├── sample_recordings/         # Demo audio files
└── docs/                      # Documentation
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.9+**
- **Node.js 18+**
- **Git**

### 1. Clone Repository

```bash
git clone https://github.com/sorathiyalaksh37-lang/VISHWAS.git
cd VISHWAS
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Unix/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Edit .env and set:
# ANALYSIS_MODE=mock    # For demo without model dependencies
# ANALYSIS_MODE=real    # For actual ASR + voice detection (requires models)
```

### 3. Frontend Setup (separate terminal)

```bash
cd vishwas-frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env

# .env content:
# VITE_API_URL=http://localhost:8000/api/v1
```

### 4. Start Services

```bash
# Terminal 1: Start backend
cd backend
source venv/bin/activate  # or venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2: Start frontend
cd vishwas-frontend
npm run dev
```

### 5. Access Application

- **React Dashboard**: http://localhost:5173
- **Backend API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/health

---

## 🧪 Testing

### Backend Tests

```bash
cd backend
source venv/bin/activate

# Run all tests
pytest tests/ --ignore=tests/test_m2_perception.py -v

# Run specific test categories
pytest tests/test_e2e_integration.py -v       # End-to-end tests
pytest tests/test_pii_masking.py -v           # PII masking tests
pytest tests/test_trust_engine_simple.py -v   # Trust Judge tests
pytest tests/test_phase4_voice_antispoof.py -v # Voice detection tests
```

**Results**: 381 passing, 17 skipped, 0 failed

### Frontend Tests

```bash
cd vishwas-frontend
# Frontend tests: TODO (manual testing currently)
```

---

## 📡 API Endpoints

### Core Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/health` | Health check |
| POST | `/api/v1/analyze/recording` | Upload audio for analysis |
| GET | `/api/v1/call/{id}/status` | Poll analysis status |
| GET | `/api/v1/call/{id}/state` | Get complete analysis report |
| GET | `/api/v1/calls` | List analyses (paginated) |
| GET | `/api/v1/calls/{id}/transcript` | Get transcript only |

### Trust Graph

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/contacts` | Create trusted contact |
| GET | `/api/v1/contacts` | List contacts |
| POST | `/api/v1/contacts/{id}/voiceprint` | Enroll voice sample |

**Full API documentation**: http://localhost:8000/docs

---

## 🔒 Security & Privacy

### Implemented Controls

✅ **PII Masking**: 7 data types (phone, email, card, account, CVV, Aadhaar, PAN)  
✅ **File Upload Validation**: Extension, size (50MB max), MIME type checking  
✅ **Path Traversal Protection**: Server-generated filenames  
✅ **SQL Injection Prevention**: SQLAlchemy ORM with parameterized queries  
✅ **CORS Restrictions**: Configured frontend origins only  
✅ **Safe Error Messages**: No stack traces exposed to clients

### Production Limitations

⚠️ **No Authentication/Authorization** - Local development only  
⚠️ **No Rate Limiting** - Vulnerable to abuse  
⚠️ **No Encryption at Rest** - Database and files unencrypted  
⚠️ **No Audit Logging** - PII access not tracked  
⚠️ **No Auto File Cleanup** - Manual retention management required

**This system is NOT production-ready**. See [Production Readiness Checklist](#-production-readiness) below.

---

## 🎭 Analysis Modes

### Mock Mode (Default)

```env
ANALYSIS_MODE=mock
```

- Fast demo mode (2-second delay)
- No model dependencies required
- Clearly labeled with `"analysis_mode": "mock"`
- Deterministic results for testing

### Real Mode

```env
ANALYSIS_MODE=real
```

**Requires**:
- faster-whisper (ASR): `pip install faster-whisper`
- transformers (voice): `pip install transformers`
- Model: Vansh180/deepfake-audio-wav2vec2

**Features**:
- Actual speech-to-text transcription
- Real deepfake audio detection
- Evidence extraction from transcripts
- Deterministic Trust Judge scoring

---

## 📊 Risk Assessment

### Risk Bands

- **LOW** (0-24): No significant fraud indicators
- **MEDIUM** (25-49): Some suspicious patterns
- **HIGH** (50-74): Multiple fraud indicators
- **CRITICAL** (75-100): Clear fraud attempt

### Category Scoring (v3)

| Category | Max Points | Detects |
|----------|------------|---------|
| Identity | 25 | Impersonation, authority claims, relationship fraud |
| Sensitive Requests | 30 | OTP, money, credentials, account access |
| Behavioral Pressure | 20 | Urgency, threats, secrecy demands |
| Channel Inconsistency | 15 | Unknown number, first-time caller |
| Voice | 10 | Deepfake/synthetic voice detection |

### Hard Safety Floors

1. **OTP + Unverified Channel** → Minimum score 75 (CRITICAL)
2. **Money + Secrecy + Identity Mismatch** → Minimum score 50 (HIGH)
3. **Relative Claim + Voice Spoof + Unverified** → Minimum score 50 (HIGH)

**These are deterministic rules, not AI predictions.**

---

## 🎨 Frontend Features

### Dashboard
- Total analyses count
- Risk distribution (LOW/MEDIUM/HIGH/CRITICAL)
- Recent analysis history
- Backend health status

### Analysis Report
- Risk score visualization (0-100)
- Category-level breakdown
- Fired rules with explanations
- Transcript with timestamps
- Voice anti-spoof status
- Evidence with severity badges
- Verification recommendations
- Safe next actions

### Call History
- Paginated list of all analyses
- Risk band and status filters
- Quick access to reports

---

## 📱 Android Application

Located in `android-app/` directory.

**Features**:
- Audio file upload
- Analysis status tracking
- Risk report viewing
- Material 3 design

**Backend URL Configuration**:
- Emulator: `http://10.0.2.2:8000`
- Physical device: `http://YOUR_LOCAL_IP:8000`

**See**: [android-app/README.md](./android-app/README.md)

---

## 📚 Documentation

- [Phase 6 Integration Report](./PHASE6_INTEGRATION_REPORT.md) - Complete architecture and verification
- [Phase 5 Complete](./PHASE5_COMPLETE.md) - Security audit and test fixes
- [Phase 4 Summary](./PHASE4_SUMMARY.md) - Voice anti-spoof integration
- [Phase 2 Complete](./PHASE2_COMPLETE.md) - Trust Engine and Judge
- [API Documentation](http://localhost:8000/docs) - Interactive OpenAPI docs

---

## 🚦 Production Readiness

### Required Before Production

**Security (HIGH PRIORITY)**:
- [ ] Authentication (OAuth2/JWT)
- [ ] Authorization (RBAC)
- [ ] Rate limiting
- [ ] Encryption at rest
- [ ] Audit logging
- [ ] HTTPS enforcement

**Operational (HIGH PRIORITY)**:
- [ ] Job queue (Celery/RQ)
- [ ] Monitoring (Prometheus/Grafana)
- [ ] Alerting
- [ ] Database backups
- [ ] File retention automation
- [ ] Load balancing

**Data Quality (MEDIUM)**:
- [ ] ASR accuracy validation (Hindi/Hinglish test set)
- [ ] Voice anti-spoof accuracy validation (labeled dataset)
- [ ] Evidence extraction benchmarks

**Compliance (VARIES)**:
- [ ] GDPR/DPDPA audit
- [ ] User consent tracking
- [ ] Right-to-deletion
- [ ] Data export

---

## 🔬 Technology Stack

### Backend
- **Framework**: FastAPI 0.115+
- **Database**: SQLAlchemy + SQLite (dev) / PostgreSQL (prod)
- **ASR**: faster-whisper (OpenAI Whisper)
- **Voice Detection**: transformers + Vansh180/deepfake-audio-wav2vec2
- **Audio**: ffmpeg / PyAV
- **Testing**: pytest

### Frontend
- **Framework**: React 19
- **Build Tool**: Vite 8
- **Language**: TypeScript 6
- **Styling**: TailwindCSS 4
- **Routing**: React Router 7
- **Icons**: lucide-react

### Android
- **Language**: Kotlin
- **UI**: Jetpack Compose
- **HTTP**: Retrofit
- **Async**: Coroutines

---

## 🤝 Contributing

This is a demonstration project for academic/research purposes.

**Development Workflow**:
1. Create feature branch from `main`
2. Make changes with tests
3. Run full test suite
4. Create pull request
5. Code review + CI checks
6. Merge to `main`

---

## 📄 License

Copyright © 2026 VISHWAS Team. All rights reserved.

**Important**: This system is for authorized call recording analysis only. Using this system to intercept live calls without consent is illegal in most jurisdictions.

---

## ⚠️ Important Disclaimers

### Legal
- Analyze **authorized recordings only**
- Cannot intercept live cellular calls
- User responsible for consent and legal compliance
- Not legal advice

### Technical
- **NOT production-ready** (see limitations above)
- ASR accuracy not validated on Hindi/Hinglish benchmarks
- Voice anti-spoof accuracy not validated (pending labeled dataset)
- No guarantees of fraud detection accuracy
- False positives and false negatives will occur

### Privacy
- Recordings may contain sensitive personal information
- PII masking reduces but does not eliminate all risks
- User responsible for data protection compliance
- No data sent to external services without configuration

---

## 📧 Contact

For questions, issues, or contributions:
- GitHub Issues: https://github.com/sorathiyalaksh37-lang/VISHWAS/issues
- Documentation: See `docs/` directory

---

## 🎯 Project Phases

- [x] **Phase 1**: Foundation and infrastructure
- [x] **Phase 2**: Trust Engine and deterministic Judge
- [x] **Phase 3**: ASR integration (faster-whisper)
- [x] **Phase 4**: Voice anti-spoof detection
- [x] **Phase 5**: Security audit and test cleanup
- [x] **Phase 6**: Full system integration (React + FastAPI)
- [ ] **Phase 7**: Production deployment (authentication, monitoring, scalability)
- [ ] **Phase 8**: Model accuracy validation and tuning

**Current Status**: Phase 6 Complete ✅

---

**Built with ❤️ for safer communications**
