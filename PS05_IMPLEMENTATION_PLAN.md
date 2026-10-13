# VISHWAS: PS05 Final Implementation Plan (v3 with Voice-Clone Detection)

**Positioning Statement:**  
VISHWAS asks two questions together: "Does this voice show signs of being synthetic or not match the claimed person?" and "Does the caller's story match what we know and can verify?" The AI extracts evidence, deterministic rules decide, and the human stays in control.

## What Changed from v2

1. **Voice-clone detection** is now a real evidence layer with two checks:
   - **Check A:** Synthetic-speech detection (AASIST or wav2vec2-based)
   - **Check B:** Voiceprint match against enrolled contacts
2. The **Judge** has voice rules and one voice-aware floor
3. A **voice enrollment endpoint** and screen are added
4. The **schedule and evaluation** now include voice validation
5. The **counterfactual examples** are corrected with proper arithmetic

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

## 1. Input Modes (One Pipeline)

| Mode | Source | Role |
|------|--------|------|
| **A. Recording upload** | WAV/MP3/M4A from web or Android | Primary. Fully satisfies PS05 |
| **B. Live stream** | Mic → WebSocket (2s chunks), via speakerphone or VoIP | Demonstrates mid-call warning |
| **C. Simulated transcript** | scenarios.json | Fallback if ASR or mic fails |

**Note:** Cellular call audio is not accessible on Android, so put that limitation on a slide. All modes produce the same `TranscriptSegment` objects, so nothing downstream cares which was used.

---

## 2. Unique Features

Each feature is buildable in the available time and maps to a PS05 requirement.

| # | Feature | What the Judge Sees | Build Effort |
|---|---------|-------------------|--------------|
| 1 | **Claim-vs-Graph Contradiction Engine** | Caller says "Mummy bol rahi hoon", but the Trust Graph shows Mom's saved number is different. The UI shows "Claim contradicts your records." | Low |
| 2 | **Claim-vs-Voiceprint Check (NEW)** | The caller claims to be Mom, but the voice similarity to Mom's enrolled voiceprint is low | Medium |
| 3 | **Counterfactual Explanation** | "From Mom's saved number this drops from 80 to 15." Computed by re-running the Judge, so it is provably true | Low |
| 4 | **Evidence-Linked Reasons** | Click any reason and the transcript jumps to the exact quote and timestamp, highlighted | Low |
| 5 | **Risk Timeline Replay** | A chart of score over time with kill-chain markers: "First HIGH at 0:08, Critical at 0:12." Works for recordings and live calls | Medium |
| 6 | **Kill-Chain Stage-Skipping Detection** | A stepper (Contact → Trust → Urgency → Request → Secrecy). A call that jumps straight to "send money" is flagged as abnormal | Medium |
| 7 | **Guardian One-Tap Confirmation** | A family member gets an email link with "I know this call / This is suspicious." The answer appears live on the user's dashboard | Medium |
| 8 | **Hinglish-First Scam Detection** | Patterns for code-mixed phrases ("OTP bata do", "kisi ko mat batana", "account band ho jayega"), tested against English and Hindi as well | Medium |
| 9 | **Privacy-First Masking** | OTPs, card numbers and account numbers are masked before any text reaches the LLM. Voice enrollment stores embeddings, not audio. The UI shows "3 sensitive values masked." | Low |
| 10 | **Audit Hash** | Every report stores hash(evidence + rules_version). The same input always gives the same output, and you can show it | Low |
| 11 | **Fraud vs Skeptic Debate (Advisory)** | Runs only on MEDIUM scores, shown in an "Explain" panel. It can't change the score | Optional |

### Priority Order (if time is short)

Build **1, 3, 4, 5, 9 and voice Check A first**. They have the most "wow" per hour.

---

## 3. End-to-End Pipeline

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
   ├──────────────► [V] VOICE LAYER (parallel, never blocks ASR)
   │                   VAD slice into 4–6s windows
   │                   Quality gate: duration, SNR, clipping → else "inconclusive"
   │                   Check A: spoof_prob per window → median
   │                   Check B: speaker similarity vs enrolled voiceprint
   │                   → VoiceEvidence JSON
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
      → claim vs saved number AND claim vs voiceprint
    - Kill-Chain FSM
    - RAG (ChromaDB, ~20 curated docs)
      → top-3 above threshold, else "no match"
   ↓
