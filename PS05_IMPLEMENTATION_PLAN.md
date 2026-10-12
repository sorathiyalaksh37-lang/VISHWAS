# VISHWAS: PS05 Final Implementation Plan

**Positioning Statement:**  
VISHWAS doesn't ask "is this voice fake?" It asks "does this caller's story match what we know and can verify about them?" The AI extracts evidence, deterministic rules decide, and the human stays in control.

---

## Table of Contents

1. [Unique Features](#1-unique-features)
2. [End-to-End Pipeline](#2-end-to-end-pipeline)
3. [Key Components](#3-key-components)
4. [API Specification](#4-api-specification)
5. [Build Schedule (20 Hours)](#5-build-schedule-20-hours)
6. [Demo Script (3 Minutes)](#6-demo-script-3-minutes)
7. [Requirement Checklist](#7-requirement-checklist)
8. [Honesty Rules](#8-honesty-rules)

---

## 1. Unique Features

Each feature is buildable in the available time and maps to a PS05 requirement.

| # | Feature | What the Judge Sees | Build Effort |
|---|---------|-------------------|--------------|
| 1 | **Claim-vs-Graph Contradiction Engine** | Caller says "Mummy bol rahi hoon", but the Trust Graph shows Mom's saved number is different. The UI shows "Claim contradicts your records." | Low |
| 2 | **Counterfactual Explanation** | "If this call came from Mom's saved number, the score would drop from 70 to 15." Computed by re-running the deterministic Judge with changed input, so it's provably true. | Low (only possible because scoring is deterministic) |
| 3 | **Evidence-Linked Reasons** | Click any reason and the transcript jumps to the exact quote and timestamp, highlighted. | Low |
| 4 | **Risk Timeline Replay** | A chart of score over time with kill-chain markers: "First HIGH at 0:08, Critical at 0:12." Works for recordings and live calls. | Medium |
| 5 | **Kill-Chain Stage-Skipping Detection** | A stepper (Contact → Trust → Urgency → Request → Secrecy). A call that jumps straight to "send money" is flagged as abnormal. | Medium |
| 6 | **Guardian One-Tap Confirmation** | A family member gets an email link with "I know this call / This is suspicious." The answer appears live on the user's dashboard. | Medium |
| 7 | **Hinglish-First Scam Detection** | Patterns for code-mixed phrases ("OTP bata do", "kisi ko mat batana", "account band ho jayega"), tested against English and Hindi as well. | Medium |
| 8 | **Privacy-First Masking** | OTPs, card numbers and account numbers are masked before any text reaches the LLM. The UI shows "3 sensitive values masked." | Low |
| 9 | **Fraud vs Skeptic Debate (Advisory)** | Runs only on MEDIUM scores, shown in an "Explain" panel. It can't change the score. | Optional |
| 10 | **Audit Hash** | Every report stores hash(evidence + rules_version). The same input always gives the same output, and you can show it. | Low |

### Priority Order (if time is short)

Build **1, 2, 3, 4, and 8 first**. They have the most "wow" per hour.

---

## 2. End-to-End Pipeline

```
INPUT: 
  A) Recording upload
  B) Live mic stream (WebSocket)
  C) Simulated transcript
   ↓
[1] Audio Preparation
    - ffmpeg → 16 kHz mono WAV
    - Validation
    - 2s chunks (live mode)
   ↓
[2] Automatic Speech Recognition (ASR)
    - faster-whisper (base/small, int8, VAD)
    - Output: timestamped segments + language detection
   ↓
[3] PII Masking
    - OTP / card / account digits → tokens
    - Masked before LLM processing
   ↓
[4] Evidence Layer (Never Decides Risk)
    
    Tier 1: Instant Detection
    - Regex patterns
    - Trained TF-IDF/LogReg classifier
    - Immediate flags
    
    Tier 2: LLM Extractors
    - Claim extraction
    - Request extraction
    - Behavior extraction
    - Pydantic-validated JSON output
    - Each finding must cite: quote + timestamp
    - LLM down → regex fallback emits same JSON
   ↓
[5] Context Layer
    - Trust Graph (SQLite + NetworkX)
      → number_known, number_matches_claim
    - Channel Check
      → VERIFIED / UNKNOWN / MISMATCH
    - Contradiction Engine
      → claim vs records
    - Kill-Chain FSM
    - RAG (ChromaDB, ~20 curated docs)
      → top-3 above threshold, else "no match"
   ↓
[6] (Optional, MEDIUM only) Fraud vs Skeptic Review
    - Advisory only
    - Cannot change score
   ↓
[7] Trust Judge (Deterministic)
    - Caps + hard-rule floors
    - Output: score, level, fired rules
    - Counterfactual runner
    - Audit hash
   ↓
[8] Action Layer
    - Cross-channel verification
      (target from Trust Graph, never from caller)
    - Guardian alert + one-tap confirmation
    - Report saved to history
    - Export JSON/PDF
   ↓
OUTPUT: Web Dashboard and Android App (same API)
```

### Processing Modes

**Live Mode:**
- Rolling 6s window with 2s hop
- Re-runs steps 3–7 each hop
- Tier 1 fires immediately on partial text

**Recording Mode:**
- Processes segment by segment
- Still generates risk timeline

---

## 3. Key Components

### 3.1 Trust Graph

**Purpose:** Functional relationship and contact mapping (not a diagram)

**Data Structure:**

**Contacts:**
```json
{
  "name": "Mom",
  "relation": "mother",
  "saved_numbers": ["+919876543210"],
  "safe_word_hash": "sha256(...)",
  "typical_call_hours": [8, 22],
  "typical_amount": 5000
}
```

**Organizations:**
```json
{
  "name": "HDFC Bank",
  "official_numbers": ["+911800202020"],
  "official_app": "com.hdfc.bank"
}
```

**Channel Status Logic:**
- Saved number matching the claim → **VERIFIED**
- Unsaved number claiming a relative → **MISMATCH**
- Bank claim from non-official number → **MISMATCH**
- No identity claim → **UNKNOWN**

### 3.2 Scoring System (Corrected and Capped)

| Group | Cap | Examples |
|-------|-----|----------|
| **Identity / Relationship** | 25 | Unsaved number claims trusted contact +20<br>Safe word absent/failed +5 |
| **Sensitive Request** | 30 | OTP/PIN/password +30<br>Money transfer +15<br>KYC +15 |
| **Behavioral Pressure** | 20 | Urgency/threat +15<br>Secrecy +5<br>Unusual hour +5<br>Amount > 3× baseline +10 |
| **Channel Inconsistency** | 15 | Bank/govt claim on unverified number +15<br>New number for known relation +10 |
| **Voice (AASIST)** | 10 | +0 unless tested and reliable |

**Score Calculation:**
```
score = min(100, sum of capped groups)
```

**Hard-Rule Floors:**
- OTP/PIN request on non-VERIFIED channel → **≥ 75**
- Money request + secrecy + MISMATCH → **≥ 50**
- VERIFIED channel + no sensitive request → **≤ 24**

**Risk Levels:**
- **0–24:** Low
- **25–49:** Medium
- **50–74:** High
- **75–100:** Critical

**Reasons:** Templates tied to fired rules (LLM never writes the facts)

### 3.3 Cross-Channel Verification

**Claims a Relative:**
- Call their saved number
- Ask the safe word
- Or ask another trusted contact

**Claims a Bank/Government:**
- End the call
- Use the official app or number from organizations table

**Critical Level:**
- All of the above PLUS
- Guardian alert

### 3.4 Worked Live Example (Bank Impersonation)

| Time | Heard | Result |
|------|-------|--------|
| 0:03 | "I'm calling from your bank" | Number not in org table<br>→ identity +20, channel +15 = **35, Medium** |
| 0:08 | "Account blocked in 15 minutes" | Behavior +15 = **50, High** |
| 0:12 | "Share the OTP" | Tier 1 fires instantly<br>Request +30, floor 75 → total **80, Critical** |
| 0:14 | Context finishes | Reasons, RAG citation<br>"End call, open your bank app"<br>Counterfactual: "From bank's official number, this would score 45" |

---

## 4. API Specification

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/analyze/recording` | POST | Upload audio, returns call_id |
| `/ws/audio/{call_id}` | WebSocket | Live 2s chunks, ordered by chunk_id |
| `/transcript/simulate` | POST | Scenario input (fallback mode) |
| `/call/{id}/state` | GET | Transcript, evidence, score, timeline, kill-chain |
| `/call/{id}/counterfactual` | GET | "What would make this safe?" |
| `/calls` | GET | History list |
| `/call/{id}/export` | GET | Export report (JSON/PDF) |
| `/alert/guardian` | POST | Send guardian alert |
| `/guardian/{token}` | GET | One-tap confirmation response |

### Error Format

```json
{
  "error": {
    "code": "ASR_FAILURE",
    "message": "Speech recognition failed",
    "retryable": true
  }
}
```

### Error Handling Requirements

- Empty audio
- Unsupported file formats
- ASR failure
- LLM timeout → fall back to regex

---

## 5. Build Schedule (20 Hours)

**Team:** 4 members (M1, M2, M3, M4)

### Hours 1–2: Foundation

**Work:**
- Repository setup
- `models.py` (Pydantic contracts)
- `scenarios.json` (5 scam + 2 legit)
- `trust_seed.json`
- Mock endpoint

**Exit Check:**
- `/docs` loads
- Mock report returned

---

### Hours 3–6: Core Modules

**M2:** FastAPI + faster-whisper integration  
**M3:** Extractors, regex fallback, Judge with unit tests  
**M4:** Dashboard skeleton, Trust Graph loader, RAG ingest  
**M1:** Mic client, WAV fallback

**Exit Check:**
- Each module works standalone
- Judge tests pass

---

### Hours 7–10: Thin Loop

**Work:**
- Simulated transcript → extract → Judge → dashboard
- PII masking implementation

**Exit Check:**
- Scenario 1 shows level + reasons correctly

---

### Hours 11–14: Context Integration

**Work:**
- Trust Graph + channel check
- Contradiction Engine
- Kill-Chain FSM
- RAG integration
- Counterfactuals
- Verification prompt generation

**Exit Check:**
- Legit scenario → LOW
- Scenarios 1 and 5 → HIGH/CRITICAL

---

### Hours 15–17: Full Pipeline

**Work:**
- Recording upload integration
- Live mic into same pipeline
- Rolling window processing
- Risk timeline generation
- Guardian email + one-tap link
- `run.sh` script

**Exit Check:**
- Spoken scam line makes risk rise live

---

### Hours 18–19: Testing & Measurement

**Work:**
- Run all 7 scenarios
- Measure latency over ≥20 chunks
- WER on English/Hindi/Hinglish clips
- Precision/recall for classifier

**Exit Check:**
- Table of measured numbers only (no aspirational goals)

---

### Hour 20: Finalization

**Work:**
- Feature freeze
- Backup video
- Fresh-clone test

**Exit Check:**
- One-command start works

---

### Cut Order (If Behind Schedule)

Priority to cut (in order):
1. Fraud vs Skeptic debate
2. AASIST/emotion detection
3. Audit hash
4. Guardian email
5. Live mic
6. RAG

**Must-Have Core:**  
Simulated transcript → evidence → Trust Graph → Judge → dashboard

---

## 6. Demo Script (3 Minutes)

### 0:00–0:20 (20s): The Problem

"It's 2 AM. Your phone rings: 'Mummy, new number, send money.' Why voice detection alone fails."

### 0:20–1:20 (60s): The Accident Scam

**Show:**
- The transcript appearing
- Timeline rising (Medium → High → Critical)
- Clickable reason jumping to exact quote
- Verification prompt: "Call Mom's saved number"

### 1:20–1:40 (20s): Counterfactual

**Show:**
"From Mom's saved number, this drops to Low."

Demonstrates deterministic logic and explainability.

### 1:40–2:10 (30s): Legitimate Call

**Show:**
Legit call from saved number → LOW risk

"This shows it isn't a fear machine."

### 2:10–2:30 (20s): Guardian Confirmation

**Show:**
- Guardian taps "suspicious" on their phone
- Dashboard updates live

### 2:30–2:50 (20s): Limitations & Roadmap

**Honestly state:**
- Live mode uses speakerphone/VoIP (not cellular)
- Voice signal optional unless tested
- Advisory system only
- Future: Production deployment, cellular integration (with carrier API)

---

## 7. Requirement Checklist

Update as you build:

| PS05 Requirement | Implementation | Status |
|-----------------|----------------|--------|
| Trust Graph | SQLite + NetworkX, seeded | ☐ Pending |
| Channel Verification | channel_status + rules | ☐ Pending |
| Request Analysis | Regex/classifier + LLM + rules | ☐ Pending |
| Behavior Analysis | Urgency, secrecy, timing, amount baseline | ☐ Pending |
| Dynamic Trust Score | Caps + floors, unit-tested | ☐ Pending |
| Low/Med/High/Critical + Explanation | Templated, evidence-linked reasons | ☐ Pending |
| Cross-Channel Verification | Graph-derived callback/safe word/app | ☐ Pending |
| Recording Analysis | Upload → ASR → report | ☐ Pending |
| Live Mid-Call Warning | WebSocket mic (not cellular) | ☐ Pending |
| Voice-Clone Signal | AASIST | ☐ Only if tested |

---

## 8. Honesty Rules

**These protect your score and maintain integrity:**

### 1. Cellular Call Audio Limitation

**Reality:** Cellular call audio is **inaccessible** on Android without root access or carrier API.

**Our Approach:**
- Live mode uses **speakerphone or VoIP**
- Clearly stated on demo slide
- Documented in limitations

### 2. Voice Signal

**Reality:** AASIST requires extensive testing for reliability.

**Our Approach:**
- Voice signal is **optional**
- Scored **+0 unless tested and validated**
- Never claim voice-clone detection without proof

### 3. Measurement Reporting

**Rules:**
- Report **only measured numbers**
- Label cost and accuracy **goals as targets**
- Never claim untested performance
- Provide confidence intervals where applicable

### 4. System Limitations

**Clearly State:**
- System is **advisory only**
- Never auto-blocks a call
- Human stays in control
- Requires user judgment

### 5. LLM Role

**Rules:**
- LLM **never outputs the score**
- LLM only extracts evidence
- Scoring is **deterministic and rule-based**
- Reasons are **templated**, not generated

### 6. Transparency

**Provide:**
- Open methodology
- Audit hash for reproducibility
- Evidence citations
- Counterfactual explanations

---

## Implementation Notes

### Technology Stack

**Backend:**
- FastAPI
- faster-whisper (ASR)
- SQLite + SQLAlchemy
- NetworkX (Trust Graph)
- ChromaDB (RAG)
- Pydantic (validation)

**Frontend:**
- Streamlit (Web Dashboard)
- Android App (Kotlin + Jetpack Compose)

**ML/AI:**
- TF-IDF + LogisticRegression (Tier 1)
- LLM (evidence extraction only)
- Optional: AASIST (if validated)

### File Structure

```
vishwas/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── analyze.py
│   │   │   │   ├── live.py
│   │   │   │   └── guardian.py
│   │   │   └── websocket.py
│   │   ├── core/
│   │   │   ├── asr.py
│   │   │   ├── pii_masker.py
│   │   │   └── audio_processor.py
│   │   ├── evidence/
│   │   │   ├── tier1_classifier.py
│   │   │   ├── tier2_extractors.py
│   │   │   └── fallback.py
│   │   ├── context/
│   │   │   ├── trust_graph.py
│   │   │   ├── channel_checker.py
│   │   │   ├── contradiction.py
│   │   │   ├── kill_chain.py
│   │   │   └── rag.py
│   │   ├── judge/
│   │   │   ├── scoring.py
│   │   │   ├── counterfactual.py
│   │   │   └── audit.py
│   │   ├── actions/
│   │   │   ├── verification.py
│   │   │   └── guardian.py
│   │   └── main.py
│   ├── data/
│   │   ├── scenarios.json
│   │   ├── trust_seed.json
│   │   └── scam_patterns.json
│   └── tests/
├── web-dashboard/
├── android-app/
└── docs/
    └── PS05_IMPLEMENTATION_PLAN.md
```

### Test Scenarios

**Scam Scenarios (5):**
1. Bank impersonation + OTP request
2. Accident scam (relative emergency)
3. Verification fraud (KYC)
4. Authority threat (police/legal)
5. Investment scam

**Legitimate Scenarios (2):**
1. Known contact from saved number
2. Expected callback (verified context)

### Performance Targets

**Latency Goals:**
- Tier 1 detection: < 100ms
- Full analysis (recording): < 5s
- Live chunk processing: < 500ms
- WebSocket latency: < 200ms

**Accuracy Goals:**
- False positive rate: < 5%
- True positive rate: > 90%
- WER (Whisper): < 15% on clean audio

**Resource Limits:**
- Max recording size: 100 MB
- Max recording duration: 10 minutes
- Live session timeout: 30 minutes

---

## Success Criteria

### Minimum Viable Product (MVP)

- [ ] Simulated transcript → full report
- [ ] Trust Graph matching working
- [ ] Contradiction detection working
- [ ] Risk timeline generation
- [ ] Evidence-linked reasons
- [ ] Counterfactual explanations
- [ ] PII masking functional
- [ ] Dashboard displays all features
- [ ] All 7 scenarios tested

### Full Feature Set

- [ ] Recording upload + analysis
- [ ] Live mic stream processing
- [ ] Guardian one-tap confirmation
- [ ] Kill-chain detection
- [ ] RAG integration
- [ ] Export functionality
- [ ] Mobile app integration

### Demo Ready

- [ ] 3-minute demo script rehearsed
- [ ] All demo scenarios working
- [ ] Backup video recorded
- [ ] Fresh-clone installation works
- [ ] `run.sh` one-command start

---

## Appendix: Quick Command Reference

### Setup

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.database.init_db

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_judge.py -v

# Measure latency
python scripts/benchmark.py
```

### Demo

```bash
# One-command start
./run.sh

# Simulate scenario
curl -X POST http://localhost:8000/transcript/simulate \
  -H "Content-Type: application/json" \
  -d @data/scenarios.json
```

---

**Document Version:** 1.0  
**Last Updated:** October 12, 2026  
**Status:** Ready for Implementation
