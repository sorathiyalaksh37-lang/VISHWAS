# VISHWAS API Contract — FINAL v2.0

**Frozen on:** 2026-10-13 · **Owner:** M1 (Android) · **Field semantics per:** PS05 Final Implementation Plan v3 (Oct 12, 2026)
**Status: FINAL — M2 (backend) has confirmed implementation of every decision in §5.**
**Reference priority:** (1) this file for paths/shapes → (2) v3 plan for scoring/semantics → (3) anything else is obsolete.

> ⚠️ **This file is the single source of truth for the Android ↔ backend contract.**
> Nobody changes anything here without a written YES from the whole team in #integration.

---

## 1. Endpoints

Base URL during development/demo: `http://<laptop-LAN-IP>:8000/api/v1`
(Emulator: `http://10.0.2.2:8000/api/v1`)

| # | Method | Path | Request | Success response |
|---|--------|------|---------|------------------|
| 1 | POST   | `/api/v1/calls` | `multipart/form-data`: `file` (audio, **required**), `caller_number` (string, **optional**) | `{"call_id": "abc123", "status": "queued"}` |
| 2 | GET    | `/api/v1/calls/{call_id}/status` | — | `{"call_id": "abc123", "status": "processing", "error": null}` |
| 3 | GET    | `/api/v1/calls/{call_id}/report` | — | AnalysisReport JSON (§2) |
| 4 | GET    | `/api/v1/health` | — | liveness check |

**Status enum (endpoint 2):** `queued` → `processing` → `completed` | `failed`

- On `failed`: `{"call_id": "...", "status": "failed", "error": "<human-readable message>"}` — **the field is `error` (nullable string), NOT `error_message`.**
- HTTP-level errors use the envelope in §4.

---

## 2. AnalysisReport fields (FINAL)

| Field | Type | Notes |
|-------|------|-------|
| `call_id` | string | echoes the upload |
| `score` | int (0–100) | `min(100, sum of capped groups)` — caps in §2a |
| `level` | enum | `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` — uppercase, exact strings |
| `category_scores` | object | `{identity, request, behavior, channel, voice}` — caps **25/30/20/15/10** |
| `fired_rules` | string[] | e.g. `R_FAMILY_UNSAVED`, `R_SPOOF_HIGH` |
| `reasons` | string[] | plain-language, templated (LLM never writes facts) |
| `killchain_stage` | string? | Capitalized FSM stage: `Contact` / `Trust` / `Urgency` / `Request` / `Secrecy` / `null` |
| `verification` | object? | `{"action": "callback_saved_number", "target": "Mom (saved: +91-98xxxx)", "safe_word_prompt": true}` — `action` snake_case, `safe_word_prompt` **boolean** |
| `voice` | object? | VoiceEvidence (v3 §4): `{status: "ok" \| "inconclusive" \| "unavailable", spoof_prob: float?, windows_analyzed?, speaker_match?: {claimed_contact, similarity, enrolled}, quality?: {duration_s, snr_db}, model}` |
| `counterfactuals` | array? | `[{change, new_score}]` |
| `transcript` | array | **[embedded in this response]** `[{t, text}]` timestamped segments |
| `timeline` | array? | risk-over-time series for the replay chart (web/dashboard hero; Android may skip) |
| `rag_citations` | array? | usually `[]` |
| `limitations` | array? | honesty/limitation strings for the report footer |
| `audit_hash` | string? | `hash(evidence + rules_version)` |

**Degradation rule (non-negotiable, v3 §5.4):** every nullable field may arrive as
`null` or be missing when a model fails. Voice failure → `"status": "unavailable"`,
everything else still works. App renders gracefully, never crashes.

**Removed from contract:** `is_mock` — not in the v3 plan, dropped by mutual agreement. The app shows no demo badge.

### 2a. Scoring bands → Android color map

| Level | Band | App color |
|-------|------|-----------|
| LOW | 0–24 | Green `#388E3C` |
| MEDIUM | 25–49 | Yellow `#F9A825` |
| HIGH | 50–74 | Orange `#EF6C00` |
| CRITICAL | 75–100 | Red `#D32F2F` |

---

## 3. Mapping — every old name → FINAL name