[6] (Optional, MEDIUM only) Fraud vs Skeptic Review
    - Advisory only
    - Cannot change score
   ↓
[7] Trust Judge (Deterministic)
    - Caps + hard-rule floors (including voice-aware floor)
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
- Voice result arrives a few seconds in and updates the score when ready

**Recording Mode:**
- Processes segment by segment
- Still generates risk timeline
- Voice layer runs in parallel with ASR

---

## 4. Data Contracts (backend/models.py)

Everyone imports from this file.

### Evidence Contracts

```json
{
  "claims": [
    {
      "type": "relative",
      "value": "mother",
      "quote": "Mummy bol rahi hoon",
      "t": 3.2,
      "confidence": 0.9
    }
  ],
  "requests": [
    {
      "type": "money_transfer",
      "amount": 50000,
      "quote": "...",
      "t": 11.0
    }
  ],
  "behavior": {
    "urgency": true,
    "secrecy": true,
    "emotional_pressure": true,
    "quotes": []
  }
}
```

### Voice Evidence Contract (NEW)

```json
{
  "voice": {
    "status": "ok" | "inconclusive" | "unavailable",
    "spoof_prob": 0.82,
    "windows_analyzed": 5,
    "speaker_match": {
      "claimed_contact": "Mom",
      "similarity": 0.41,
      "enrolled": true
    },
    "quality": {
      "duration_s": 18.4,
      "snr_db": 14.2
    },
    "model": "<model name and version>"
  }
}
```

### Final Report Contract

```json
{
  "call_id": "...",
  "score": 80,
  "level": "CRITICAL",
  "category_scores": {
    "identity": 25,
    "request": 15,
    "behavior": 15,
    "channel": 15,
    "voice": 10
  },
  "fired_rules": ["R_FAMILY_UNSAVED", "R_SPOOF_HIGH"],
  "reasons": [
    "Caller claimed to be Mom from an unsaved number",
    "Voice shows synthetic indicators (experimental)"
  ],
  "killchain_stage": "Request",
  "verification": {
    "action": "callback_saved_number",
    "target": "Mom (saved: +91-98xxxx)",
    "safe_word_prompt": true
  },
  "counterfactuals": [
    {
      "change": "call from Mom's saved number",
      "new_score": 15
    }
  ],
  "rag_citations": [],
  "limitations": [],
  "audit_hash": "..."
}
```

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

---

## 5. Key Components

### 5.1 Trust Graph

**Purpose:** Functional relationship and contact mapping (not a diagram)

**Data Structure:**

**SQLite Tables loaded into NetworkX:**

