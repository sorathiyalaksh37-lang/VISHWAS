# VISHWAS - AI-Powered Voice Fraud Detection Platform

<div align="center">

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.0-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-6.0-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-380%2B%20Passing%20(100%25)-brightgreen?style=flat-square&logo=pytest&logoColor=white)](https://pytest.org)
[![Architecture](https://img.shields.io/badge/Architecture-Deterministic%20Trust%20Engine-blueviolet?style=flat-square)](#-risk-assessment--trust-engine)

**VISHWAS** (*Voice Intelligence System for Heightened Warning Against Scams*) is an enterprise-grade multi-modal voice fraud detection and call intelligence platform. It analyzes audio streams and recordings to detect synthetic voice clones, impersonation attempts, social engineering tactics, financial coercion, and illicit credential harvesting in real time.

</div>

---

## ⚡ Key Highlights

- **Multi-Modal Threat Analysis**: Combines state-of-the-art acoustic deepfake detection (wav2vec2) with high-accuracy speech transcription (Whisper ASR) and behavioral NLP extractors.
- **Deterministic Trust Engine (v3)**: Hardened safety floors and transparent rule-based scoring ensure reliable, explainable, and zero-hallucination fraud evaluations.
- **Comprehensive PII Masking Engine**: Automatically redacts 7 critical data classes (Phone, Email, Credit Cards, Bank Accounts, CVV, Aadhaar, PAN) before transcript storage or analysis.
- **Multi-Platform Ecosystem**: Features a modern **React 19 + Vite** analyst dashboard alongside a native **Android** application built with Jetpack Compose.
- **Enterprise Test Coverage**: Backed by **380+ automated tests** verifying end-to-end analysis pipelines, edge cases, acoustic classifiers, and safety constraints.

---

## 🏗️ Architecture & Pipeline

```
┌─────────────────┐     ┌─────────────────────┐     ┌──────────────────────┐
│  Audio Ingestion │ ──> │ Audio Preprocessing │ ──> │ Faster-Whisper (ASR) │
└─────────────────┘     └─────────────────────┘     └──────────┬───────────┘
                                                               │
┌──────────────────────────────────────────────────────────────┘
│
▼
┌──────────────────┐     ┌─────────────────────┐     ┌──────────────────────┐
│ PII Masking (7x) │ ──> │ Evidence Extraction │ ──> │ Trust Graph Context  │
└──────────────────┘     └─────────────────────┘     └──────────┬───────────┘
                                                               │
┌──────────────────────────────────────────────────────────────┘
│
▼
┌──────────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│ Voice Anti-Spoof ML  │ ──> │ Deterministic Judge  │ ──> │ Database & Report   │
│  (Wav2Vec2 Detector) │     │  (Hard Safety Floors)│     │  (REST / WebSocket) │
└──────────────────────┘     └──────────────────────┘     └─────────────────────┘
```

### Core Design Principle: *"Agents Propose. Rules Decide. Humans Verify."*
AI neural models provide perceptual evidence (speech-to-text, acoustic spoof likelihood, and semantic cues), while the **deterministic Trust Judge** executes verifiable mathematical risk calculations with immutable safety floors.

---

## 📁 Repository Structure

```
VISHWAS/
├── backend/                    # FastAPI backend engine (Python 3.9+)
│   ├── app/
│   │   ├── api/routes/        # REST API endpoints (Health, Ingestion, Reports)
│   │   ├── audio/             # ASR pipeline + Deepfake acoustic classifier
│   │   ├── extractors/        # Behavioral evidence extractors + PII masking
│   │   ├── trust/             # Trust Graph memory + Deterministic Trust Judge
│   │   ├── services/          # Real-time orchestration & analysis services
│   │   └── models/            # SQLAlchemy database models
│   ├── tests/                 # 380+ comprehensive automated tests
│   └── requirements.txt
├── vishwas-frontend/          # Web dashboard (React 19, Vite, TypeScript, Tailwind)
│   ├── src/
│   │   ├── pages/             # Real-time Dashboard, Detailed Report, Audit History
│   │   ├── services/          # Type-safe API client & state management
│   │   └── components/        # Interactive security visualizers & score gauges
│   └── package.json
├── android-app/               # Native Android application (Kotlin, Jetpack Compose)
├── sample_recordings/         # Audio test vectors for verification
└── docs/                      # Architecture specifications and technical guides
```

---

## 🚀 Quick Start

### Prerequisites

- **Python**: 3.9 or higher
- **Node.js**: 18.0 or higher
- **Git**

### 1. Clone the Repository

```bash
git clone https://github.com/sorathiyalaksh37-lang/VISHWAS.git
cd VISHWAS
```

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv

# On Unix / macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

Set your desired analysis mode in `backend/.env`:
- `ANALYSIS_MODE=real`: Full neural pipeline with Whisper ASR + Wav2Vec2 voice spoof detector.
- `ANALYSIS_MODE=mock`: High-speed development & CI simulation mode.

### 3. Frontend Setup

In a separate terminal:

```bash
cd vishwas-frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
```

### 4. Run the Platform

```bash
# Terminal 1: Launch Backend Engine
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2: Launch Frontend Portal
cd vishwas-frontend
npm run dev
```

### 5. Access Interfaces

- **Security Analyst Dashboard**: [http://localhost:5173](http://localhost:5173)
- **Interactive OpenAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **System Health Endpoint**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

## 🧪 Testing & Quality Assurance

The platform enforces rigorous test coverage across audio processing, evidence extraction, PII redaction, and deterministic scoring rules.

```bash
cd backend
source venv/bin/activate

# Execute full automated test suite
pytest tests/ -v

# Target specific validation suites
pytest tests/test_e2e_integration.py -v         # Full End-to-End Analysis Pipeline
pytest tests/test_pii_masking.py -v             # PII Redaction & Sanitization
pytest tests/test_trust_engine_simple.py -v     # Deterministic Trust Judge Rules
pytest tests/test_phase4_voice_antispoof.py -v   # Acoustic Spoof Classifiers
```

**Test Status**: **380+ Passing Automated Tests (100% Pass Rate)**

---

## 📡 REST API Reference

### Call Intelligence & Ingestion

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| `GET`  | `/api/v1/health` | Service health status and neural model availability |
| `POST` | `/api/v1/analyze/recording` | Submit audio recording for multi-modal analysis |
| `GET`  | `/api/v1/call/{id}/status` | Check real-time processing and pipeline status |
| `GET`  | `/api/v1/call/{id}/state` | Fetch complete forensic report with evidence graph |
| `GET`  | `/api/v1/calls` | Paginated repository of historical call analyses |
| `GET`  | `/api/v1/calls/{id}/transcript` | Retrieve PII-redacted call transcript |

### Trust Graph & Caller Verification

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| `POST` | `/api/v1/contacts` | Register authorized caller or trusted profile |
| `GET`  | `/api/v1/contacts` | Query verified identity network |
| `POST` | `/api/v1/contacts/{id}/voiceprint` | Enroll caller acoustic voiceprint for matching |

Interactive documentation, request payloads, and response schemas are available at `/docs`.

---

## 📊 Risk Assessment & Trust Engine

### Calibrated Risk Bands

| Tier | Score Range | Threat Classification | Recommended Action |
|:---|:---:|:---|:---|
| **LOW** | 0 – 24 | Normal conversation profile | Routine log retention |
| **MEDIUM** | 25 – 49 | Minor anomalies or unverified identity claims | Caution advise / Verification advised |
| **HIGH** | 50 – 74 | Multiple coordinated fraud signatures | Active warning / Hold transactions |
| **CRITICAL** | 75 – 100 | Severe scam patterns detected | Immediate intervention / Call termination |

### Multi-Dimensional Scoring Dimensions (v3)

| Dimension | Weight | Target Indicators |
|:---|:---:|:---|
| **Identity Authenticity** | 25 pts | Authority impersonation (bank/police), relationship spoofing, unverified affiliation |
| **Sensitive Data Solicitations** | 30 pts | OTP extraction, wire transfer demands, credential phishing, PIN harvesting |
| **Behavioral Coercion** | 20 pts | Artificial urgency, extortion, threats, isolation/secrecy demands |
| **Channel Consistency** | 15 pts | Caller ID spoofing, unknown number, atypical calling hour/vector |
| **Acoustic Anti-Spoofing** | 10 pts | Synthetic voice, AI clone artifacts, vocoder frequency fingerprints |

### Immutable Hard Safety Floors

To protect against probabilistic model blindspots, VISHWAS enforces deterministic safety floors:
- **OTP Solicitation + Unverified Channel** $\rightarrow$ Guaranteed Floor of **75 (CRITICAL)**
- **Financial Transfer + Secrecy Coercion + Identity Anomaly** $\rightarrow$ Guaranteed Floor of **50 (HIGH)**
- **Relative Emergency Claim + Voice Spoof Detected** $\rightarrow$ Guaranteed Floor of **50 (HIGH)**

---

## 🛡️ Security, Privacy & Compliance

VISHWAS is architected around strict data privacy and zero-trust engineering standards:

- **Automated PII Neutralization**: Deep regex-based and semantic redaction strips Phone numbers, Email addresses, Credit Cards, Bank Accounts, CVV codes, Aadhaar numbers, and PAN cards before persisting records.
- **Strict Ingestion Validation**: Multi-layer upload validation covering MIME type verification, file extension whitelisting, and a strict 50 MB payload ceiling.
- **Zero-Exposure Diagnostics**: Sanitized client error responses prevent any internal stack-trace leakage.
- **SQL Injection Immune**: Built entirely atop SQLAlchemy ORM with fully parameterized queries.
- **Path Traversal Defenses**: Deterministically generated UUIDs govern all server-side file management.
- **Configurable Access Isolation**: Strict CORS controls isolate backend APIs to trusted frontend domains.

---

## 💻 Client Applications

### 🌐 Web Dashboard (React 19 + TypeScript)
- **Live Threat Monitor**: Comprehensive analytics with risk band distributions and active pipeline diagnostics.
- **Deep Forensic Inspector**: Visualized 0-100 score gauges, category breakdowns, timestamped PII-redacted transcripts, and fired heuristic rules.
- **Interactive Call History**: Filterable, paginated audit trails of all analyzed interactions.

### 📱 Android Application (Kotlin + Jetpack Compose)
- Native mobile client with Material 3 design for on-the-go analysis ingestion, alert notifications, and report visualization.
- Configurable for local Wi-Fi testing, emulator networking (`10.0.2.2`), or remote production servers.

---

## 🔬 Core Technology Stack

- **Backend Framework**: FastAPI, Uvicorn, Python 3.9+
- **Machine Learning & Audio**: Faster-Whisper, PyTorch, Hugging Face Transformers (`deepfake-audio-wav2vec2`), PyAV, FFmpeg
- **Data Architecture**: SQLAlchemy, SQLite / PostgreSQL
- **Frontend Core**: React 19, Vite, TypeScript, TailwindCSS, Lucide Icons, React Router 7
- **Mobile Stack**: Kotlin, Jetpack Compose, Retrofit 2, Kotlin Coroutines
- **Test Infrastructure**: Pytest, Pytest-Asyncio, HTTPX

---

## 🗺️ Architectural Roadmap

- [x] High-performance Faster-Whisper ASR integration
- [x] Acoustic deepfake and voice clone detection via Wav2Vec2
- [x] 7-vector PII redaction pipeline
- [x] v3 Deterministic Trust Engine with immutable safety floors
- [x] React 19 analyst dashboard & native Android app
- [ ] Distributed task execution (Celery / Redis) for high-concurrency ingestion
- [ ] Multi-lingual speech models fine-tuned for regional dialects
- [ ] Streaming WebSocket integration for real-time live-call analysis

---

## ⚖️ Ethical AI & Usage Statement

VISHWAS is designed to safeguard individuals and organizations from voice fraud, social engineering, and synthetic identity deception. The platform must be operated in accordance with telecommunications regulations and privacy statutes. Users are responsible for ensuring that call analysis is conducted in compliance with applicable local consent laws.

---

## 📄 License

Copyright © 2026 VISHWAS Team. Released under the Apache 2.0 / MIT License.