| Source | Old | **FINAL** |
|---|---|---|
| M1 solo guide | `POST /upload` | **`POST /api/v1/calls`** |
| M1 solo guide | `GET /status/{job_id}` | **`GET /api/v1/calls/{call_id}/status`** |
| M1 solo guide | `GET /report/{job_id}` | **`GET /api/v1/calls/{call_id}/report`** |
| Execution artifact | `POST /call/start` + `POST /upload/{call_id}` | **`POST /api/v1/calls`** (single upload does it) |
| Execution artifact | `GET /job/{call_id}/status` | **`GET /api/v1/calls/{call_id}/status`** |
| Execution artifact | `GET /call/{id}/state` | **`GET /api/v1/calls/{call_id}/report`** |
| v3 plan §6 | `POST /analyze/recording` | **`POST /api/v1/calls`** |
| v3 plan §6 | `GET /call/{id}/state` | **`GET /api/v1/calls/{call_id}/report`** |
| — | `job_id` | **`call_id`** |
| — | `risk_score` / `risk_level` | **`score` / `level`** |
| — | `kill_chain_stage` | **`killchain_stage`** |
| — | `action` (flat) | **`verification.action`** |
| — | safe word as string prompt | **`verification.safe_word_prompt: boolean`** |
| — | 3-level risk | **4-level `LOW/MEDIUM/HIGH/CRITICAL`** |
| — | caps 30/20/25/25/10 | **caps 25/30/20/15/10** |

**v3 endpoints Android does NOT use** (web/dashboard scope): `/ws/audio/{call_id}` (live mic — web), `/transcript/simulate`, `/contacts/{id}/voiceprint` (enrollment is web/dashboard; Android is receive-only), `/call/{id}/counterfactual` (embedded in report), `/call/{id}/export`, `/alert/guardian`, `/guardian/{token}`, `GET /calls` history list (Android keeps its own local Room history).

---

## 4. HTTP error envelope

```json
{
  "error": {
    "code": "ASR_FAILURE",
    "message": "Speech recognition failed",
    "retryable": true
  }
}
```

Used for HTTP-level failures (4xx/5xx). Job-level failure (analysis itself failed) is reported through endpoint 2's `status: "failed"` + `error` string — not this envelope.

---

## 5. Decisions log (all confirmed by M2, 2026-10-13)

| # | Decision | Final answer |
|---|----------|--------------|
| 1 | Status failure field | **`error`** (nullable string) — not `error_message`; batch script updated to match |
| 2 | `transcript` in report | **YES — embedded** in `GET /calls/{id}/report`; app makes one call |
| 3 | `caller_number` in upload | **OPTIONAL** — app and batch script may omit it |
| 4 | `is_mock` flag | **DROPPED** — not in v3 plan, not implemented |
| 5 | Enum casing | **Uppercase exact strings**: `LOW/MEDIUM/HIGH/CRITICAL`, `queued/processing/completed/failed` |
| 6 | HTTP errors | v3 envelope `{"error": {code, message, retryable}}` |
| 7 | `verification` shape | v3 exactly: snake_case `action`, boolean `safe_word_prompt` |
| 8 | Caps & bands | 25/30/20/15/10; bands 0–24 / 25–49 / 50–74 / 75–100 |

---

## 6. Sample report JSON (target shape)

```json
{
  "call_id": "abc123",
  "score": 80,
  "level": "CRITICAL",
  "category_scores": {"identity": 25, "request": 15, "behavior": 15, "channel": 15, "voice": 10},
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
  "voice": {
    "status": "ok",
    "spoof_prob": 0.82,
    "windows_analyzed": 5,
    "speaker_match": {"claimed_contact": "Mom", "similarity": 0.41, "enrolled": true},
    "quality": {"duration_s": 18.4, "snr_db": 14.2},
    "model": "<model name and version>"
  },
  "counterfactuals": [
    {"change": "call from Mom's saved number", "new_score": 15}
  ],
  "transcript": [{"t": 0, "text": "Papa, I had an accident"}],
  "timeline": [],
  "rag_citations": [],
  "limitations": ["Voice detection is experimental and probabilistic"],
  "audit_hash": "..."
}
```

*End of contract. FINAL v2.0 — no open questions remain.*