**Contacts:**
```json
{
  "name": "Mom",
  "relation": "mother",
  "saved_numbers": ["+919876543210"],
  "safe_word_hash": "sha256(...)",
  "typical_call_hours": [8, 22],
  "typical_amount": 5000,
  "voiceprint_embedding": null
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

**Edges:**
- `trusts`
- `uses_number`
- `official_channel_of`

**Channel Status Logic:**
- Saved number matching the claimed relation → **VERIFIED**
- Unsaved number claiming a relative → **MISMATCH**
- Bank claim from non-official number → **MISMATCH**
- No identity claim → **UNKNOWN**

### 5.2 Dynamic Trust Score (Capped, with Floors)

| Group | Cap | Rules |
|-------|-----|-------|
| **Identity / Relationship** | 25 | Unsaved number claims trusted contact +20<br>Safe word absent/failed +5<br>Conflicts with contact record +15 |
| **Sensitive Request** | 30 | OTP/PIN/UPI PIN/password +30<br>Money transfer +15<br>KYC/account details +15 |
| **Behavioral Pressure** | 20 | Urgency or threat +15<br>Secrecy +5<br>Unusual hour +5<br>Amount > 3× baseline +10 |
| **Channel Inconsistency** | 15 | Bank/govt claim on unverified number +15<br>New number for known relation +10 |
| **Voice (NEW)** | 10 | `status != ok` → 0<br>`spoof_prob ≥ 0.80` → +10<br>`spoof_prob 0.60–0.79` → +5<br>Speaker similarity below threshold for enrolled claimed contact → +5 (within cap) |

**Score Calculation:**
```
score = min(100, sum of capped groups)
```

**Hard-Rule Floors:**

| Floor | Condition |
|-------|-----------|
| **≥ 75** | OTP/PIN request on a non-VERIFIED channel |
| **≥ 50** | Money request + secrecy + MISMATCH |
| **≥ 50** | Relative claim + non-VERIFIED channel + spoof_prob ≥ 0.80 (voice-aware) |
| **≤ 24** | VERIFIED channel + no sensitive request |

**Risk Levels:**
- **0–24:** Low (Green)
- **25–49:** Medium (Yellow)
- **50–74:** High (Orange)
- **75–100:** Critical (Red)

**Voice Design Rules:**
1. **Soft signal:** Can raise risk, but at most 10 points. Voice alone can never produce Critical
2. **Never lowers score:** A "real voice" result never lowers the score, because a good clone can pass a detector
3. **Inconclusive handling:** Short audio, heavy noise, or low bitrate scores 0 and is noted in the report
4. **Thresholds are placeholders:** Set them from your own test data

**Reasons:** Templates tied to fired rules (LLM never writes the facts)

### 5.3 Reference Scenarios (All Arithmetic Checked)

| Scenario | Identity | Request | Behavior | Channel | Voice | Total | Level |
|----------|----------|---------|----------|---------|-------|-------|-------|
| Bank impersonation | 20 | 30 | 15 | 15 | 0 | 80 | Critical |
| Family emergency, no voice flag | 25 | 15 | 15 | 15 | 0 | 70 | High |
| Family emergency, cloned voice flagged | 25 | 15 | 15 | 15 | 10 | 80 | Critical |
| Delivery update | 0 | 0 | 0 | 12 | 0 | 12 | Low |

**Counterfactual Example (Family Emergency with Cloned Voice):**
- Current score: **80 (Critical)**
- Without synthetic-voice flag: **70 (High)**
- From Mom's saved number: **15 (Low)**

---

### 5.4 Voice Layer in Detail (NEW)

| Check | Question | Method |
|-------|----------|--------|
| **A. Synthetic-Speech Detection** | Does the audio show signs of generation or replay? | Pretrained anti-spoofing model (AASIST or wav2vec2-based deepfake classifier).<br>**Check model card and license first** |
| **B. Voiceprint Match** | Does the voice resemble the claimed contact's enrolled voice? | SpeechBrain ECAPA-TDNN embeddings and cosine similarity vs a 10–15s enrollment clip |

#### Implementation

```python
def analyze_voice(wav_path, claimed_contact=None):
    try:
        audio = load_16k_mono(wav_path)
        wins = vad_slice(audio, win_s=5, hop_s=2.5)
        
        if total_speech(wins) < 3.0 or snr(audio) < 5:
            return {"status": "inconclusive"}
        
        out = {
            "status": "ok",
            "spoof_prob": float(np.median([spoof_model(w) for w in wins]))
        }
        
        if claimed_contact and has_voiceprint(claimed_contact):
            out["speaker_match"] = {
                "similarity": cosine(embed(audio), voiceprint(claimed_contact))
            }
        
        return out
    except Exception:
        return {"status": "unavailable"}  # never break the pipeline
```

#### Key Points

1. **Runs as background task:** ASR and Tier 1 alerts are never delayed
2. **Enrollment stores embeddings only:** Not the audio
3. **Check B caveat:** High-quality clone may match voiceprint, so channel and request signals stay primary
4. **Quality gate:** Short duration, low SNR, or clipping → "inconclusive"

---

### 5.5 Cross-Channel Verification

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

## 6. API Specification

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/analyze/recording` | POST | Upload audio, returns call_id |
| `/ws/audio/{call_id}` | WebSocket | Live 2s chunks, ordered by chunk_id |
| `/transcript/simulate` | POST | Scenario input (fallback mode) |
| `/contacts/{id}/voiceprint` | POST | **Enroll a 10–15s clip, store the embedding** |
| `/call/{id}/state` | GET | Transcript, evidence, voice, score, timeline, kill-chain |
| `/call/{id}/counterfactual` | GET | "What would make this safe?" |
| `/calls` | GET | History list |
| `/call/{id}/export` | GET | Export report (JSON/PDF) |
| `/alert/guardian` | POST | Send guardian alert |
| `/guardian/{token}` | GET | One-tap confirmation response |

### Error Handling Requirements

