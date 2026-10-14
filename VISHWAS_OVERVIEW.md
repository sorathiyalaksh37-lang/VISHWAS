# VISHWAS: Voice Intelligence System for Heightened Warning Against Scams

> **Core Philosophy**: *"Agents propose. Rules decide. Humans verify."*  
> An enterprise-grade, privacy-first, multi-modal AI platform designed to detect telephony fraud, social engineering, impersonation, and synthetic voice clones (deepfakes).

---

## 1. Executive Summary

**VISHWAS** is an end-to-end AI security and fraud prevention platform tailored to counter modern voice-based attacks, including AI voice cloning, deepfake audio, and social engineering scams (such as "digital arrest", bank impersonation, and urgency-driven extortion). 

Engineered specifically with Indian telephony nuances and Hinglish (code-mixed Hindi + English) conversational tactics in mind, VISHWAS simultaneously evaluates two critical vectors:
1. **Perceptual Acoustic Integrity**: *"Does this audio exhibit synthetic voice-clone artifacts, or does the voice fail to match the claimed person's enrolled biometric voiceprint?"*
2. **Behavioral & Contextual Legitimacy**: *"Does the caller's story, requests, and pressure tactics match known scam kill-chains, and do their claims contradict verified records in the user's Trust Graph?"*

Rather than allowing generative AI to hallucinate risk classifications, VISHWAS couples multi-model perceptual layers with a **deterministic Trust Judge** featuring hard safety floors and cryptographic audit hashes.

---

## 2. High-Level Architecture