Handle all of the following gracefully:
- Empty audio
- Unsupported file formats
- ASR failure
- **Voice-model failure**
- LLM timeout → fall back to regex

---

## 7. Build Schedule (20 Hours)

**Team:** 4 members (M1, M2, M3, M4)

### Hours 1–2: Foundation

**Work:**
- Repository setup
- `models.py` (Pydantic contracts including `VoiceEvidence`)
- `scenarios.json` (5 scam + 2 legit)
- `trust_seed.json`
- Mock endpoint

**Exit Check:**
- `/docs` loads
- Mock report returned

---

### Hours 3–6: Core Modules

**M2:** FastAPI + faster-whisper + **load spoof model and run it on one clip**  
**M3:** Extractors, regex fallback, Judge with unit tests  
**M4:** Dashboard skeleton, Trust Graph loader, RAG ingest  
**M1:** Mic client, WAV fallback

**Exit Check:**
- Each module works standalone
- Judge tests pass
- **Spoof model returns a probability**

---

### Hours 7–10: Thin Loop

**Work:**
- Simulated transcript → extract → Judge → dashboard
- PII masking implementation

**Exit Check:**
- Scenario 1 shows level + reasons correctly

---

### Hours 11–14: Context Integration + Voice

**Work:**
- Trust Graph + channel check
- Contradiction Engine
- Kill-Chain FSM
- RAG integration
- Counterfactuals
- Verification prompt generation
- **Voice: quality gate, windowing, ECAPA enrollment/similarity**
- **Judge voice rules + tests**

**Exit Check:**
- Legit scenario → LOW
- Scenarios 1 and 5 → HIGH/CRITICAL
- **Inconclusive path works**

---

### Hours 15–17: Full Pipeline + Voice UI

**Work:**
- Recording upload integration
- Live mic into same pipeline
- Rolling window processing
- Risk timeline generation
- Guardian email + one-tap link
- **Voice card + enrollment screen**
- `run.sh` script

**Exit Check:**
- Spoken scam line makes risk rise live
- **Voice result appears in both modes**

---

### Hours 18–19: Testing & Measurement

**Work:**
- Run all 7 scenarios
- Measure latency over ≥20 chunks
- WER on English/Hindi/Hinglish clips
- Classifier precision/recall
- **Voice test set (clean vs phone-quality)**

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
2. **Voiceprint (Check B)**
3. **Voice floor**
4. Audit hash
5. Guardian email
6. Live mic
7. RAG
8. **Spoof model (Check A)**

**Must-Have Core:**  
Simulated transcript → evidence → Trust Graph → Judge → dashboard

**Note:** If the voice layer fails, it degrades to "unavailable" and everything else still works.

---

## 9. Demo Script (3 Minutes)

### 0:00–0:20 (20s): The Problem

"It's 2 AM. Your phone rings: 'Mummy, new number, send money.'"

### 0:20–1:10 (50s): The Cloned-Voice Family Emergency

**Show:**
- Upload the cloned-voice family-emergency recording
- The transcript appearing
- The timeline rising
- **The voice card flagging it as synthetic**

### 1:10–1:30 (20s): Evidence-Linked Reasons + Counterfactual

**Show:**
- Click a reason → jumps to the quote
- Show the counterfactual: **"Without the voice flag, 70. From Mom's saved number, 15."**

### 1:30–1:55 (25s): Legitimate Call

**Show:**
- Upload a real call from a saved number → LOW
- **Voice card doesn't reduce or inflate anything**

"This shows it isn't a fear machine."

### 1:55–2:15 (20s): Guardian One-Tap

**Show:**
- Guardian taps "suspicious" on their phone
- Dashboard updates live

### 2:15–2:40 (25s): Limitations & Key Message

**Honestly state:**
- Live mode uses speakerphone/VoIP (not cellular)
- Voice detection is experimental
- Advisory system only

**Key line:**
"Even a perfect clone that fools our detector is still caught by the identity, channel and request signals."

---

## 10. Requirement Checklist

Update as you build. **Mark each as implemented, tested, or pending. Claim only what you've demonstrated.**

| PS05 Requirement | Implementation | Status |
|-----------------|----------------|--------|
| Trust Graph | SQLite + NetworkX, seeded contacts, orgs, safe word, voiceprints | ☐ Pending |
| Channel Verification | channel_status + rules | ☐ Pending |
| Request Analysis | Regex/classifier + LLM + rules | ☐ Pending |
| Behavior Analysis | Urgency, secrecy, timing, amount baseline | ☐ Pending |
| Dynamic Trust Score | Caps + floors, unit-tested | ☐ Pending |
| Low/Med/High/Critical + Explanation | Templated, evidence-linked reasons | ☐ Pending |
| Cross-Channel Verification | Graph-derived callback/safe word/app | ☐ Pending |
| Recording Analysis | Upload → ASR → report | ☐ Pending |
| Live Mid-Call Warning | WebSocket mic (not cellular) | ☐ Pending |
| Voice-Clone Detection | Check A (spoof) + Check B (voiceprint), soft signal | ☐ Pending |

---

## 11. Honesty Rules

**These protect your score and maintain integrity:**

### 1. Cellular Call Audio Limitation

**Reality:** Cellular call audio is **inaccessible** on Android without root access or carrier API.

**Our Approach:**
- Live mode uses **speakerphone or VoIP**
- Clearly stated on demo slide
- Documented in limitations

### 2. Voice Detection

**Reality:** Voice detection is probabilistic, experimental, and capped at 10 points.

**Our Approach:**
- Voice signal is a **soft signal only**
- Can raise risk but **cannot alone produce Critical**
- Report only **measured detection rates**
- Never claim 100% accuracy
- State degradation on phone-quality audio

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

### 7. Key Message for Demo

**Always include:**
"Even a perfect clone that fools our detector is still caught by the identity, channel and request signals."

This shows that voice is one layer in a multi-layered defense.

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

## 8. Evaluation

| What | How |
|------|-----|
| **Transcription** | WER on a few English, Hindi and Hinglish clips |
| **Fraud Classification** | 7-scenario table; precision/recall for the Tier 1 classifier on a held-out split |
| **Latency** | ASR time, Tier 1 time, time to first HIGH, over ≥20 chunks |
| **Voice Detection (NEW)** | **Real voices** from team members; **cloned versions** of consenting teammates' voices; each re-encoded to 8 kHz narrowband with noise. Report detection rate and false-positive rate separately for clean and phone-quality audio |

**Expected Behavior:**
- Expect a drop on phone audio
- If so, say it: "Works on clean audio, degrades on compressed telephony audio, so it is scored as a soft signal"
- **Never clone or test on anyone's voice without consent**

### Performance Targets

**Latency Goals:**
- Tier 1 detection: < 100ms
- Full analysis (recording): < 5s
- Live chunk processing: < 500ms
- WebSocket latency: < 200ms
- Voice layer (parallel): < 3s

**Accuracy Goals:**
- False positive rate: < 5%
- True positive rate: > 90%
- WER (Whisper): < 15% on clean audio
- Voice spoof detection: Report actual measured rates

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

**Document Version:** 3.0 (with Voice-Clone Detection)  
**Last Updated:** October 12, 2026  
**Status:** Ready for Implementation

---

## 12. Team Member Responsibilities

This section defines clear ownership and deliverables for each team member to ensure parallel progress and accountability.

### Member 1 — Android App + API Integration

**Owns:** `android-app/`

**Responsibilities:**
- Build upload, progress, result and history screens
- Integrate upload, status and report endpoints
- Handle network errors and large-file upload states
- Display safety warnings and recommendations
- Test the application on an actual Android device

**Deliverable:**  
A user can upload a recording and view its completed report on Android.

**Key Tasks:**
- Implement file picker with Storage Access Framework
- Create upload progress UI with real-time status updates
- Build results screen showing:
  - Risk level with color coding
  - Evidence-linked reasons (clickable)
  - Voice detection results (if available)
  - Recommended actions
  - Counterfactual explanations
- Implement history screen with:
  - List of all previous analyses
  - Filter by status
  - Pull-to-refresh
- Handle error states:
  - Network timeouts
  - Backend unavailable
  - Invalid file formats
  - Large file upload progress
- Test on physical Android device (not just emulator)
- Verify backend URL configuration for device testing

---

### Member 2 — Backend + Perception

**Owns:** `backend/api/`, `backend/audio/`, `backend/storage/`

**Responsibilities:**
- Build FastAPI endpoints and job-status handling
- Integrate audio preprocessing and faster-whisper
- Return timestamped transcripts and language metadata
- Integrate optional AASIST/Wav2Vec2 models if feasible
- Save job results and handle processing failures