```
                    ┌──────────────────────────────┐
                    │     Client Applications      │
                    │  ┌────────────────────────┐  │
                    │  │ React + Vite Dashboard │  │
                    │  │ Android Native (Kotlin)│  │
                    │  └────────────────────────┘  │
                    └──────────────┬───────────────┘
                                   │ HTTP / WebSocket
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend Engine                          │
│                                                                        │
│  [1] INGESTION & INTEGRITY                                             │
│      ├── Streaming SHA-256 Audio Integrity Hashing                     │
│      ├── Telephony Codec Normalization (16kHz mono WAV via ffmpeg/AV)  │
│      └── Dual Input: Batch Recording Upload & Live 2s Streaming Chunks │
│                                                                        │
│  [2] PARALLEL PERCEPTION LAYER                                         │
│      ├── Speech-to-Text: faster-whisper (CTranslate2, int8, VAD)       │
│      │   └── Code-mixed language detection (English, Hindi, Hinglish)   │
│      └── Voice Anti-Spoof & Biometrics:                                │
│          ├── Check A: wav2vec2 / AASIST synthetic speech detection    │
│          └── Check B: SpeechBrain ECAPA-TDNN speaker voiceprint match   │
│                                                                        │
│  [3] PRIVACY & DATA PROTECTION                                         │
│      ├── PII Masker: Redaction of OTPs, cards, CVVs, Aadhaar, PAN      │
│      └── Embedding Storage: Raw audio discarded, voiceprints secured   │
│                                                                        │
│  [4] MULTI-TIER EVIDENCE EXTRACTION                                    │
│      ├── Tier 1: Instant Regex & TF-IDF/LogReg pattern matching        │
│      ├── Kill-Chain Tracker: FSM stages (Contact→Trust→Urgency→Request)│
│      └── Claim vs. Trust Graph Contradiction Engine                    │
│                                                                        │
│  [5] DECISION & EXPLAINABILITY ENGINE                                  │
│      ├── Deterministic Trust Judge (Capped Parameter Scoring: 0–100)   │
│      ├── Safety Floors: Non-negotiable minimum risk on toxic combos    │
│      ├── Counterfactual Reasoning: Provable risk delta calculations     │
│      └── Fraud vs. Skeptic Agent Debate (Advisory on MEDIUM risk)      │
│                                                                        │
│  [6] PERSISTENCE & AUDIT                                               │
│      ├── SQLite / SQLAlchemy with User Ownership Isolation             │
│      └── Audit Hash: SHA-256(evidence + rules_version)                 │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Key Differentiators & Unique Capabilities

### 🛡️ Dual-Check Voice Layer (Clone & Deepfake Detection)
- **Check A (Synthetic Audio Detection)**: Slices speech into 4–6 second windows using Voice Activity Detection (VAD) and feeds them into fine-tuned Wav2Vec2 / AASIST models to detect generative voice-synthesis artifacts (calculating median spoof probabilities).
- **Check B (Voice Biometric Matching)**: Compares speaker embeddings against enrolled voiceprints saved in the user's **Trust Graph** using cosine similarity (ECAPA-TDNN), alerting users when a caller claims to be a relative (e.g., "Mummy bol rahi hoon") but the acoustic signature differs.

### ⚖️ Deterministic Trust Judge & Hard Safety Floors
- Unlike pure LLM-based classifiers that hallucinate and shift unpredictably, the final score (0–100) and risk level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) are computed by a deterministic rule engine.
- **Category Scoring Caps (Total: 100)**:
  - **Identity** (Cap: 25): Unsaved caller, caller ID spoofing, claim contradiction.
  - **Request** (Cap: 30): Asking for OTP, remote access software, funds transfer.
  - **Behavior** (Cap: 20): Artificial urgency, threats of arrest/penalties, secrecy demands.
  - **Channel** (Cap: 15): Suspicious VoIP headers, abnormal call hours, spoof flags.
  - **Voice** (Cap: 10): Deepfake synthesis probability score.
- **Safety Floors**: When high-threat combinations occur (e.g., *unsaved number + OTP request*), the score is immediately locked to a safety floor (e.g., minimum score 75 - `CRITICAL`), regardless of other mitigating factors.

### 🔍 Provable Counterfactual Explanations
- Instead of generating text justifications, the platform calculates exact counterfactual alternatives:
  > *"If this call had originated from Mom's saved phone number, the risk score would drop from 82 (CRITICAL) to 15 (LOW)."*
- Generated by programmatically re-running the deterministic judge with swapped parameters.

### 🇮🇳 Hinglish-First Telephony Scam Recognition
- Specifically tuned to identify prevalent Indian fraud archetypes:
  - **Digital Arrest**: False police, CBI, ED, and customs intimidation.
  - **Urgent Financial Coercion**: Electricity bill disconnects, KYC update threats, SIM deactivation notices.
  - **Code-Mixed Phrasing**: Pre-trained patterns capturing nuances like *"OTP bata do"*, *"kisi ko mat batana"*, *"account block ho jayega"*.

### 🔒 Enterprise Privacy & PII Masking
- Automated regex and NLP redaction for 7 distinct sensitive data types: Phone Numbers, Email Addresses, Credit/Debit Card Numbers, Bank Account Numbers, CVV Codes, Aadhaar Numbers (12 digits), and PAN Cards (10 alphanumeric characters).
- Sanitized before passing to downstream advisory agents or reports.

### 🎭 Multi-Agent Adversarial Debate (Advisory)
- For ambiguous calls scoring in the `MEDIUM` tier (25–49), an autonomous **Fraud Agent** and a **Skeptic Agent** debate the interaction, surfacing edge-case considerations for human operators without overriding the deterministic score.

---

## 4. Technology Stack

| Layer | Technologies Used |
|---|---|
| **Backend Framework** | Python 3.11+, FastAPI, Uvicorn, Pydantic v2 |
| **Audio Processing & Speech** | `faster-whisper` (CTranslate2), `ffmpeg`, `PyAV`, `webrtcvad` |
| **Voice ML / Anti-Spoof** | PyTorch, `transformers` (Wav2Vec2), `speechbrain` (ECAPA-TDNN) |
| **Database & ORM** | SQLite, SQLAlchemy, Alembic migration scripts |
| **Security & Auth** | JWT (`python-jose`), Passlib (bcrypt), SHA-256 integrity streaming |
| **Web Frontend** | React 18, Vite, TypeScript, Lucide Icons, Glassmorphic CSS |
| **Mobile Application** | Native Android, Kotlin, Jetpack Compose, Retrofit, Room DB |
| **Testing & CI** | `pytest`, `pytest-asyncio` (380+ automated tests) |

---

## 5. Repository Layout

```
VISHWAS/
├── backend/
│   ├── app/
│   │   ├── agents/          # Fraud & Skeptic debate agents
│   │   ├── api/routes/      # REST API endpoints (calls, auth, analyze, live)
│   │   ├── audio/           # ASR (Whisper), Voice Layer, AASIST, Codec handling
│   │   ├── auth/            # JWT authentication, password hashing, dependencies
│   │   ├── database/        # Session and connection pooling
│   │   ├── extractors/      # PII masking, Hinglish patterns, Tier 1 classifiers
│   │   ├── models/          # SQLAlchemy ORM models (CallRecord, AnalysisReport, User, Contact)
│   │   ├── schemas/         # Pydantic v2 validation contracts
│   │   ├── services/        # Orchestration services (real & mock analysis)
│   │   └── trust_engine/    # Trust Graph, Parameter Scorer, Deterministic Judge
│   ├── tests/               # Over 380 unit and end-to-end integration tests
│   └── requirements.txt     # Python backend dependencies
├── vishwas-frontend/        # React + Vite TypeScript SPA
│   ├── src/
│   │   ├── components/      # UI components (AudioPlayer, Timeline, ScoreBadge)
│   │   ├── contexts/        # AuthContext and state management
│   │   ├── pages/           # Dashboard, LiveAnalysis, Report, TrustGraph, Privacy
│   │   └── services/        # REST & WebSocket API clients
│   └── package.json
├── android-app/             # Jetpack Compose mobile client
│   └── app/src/main/java/   # Kotlin source code, API services, local Room cache
├── sample_recordings/       # Test audio files representing scam and clean scenarios
├── docs/                    # Architecture diagrams, API contracts, setup guides
├── start.py / stop.py       # Cross-platform orchestration scripts
└── README.md                # Project documentation
```

---

## 6. API Reference (Core Endpoints)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | User signup with hashed credentials |
| `POST` | `/api/v1/auth/login` | JWT bearer token generation |
| `POST` | `/api/v1/calls` | Upload audio recording (`multipart/form-data`) + streaming SHA-256 |
| `GET` | `/api/v1/calls/{id}/status` | Check processing stage (`queued`, `processing`, `completed`, `failed`) |
| `GET` | `/api/v1/calls/{id}/report` | Fetch finalized `AnalysisReport` with score, reasons, and timeline |
| `WS` | `/api/v1/ws/audio/{id}` | Real-time WebSocket audio streaming for live in-call intervention |
| `GET` | `/api/v1/contacts` | Retrieve trusted contacts and enrolled voiceprints |
| `POST` | `/api/v1/contacts/{id}/voiceprint` | Enroll reference audio embedding for a contact |

---

## 7. How to Run Locally

### Quick Start (Automated Script)
```bash
python start.py
```

### Manual Setup

1. **Backend**:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate       # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env
   # Set ANALYSIS_MODE=mock (lightweight) or ANALYSIS_MODE=real (downloads models)
   python -m uvicorn app.main:app --reload --port 8000
   ```
   - OpenAPI Swagger Docs: `http://localhost:8000/docs`

2. **Frontend**:
   ```bash
   cd vishwas-frontend
   npm install
   npm run dev
   ```
   - Dashboard: `http://localhost:5173`

3. **Running the Test Suite**:
   ```bash
   cd backend
   pytest tests/ --ignore=tests/test_m2_perception.py -v
   ```