**Deliverable:**  
A stable backend that accepts real audio and produces a transcript.

**Key Tasks:**
- Implement core API routes:
  - `POST /analyze/recording` - Upload handler
  - `GET /call/{id}/status` - Status polling
  - `GET /call/{id}/state` - Full state retrieval
  - `POST /contacts/{id}/voiceprint` - Voice enrollment
  - `WS /ws/audio/{call_id}` - Live streaming (if time permits)
- Audio preprocessing pipeline:
  - ffmpeg integration for format conversion
  - 16 kHz mono WAV normalization
  - VAD (Voice Activity Detection)
  - 2s chunking for live mode
- ASR integration:
  - faster-whisper (base or small model, int8 quantized)
  - Timestamped segment generation
  - Language detection
  - Handle ASR failures gracefully
- Voice layer (parallel processing):
  - Quality gate (duration, SNR, clipping detection)
  - AASIST or wav2vec2 integration for spoof detection
  - ECAPA-TDNN for voiceprint matching
  - Return VoiceEvidence JSON
- Storage management:
  - Secure file storage with UUID naming
  - Cleanup of temporary files
  - Handle large file uploads (streaming)
- Job state management:
  - queued → processing → completed/failed
  - Database persistence
  - Error logging

---

### Member 3 — AI Agents + Trust Engine

**Owns:** `backend/agents/`, `backend/knowledge/`, `backend/trust_engine/`, `backend/actions/`

**Responsibilities:**
- Implement Claim, Request and Behavior agents
- Add Trust Graph, Kill-Chain Tracker and curated RAG
- Implement Fraud/Skeptic orchestration using LangGraph
- Define category caps, additive scoring and hard-rule floors
- Implement Verification and Guardian outputs

**Deliverable:**  
A tested analysis engine that produces explainable and repeatable decisions.

**Key Tasks:**
- Evidence Extraction Agents:
  - **Tier 1:** Regex patterns + TF-IDF/LogReg classifier
    - Instant detection of OTP, money, urgency keywords
    - Hinglish pattern detection
  - **Tier 2:** LLM extractors (with fallback)
    - Claim Agent: Extract identity claims with quotes
    - Request Agent: Extract sensitive requests with context
    - Behavior Agent: Detect urgency, secrecy, pressure
    - Each finding must cite quote + timestamp
    - Pydantic validation for all outputs
- Trust Graph Implementation:
  - SQLite schema + NetworkX graph
  - Contacts: name, relation, saved_numbers, safe_word_hash, voiceprint_embedding
  - Organizations: official_numbers, official_app
  - Channel status logic (VERIFIED/MISMATCH/UNKNOWN)
  - Contradiction detection (claim vs saved contact)
- Kill-Chain FSM:
  - Track progression: Contact → Trust → Urgency → Request → Secrecy
  - Detect stage-skipping (abnormal patterns)
- RAG System:
  - ChromaDB setup
  - Ingest ~20 curated scam pattern documents
  - Top-3 retrieval with threshold
  - Citation tracking
- Trust Judge (Deterministic):
  - Category scoring with caps:
    - Identity/Relationship: 25 points
    - Sensitive Request: 30 points
    - Behavioral Pressure: 20 points
    - Channel Inconsistency: 15 points
    - Voice: 10 points
  - Hard-rule floors:
    - OTP/PIN on non-VERIFIED → ≥75
    - Money + secrecy + MISMATCH → ≥50
    - Relative + non-VERIFIED + spoof ≥0.80 → ≥50
    - VERIFIED + no sensitive request → ≤24
  - Reason generation (template-based, not LLM-generated)
  - Counterfactual computation (re-run with changed inputs)
  - Audit hash generation
- Fraud vs Skeptic Orchestration (Optional):
  - LangGraph implementation
  - Advisory only (MEDIUM band)
  - Cannot change score
- Action Layer:
  - Cross-channel verification prompts
  - Guardian alert generation
  - One-tap confirmation links

---

### Member 4 — Web Dashboard + Evaluation

**Owns:** `web-dashboard/`, `tests/`, integration documentation

**Responsibilities:**
- Build the Streamlit dashboard
- Show transcript, agent findings, risk level and kill-chain progression
- Add report history, report export and evaluation metrics
- Create legitimate and scam test scenarios, including Hinglish
- Run end-to-end tests and coordinate demo preparation

**Deliverable:**  
A working dashboard plus evidence that the pipeline has been tested.

**Key Tasks:**
- Streamlit Dashboard Pages:
  - **Home:** Backend health, statistics, phase notice
  - **Upload:** File uploader with progress and status polling
  - **Analysis Results:**
    - Risk level display with color coding
    - Mock/real analysis badge
    - Transcript with clickable timestamps
    - Agent findings table (expandable)
    - Voice detection card (if available)
    - Kill-chain progression stepper
    - Reasons list (click to jump to evidence)
    - Counterfactual explanations
    - Recommended actions
    - Warnings and limitations
  - **History:** List all analyses with filters and search
  - **About:** Project info and documentation links
- API Client:
  - `api_client.py` with all endpoint wrappers
  - Error handling and retry logic
  - Connection status monitoring
- Report Export:
  - JSON export
  - PDF export (if time permits)
- Test Scenarios:
  - Create `scenarios.json` with:
    - 5 scam scenarios (bank, family emergency, KYC, authority, investment)
    - 2 legitimate scenarios (known contact, expected callback)
  - Include Hinglish examples
  - Cover all risk levels (Low, Medium, High, Critical)
- Evaluation & Testing:
  - End-to-end integration tests
  - Measure and document:
    - WER on English/Hindi/Hinglish samples
    - Latency (Tier 1, full analysis, time to first HIGH)
    - Precision/recall for Tier 1 classifier
    - Voice detection rates (clean vs phone-quality)
  - Create evaluation report with tables and charts
- Demo Coordination:
  - Prepare 3-minute demo script
  - Test all demo scenarios
  - Create backup video recording
  - Coordinate with all team members for demo readiness
- Documentation:
  - Integration testing guide
  - Demo instructions
  - Known issues and workarounds
  - Performance metrics report

---

### Coordination Points

**Daily Standups:**
- What did you complete yesterday?
- What will you work on today?
- Any blockers?

**Integration Checkpoints:**
- **Hour 6:** All modules work standalone
- **Hour 10:** Thin loop functional (simulated transcript → report)
- **Hour 14:** Full context integration complete
- **Hour 17:** End-to-end pipeline working
- **Hour 19:** All tests passing, measurements documented

**Communication:**
- Shared `models.py` - coordinate schema changes
- API contract changes - notify all members
- Blocking issues - escalate immediately
- Testing - coordinate shared test resources

**Pre-Demo Checklist:**
- [ ] M1: Android app tested on physical device
- [ ] M2: Backend stable, no crashes in 30-minute run
- [ ] M3: All 7 scenarios produce correct risk levels
- [ ] M4: Dashboard displays all features, demo rehearsed
- [ ] All: Fresh clone test passed
- [ ] All: Backup video recorded

---

## Summary of v3 Changes

1. ✅ **Voice-clone detection added as real evidence layer**
   - Check A: Synthetic-speech detection (AASIST/wav2vec2)
   - Check B: Voiceprint match vs enrolled contacts
   
2. ✅ **Judge updated with voice rules**
   - Voice group with 10-point cap
   - Voice-aware floor: relative claim + non-VERIFIED + spoof_prob ≥ 0.80 → floor 50
   
3. ✅ **Voice enrollment endpoint added**
   - `POST /contacts/{id}/voiceprint` stores embeddings (not audio)
   
4. ✅ **Corrected counterfactual examples**
   - All arithmetic checked against scoring table
   - Family emergency example: 80 (with voice) → 70 (without voice) → 15 (saved number)
   
5. ✅ **Evaluation includes voice validation**
   - Test on clean vs phone-quality audio
   - Report detection rate and false-positive rate separately
   - Consent required for voice cloning tests
   
6. ✅ **Updated data contracts**
   - `VoiceEvidence` schema added
   - `voiceprint_embedding` added to contacts table
   - Report includes `category_scores` with voice breakdown

7. ✅ **Voice layer runs in parallel**
   - Never blocks ASR or Tier 1
   - Degrades gracefully to "unavailable" on failure
   - Quality gate for inconclusive results

8. ✅ **Enhanced honesty rules**
   - Voice is experimental and soft signal
   - Perfect clones may pass detector
   - Multi-layered defense emphasized
