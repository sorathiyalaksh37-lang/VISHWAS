# VISHWAS Parameter-Based Risk Assessment Specification

**Status:** 📋 SPECIFICATION - Implementation Required  
**Priority:** HIGH  
**Complexity:** MAJOR REFACTORING (Est. 40-60 hours)

---

## Executive Summary

This document specifies a comprehensive refactoring of VISHWAS from an evidence-first to a **parameter-first risk assessment architecture**. The current system extracts evidence objects and passes them to scoring; the new system will capture validated parameters, score deterministically from those parameters, and generate consistent reports.

**Core Principle:** Parameters → Validation → Scoring → Classification → Report

---

## Current Architecture Analysis

### Current Flow
```
Audio/Transcript → Evidence Extraction → Trust Judge → Scoring → Report
```

### Current Components

**Evidence Schemas** (`app/schemas/evidence.py`):
- `ClaimEvidence` - Identity claims with quote, timestamp, confidence
- `MoneyRequest` - Financial requests with amount, currency, method
- `CredentialRequest` - Sensitive info requests (OTP, PIN, password, etc.)
- `UrgencyEvidence` - Time pressure with `.quotes` (plural), severity, patterns
- `SecrecyEvidence` - Isolation tactics
- `EmotionalPressureEvidence` - Manipulation types
- `VoiceEvidence` - Anti-spoof analysis results
- `EvidenceExtraction` - Container for all evidence types

**Scoring Engine** (`app/trust_engine/scoring.py`):
- Category caps: Identity(25), Request(30), Behavior(20), Channel(15), Voice(10)
- Risk bands: LOW(0-24), MEDIUM(25-49), HIGH(50-74), CRITICAL(75-100)
- Hard floors for critical combinations
- Deduplication via `_seen_evidence` set

**Trust Judge** (`app/trust_engine/judge.py`):
- Coordinates evidence → context → scoring → assessment
- Generates verification recommendations
- Collects warnings about limitations
- Detects killchain stages
- Produces `RiskAssessment` with audit hash

### Issues Identified

1. **Schema Inconsistency:** Some evidence has `.quote` (singular), others `.quotes` (plural)
2. **Silent Fallbacks:** Trust Engine failures substitute simplified scoring without clear degradation warnings
3. **Contradictory Warnings:** "No requests detected" when requests exist
4. **Voice Status Confusion:** "Unavailable" shown when status="ok"
5. **Evidence-Centric Design:** Scoring reads evidence structure directly rather than validated parameters
6. **Missing Parameter Validation:** No centralized parameter normalization/validation layer
7. **Duplicate Scoring Risk:** Same evidence can contribute through multiple paths

---

## Parameter-First Architecture

### New Flow
```
Audio/Transcript → Parameter Capture → Parameter Validation → Deterministic Scoring → Risk Classification → Report Generation → Frontend
```

### Parameter Groups

#### A. Identity Parameters

```python
class IdentityParameters(BaseModel):
    """Validated identity and verification parameters."""
    
    # Claimed identity
    claimed_name: Optional[str] = Field(None, description="Claimed caller name")
    claimed_relationship: Optional[Literal[
        "relative", "organization", "authority", 
        "service_provider", "friend", "unknown"
    ]] = None
    claim_confidence: Optional[float] = Field(None, ge=0, le=1)
    claim_source_quote: Optional[str] = None
    claim_timestamp: Optional[float] = Field(None, ge=0)
    
    # Verification status
    identity_verification_status: Literal[
        "verified",      # Independently confirmed
        "supported",     # Evidence supports claim
        "unverified",    # No verification attempted
        "contradicted",  # Evidence contradicts claim
        "unavailable"    # Cannot determine
    ] = "unverified"
    
    # Identity consistency
    identity_changed: bool = Field(False, description="Whether claimed identity changed during call")
    identity_change_count: int = Field(0, ge=0)
    
    # Supporting details
    verification_method: Optional[str] = None  # "callback", "safe_word", "known_details"
    verification_timestamp: Optional[float] = None
```

#### B. Sensitive Request Parameters

```python
class SensitiveRequestParameters(BaseModel):
    """Validated sensitive request parameters."""
    
    # Financial requests
    money_requested: bool = False
    money_amount: Optional[float] = Field(None, ge=0)
    money_currency: str = "INR"
    payment_method: Optional[str] = None  # "upi", "bank_transfer", "cash"
    money_request_count: int = Field(0, ge=0)
    money_request_quotes: List[str] = Field(default_factory=list)
    money_request_timestamps: List[float] = Field(default_factory=list)
    
    # Credential requests
    credentials_requested: bool = False
    credential_types: List[Literal[
        "otp", "pin", "password", "cvv", "card_number",
        "account_number", "aadhar", "pan", "kyc_details"
    ]] = Field(default_factory=list)
    credential_request_quotes: List[str] = Field(default_factory=list)
    credential_request_timestamps: List[float] = Field(default_factory=list)
    
    # Action requests
    actions_requested: bool = False
    action_types: List[str] = Field(default_factory=list)
    action_details: List[str] = Field(default_factory=list)
    
    # Attribution
    requester_role: Literal[
        "caller",        # Request made by caller
        "recipient",     # Request made by recipient
        "unknown"        # Cannot determine from transcript
    ] = "unknown"
    
    @property
    def has_sensitive_request(self) -> bool:
        return self.money_requested or self.credentials_requested or self.actions_requested
```

#### C. Behavioral Pressure Parameters

```python
class BehavioralPressureParameters(BaseModel):
    """Validated behavioral pressure parameters."""
    
    # Urgency
    urgency_detected: bool = False
    urgency_severity: Literal["low", "medium", "high"] = "low"
    urgency_patterns: List[str] = Field(default_factory=list)  # "time_limit", "threat", "emergency"
    urgency_quotes: List[str] = Field(default_factory=list)
    urgency_timestamps: List[float] = Field(default_factory=list)
    
    # Secrecy
    secrecy_detected: bool = False
    secrecy_patterns: List[str] = Field(default_factory=list)  # "dont_tell", "secret", "alone"
    secrecy_quotes: List[str] = Field(default_factory=list)
    secrecy_timestamps: List[float] = Field(default_factory=list)
    
    # Emotional pressure
    emotional_pressure_detected: bool = False
    pressure_types: List[Literal["fear", "guilt", "authority", "sympathy", "greed", "confusion"]] = Field(default_factory=list)
    pressure_quotes: List[str] = Field(default_factory=list)
    pressure_timestamps: List[float] = Field(default_factory=list)
    
    # Threats and intimidation
    threats_detected: bool = False
    threat_types: List[str] = Field(default_factory=list)  # "account_block", "legal_action", "police"
    
    # Repeated demands
    demand_repetition_count: int = Field(0, ge=0)
    
    # Verification resistance
    resists_verification: bool = False
    verification_resistance_quotes: List[str] = Field(default_factory=list)
    
    @property
    def has_pressure_tactics(self) -> bool:
        return (
            self.urgency_detected or 
            self.secrecy_detected or 
            self.emotional_pressure_detected or
            self.threats_detected or
            self.resists_verification
        )
```

#### D. Communication Channel Parameters

```python
class CommunicationChannelParameters(BaseModel):
    """Validated communication channel parameters."""
    
    # Caller number status
    caller_number: Optional[str] = None
    caller_number_status: Literal[
        "verified_contact",   # Saved contact with verification history
        "known_contact",      # Saved contact, not verified
        "unknown",            # Not in contacts
        "blocked",            # Previously blocked
        "unavailable"         # Caller ID unavailable
    ] = "unknown"
    
    # Channel verification
    channel_verified: bool = False
    verification_method: Optional[str] = None  # "callback", "contact_match"
    
    # Claimed channel issues
    claims_phone_unavailable: bool = False
    phone_unavailable_explanation: Optional[str] = None
    
    # Channel inconsistency
    channel_inconsistency_detected: bool = False
    inconsistency_type: Optional[Literal[
        "verified_mismatch",    # Verified contact called from different number
        "known_mismatch",       # Known contact called from different number  
        "unknown_number",       # No previous contact history
        "suspicious_pattern"    # Other suspicious channel behavior
    ]] = None
    
    # Context
    previous_call_count: int = Field(0, ge=0)
    last_verified_call: Optional[float] = None  # Timestamp of last verified call
```

#### E. Voice Authenticity Parameters

```python
class VoiceAuthenticityParameters(BaseModel):
    """Validated voice analysis parameters."""
    
    # Analysis status
    analysis_status: Literal[
        "analysed",       # Successfully analyzed
        "inconclusive",   # Analysis completed but inconclusive
        "unavailable",    # Model not available
        "failed"          # Analysis failed/error
    ] = "unavailable"
    
    # Spoof detection
    spoof_score: Optional[float] = Field(None, ge=0, le=1, description="Model-reported spoof probability")
    spoof_score_valid: bool = False
    spoof_model_name: Optional[str] = None
    spoof_model_version: Optional[str] = None
    windows_analyzed: Optional[int] = Field(None, ge=0)
    
    # Score interpretation
    spoof_confidence_level: Optional[Literal["low", "medium", "high"]] = None  # <0.6, 0.6-0.8, >0.8
    
    # Voiceprint matching
    voiceprint_available: bool = False
    voiceprint_similarity: Optional[float] = Field(None, ge=0, le=1)
    voiceprint_matches: Optional[bool] = None
    
    # Audio quality
    audio_duration_seconds: Optional[float] = Field(None, ge=0)
    audio_quality_sufficient: bool = False
    
    # Calibration metadata
    threshold_high: float = 0.80
    threshold_medium: float = 0.60
    
    def get_risk_contribution(self) -> int:
        """Calculate voice risk contribution (0-10)."""
        if self.analysis_status != "analysed" or not self.spoof_score_valid:
            return 0
        
        if self.spoof_score is None:
            return 0
        
        if self.spoof_score >= self.threshold_high:
            return 10  # HIGH confidence synthetic
        elif self.spoof_score >= self.threshold_medium:
            return 5   # MEDIUM confidence synthetic
        else:
            return 0   # Insufficient confidence
```

#### F. Conversation Consistency Parameters

```python
class ConversationConsistencyParameters(BaseModel):
    """Validated conversation consistency parameters."""
    
    # Contradictions
    contradictions_detected: bool = False
    contradiction_types: List[str] = Field(default_factory=list)
    contradiction_quotes: List[str] = Field(default_factory=list)
    
    # Explanation changes
    explanation_changes: int = Field(0, ge=0)
    explanation_change_details: List[str] = Field(default_factory=list)
    
    # Verification interaction
    recipient_proposes_verification: bool = False
    recipient_verification_quotes: List[str] = Field(default_factory=list)
    caller_discourages_verification: bool = False
    caller_discouragement_quotes: List[str] = Field(default_factory=list)
    
    # Pressure after verification
    pressure_continues_after_verification: bool = False
```

### Unified Parameter Container

```python
class RiskAssessmentParameters(BaseModel):
    """Complete validated parameters for risk assessment."""
    
    # Metadata
    call_id: str
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    transcript_segments_analyzed: int = Field(0, ge=0)
    analysis_mode: str = "real"  # "real", "mock", "degraded"
    
    # Parameter groups
    identity: IdentityParameters
    requests: SensitiveRequestParameters
    behavior: BehavioralPressureParameters
    channel: CommunicationChannelParameters
    voice: VoiceAuthenticityParameters
    consistency: ConversationConsistencyParameters
    
    # Extraction quality
    extraction_warnings: List[str] = Field(default_factory=list)
    extraction_errors: List[str] = Field(default_factory=list)
    missing_parameters: List[str] = Field(default_factory=list)
    parameter_confidence_score: float = Field(0.0, ge=0, le=1)
    
    # Source tracking
    source_evidence_version: str = "1.0"
    source_extractor: str = "tier1"  # "tier1", "tier2", "hybrid"
    
    class Config:
        validate_assignment = True
```

---

## Implementation Plan

### Phase 1: Parameter Schema Implementation (4-6 hours)

**Files to Create:**
1. `app/schemas/parameters.py` - All parameter model classes
2. `app/validation/parameter_validator.py` - Validation and normalization logic
3. `tests/test_parameter_schemas.py` - Schema validation tests

**Tasks:**
- [ ] Implement all 6 parameter group models
- [ ] Add comprehensive field validation
- [ ] Implement parameter normalization (currency, amounts, timestamps)
- [ ] Add computed properties and helper methods
- [ ] Write 50+ unit tests for parameter validation

### Phase 2: Evidence-to-Parameter Adapter (6-8 hours)

**Files to Create:**
1. `app/adapters/evidence_to_parameters.py` - Converts EvidenceExtraction → RiskAssessmentParameters

**Tasks:**
- [ ] Map ClaimEvidence → IdentityParameters
- [ ] Map MoneyRequest/CredentialRequest → SensitiveRequestParameters
- [ ] Map UrgencyEvidence/SecrecyEvidence → BehavioralPressureParameters (fix `.quotes` plural)
- [ ] Map channel status → CommunicationChannelParameters
- [ ] Map VoiceEvidence → VoiceAuthenticityParameters
- [ ] Implement deduplication logic
- [ ] Handle missing/invalid evidence gracefully
- [ ] Add extraction warnings and errors to parameters
- [ ] Write 30+ adapter tests

### Phase 3: Parameter-Based Scoring Engine (8-10 hours)

**Files to Modify:**
1. `app/trust_engine/scoring.py` - Refactor to accept RiskAssessmentParameters

**New Classes:**
```python
class ParameterScorer:
    """Scores risk from validated parameters."""
    
    def calculate_score(
        self,
        parameters: RiskAssessmentParameters
    ) -> ScoreBreakdown:
        """Calculate risk from parameters."""
        
    def _score_identity_parameters(self, params: IdentityParameters, channel: CommunicationChannelParameters) -> int:
        """Score identity consistency (0-25)."""
        
    def _score_request_parameters(self, params: SensitiveRequestParameters) -> int:
        """Score sensitive requests (0-30)."""
        
    def _score_behavior_parameters(self, params: BehavioralPressureParameters) -> int:
        """Score pressure tactics (0-20)."""
        
    def _score_channel_parameters(self, params: CommunicationChannelParameters, identity: IdentityParameters) -> int:
        """Score channel inconsistency (0-15)."""
        
    def _score_voice_parameters(self, params: VoiceAuthenticityParameters) -> int:
        """Score voice authenticity (0-10)."""
        
    def _apply_hard_floors(self, parameters: RiskAssessmentParameters, breakdown: ScoreBreakdown) -> int:
        """Apply hard rule floors based on parameter combinations."""
        
    def _detect_duplicates(self, parameters: RiskAssessmentParameters) -> Set[str]:
        """Detect duplicate parameter contributions."""
```

**Tasks:**
- [ ] Refactor each `_score_*` method to read from parameters
- [ ] Implement explicit scoring rules with configurable weights
- [ ] Add duplicate detection across parameter groups
- [ ] Ensure category caps enforced
- [ ] Validate hard floors work with parameters
- [ ] Add detailed score explanations
- [ ] Write 40+ scoring tests including edge cases

### Phase 4: Trust Judge Integration (4-6 hours)

**Files to Modify:**
1. `app/trust_engine/judge.py` - Update to use parameter-based scoring

**Tasks:**
- [ ] Accept RiskAssessmentParameters instead of EvidenceExtraction
- [ ] Update verification recommendation logic
- [ ] Update warning collection from parameters
- [ ] Update killchain detection from parameters
- [ ] Preserve audit hash generation
- [ ] Update failure handling to preserve parameters
- [ ] Write 20+ integration tests

### Phase 5: Real Analysis Service Integration (6-8 hours)

**Files to Modify:**
1. `app/services/real_analysis_service.py` - Insert parameter adapter before scoring

**New Flow:**
```python
def analyze_call(self, call_id: str) -> None:
    # ... existing ASR and evidence extraction ...
    
    # NEW: Convert evidence to parameters
    from app.adapters.evidence_to_parameters import convert_evidence_to_parameters
    parameters = convert_evidence_to_parameters(
        evidence=evidence,
        channel_status=channel_status,
        trust_context=trust_context,
        voice_result=voice_result
    )
    
    # Validate parameters
    from app.validation.parameter_validator import validate_parameters
    validation_result = validate_parameters(parameters)
    if not validation_result.is_valid:
        parameters.extraction_errors.extend(validation_result.errors)
    
    # Score from parameters
    assessment = judge.evaluate_from_parameters(
        call_id=call_id,
        parameters=parameters
    )
```

**Tasks:**
- [ ] Insert parameter conversion after evidence extraction
- [ ] Add parameter validation step
- [ ] Update Trust Judge call to pass parameters
- [ ] Preserve fallback behavior but mark as degraded
- [ ] Update agent_findings generation from parameters
- [ ] Fix UrgencyEvidence.quote → .quotes usage
- [ ] Write 15+ integration tests

### Phase 6: Report Generation (4-6 hours)

**Files to Modify:**
1. `app/api/routes/analyze.py` - Update _build_report_response
2. `app/schemas/report.py` - Add parameter fields if needed

**Tasks:**
- [ ] Ensure report built from same parameters used in scoring
- [ ] Add parameter summary to report
- [ ] Fix contradictory warnings (check parameters.requests.has_sensitive_request)
- [ ] Fix voice status warnings (check parameters.voice.analysis_status)
- [ ] Ensure verification recommendations match risk level
- [ ] Add missing parameter indicators
- [ ] Write 10+ report consistency tests

### Phase 7: Frontend Compatibility (2-4 hours)

**Files to Check:**
1. `vishwas-frontend/src/types/analysis.ts` - Ensure types match
2. `vishwas-frontend/src/components/results/*` - Check rendering

**Tasks:**
- [ ] Verify API response schema compatibility
- [ ] Update TypeScript types if needed
- [ ] Test report rendering with new parameter structure
- [ ] Ensure no breaking changes in API
- [ ] Run production build

### Phase 8: Regression Testing (4-6 hours)

**Test Files to Create/Update:**
1. `tests/test_parameter_based_scoring_regression.py` - The ₹5,000 example and others

**Test Cases:**
- [ ] ₹5,000 transfer with urgency + secrecy (from bug report)
- [ ] OTP request on unverified channel (hard floor)
- [ ] Unknown number with no requests (should be LOW not MEDIUM)
- [ ] Verified contact with legitimate request (should be LOW)
- [ ] Repeated urgency phrases (no score inflation)
- [ ] Recipient refusal (not counted as request)
- [ ] Voice 72.4% spoof score (5 points, VOICE_SPOOF_MED)
- [ ] Voice unavailable (0 points, clear warning)
- [ ] Trust Judge failure (degraded analysis, no "Normal conversation")
- [ ] Missing parameters (unknown status, not zero risk)
- [ ] All existing test suites (preserve 84/88 passing)

---

## Scoring Rules Configuration

### Identity Category (0-25 points)

| Parameter Condition | Points | Rule ID |
|---|---:|---|
| `identity_verification_status == "contradicted"` AND `channel == "verified_mismatch"` | 20 | IDENTITY_VERIFIED_MISMATCH |
| `identity_verification_status == "unverified"` AND `claimed_relationship == "relative"` AND `channel == "unknown"` | 15 | IDENTITY_UNKNOWN_RELATIVE |
| `identity_verification_status == "unverified"` AND `claimed_relationship in ["organization", "authority"]` AND `channel == "unknown"` | 15 | IDENTITY_UNKNOWN_ORG |
| `identity_changed == True` | +5 | IDENTITY_CHANGE |
| `identity_verification_status == "verified"` | 0 | IDENTITY_VERIFIED |

### Request Category (0-30 points)

| Parameter Condition | Points | Rule ID |
|---|---:|---|
| `credential_types contains "otp" OR "pin"` | 30 | REQ_OTP_PIN |
| `credential_types contains "password"` | 25 | REQ_PASSWORD |
| `credential_types contains ["cvv", "card_number", "account_number"]` | 20 | REQ_FINANCIAL_CRED |
| `credentials_requested == True` (other types) | 15 | REQ_CREDENTIALS |
| `money_requested == True` AND `money_amount >= 50000` | 20 | REQ_MONEY_HIGH |
| `money_requested == True` AND `money_amount > 0` | 15 | REQ_MONEY |
| `money_requested == True` AND `money_amount is None` | 15 | REQ_MONEY_UNSPECIFIED |
| `actions_requested == True` | 10 | REQ_ACTION |

**Deduplication:** Only highest scoring request type counts.

### Behavior Category (0-20 points)

| Parameter Condition | Points | Rule ID |
|---|---:|---|
| `urgency_severity == "high"` | 15 | BEHAVIOR_URGENCY_HIGH |
| `urgency_severity == "medium"` | 10 | BEHAVIOR_URGENCY_MED |
| `urgency_severity == "low"` | 5 | BEHAVIOR_URGENCY_LOW |
| `secrecy_detected == True` | +5 | BEHAVIOR_SECRECY |
| `emotional_pressure_detected == True` | +5 | BEHAVIOR_EMOTION |
| `threats_detected == True` | +5 | BEHAVIOR_THREAT |
| `resists_verification == True` | +5 | BEHAVIOR_RESIST_VERIFY |

**Cap:** Total cannot exceed 20.

### Channel Category (0-15 points)

| Parameter Condition | Points | Rule ID |
|---|---:|---|
| `inconsistency_type == "verified_mismatch"` | 15 | CHANNEL_VERIFIED_MISMATCH |
| `inconsistency_type == "known_mismatch"` | 12 | CHANNEL_KNOWN_MISMATCH |
| `caller_number_status == "unknown"` AND `claimed_relationship != "unknown"` | 10 | CHANNEL_UNKNOWN_CLAIM |
| `caller_number_status == "blocked"` | 15 | CHANNEL_BLOCKED |
| `claims_phone_unavailable == True` | +3 | CHANNEL_PHONE_EXCUSE |

**Deduplication:** Only highest channel inconsistency counts, plus modifiers.

### Voice Category (0-10 points)

| Parameter Condition | Points | Rule ID |
|---|---:|---|
| `analysis_status == "analysed"` AND `spoof_score >= 0.80` | 10 | VOICE_SPOOF_HIGH |
| `analysis_status == "analysed"` AND `spoof_score >= 0.60` | 5 | VOICE_SPOOF_MED |
| `voiceprint_matches == False` AND `voiceprint_available == True` | +5 | VOICE_MISMATCH |
| `analysis_status != "analysed"` | 0 | (No voice contribution) |

**Cap:** Total cannot exceed 10.

### Hard Floors

| Condition | Floor Score | Rule ID |
|---|---:|---|
| `credential_types contains ["otp", "pin"]` AND `channel_verified == False` | 75 | FLOOR_OTP_NONVERIFIED |
| `money_requested == True` AND `secrecy_detected == True` AND `inconsistency_type in ["verified_mismatch", "known_mismatch"]` | 50 | FLOOR_MONEY_SECRECY_MISMATCH |
| `claimed_relationship == "relative"` AND `spoof_score >= 0.80` AND `channel_verified == False` | 50 | FLOOR_VOICE_RELATIVE_NONVERIFIED |

---

## Migration Strategy

### Phase 1: Parallel Implementation (Non-Breaking)

1. Create all new parameter schemas alongside existing evidence schemas
2. Implement adapter layer that converts evidence → parameters
3. Create new `ParameterScorer` class alongside existing `TrustScorer`
4. Add parameter-based path as opt-in via feature flag

### Phase 2: Gradual Switchover

1. Enable parameter-based scoring in test environment
2. Run both paths in parallel, compare results
3. Fix discrepancies
4. Switch production to parameter-based scoring
5. Deprecate old evidence-first path

### Phase 3: Cleanup

1. Remove old evidence-first scoring code
2. Simplify evidence schemas to focus on extraction only
3. Update all documentation

---

## Testing Strategy

### Unit Tests (100+ tests)
- Parameter schema validation
- Parameter normalization (currency, amounts)
- Evidence-to-parameter adapter
- Individual scoring rules
- Category caps enforcement
- Hard floor evaluation
- Duplicate detection

### Integration Tests (50+ tests)
- End-to-end parameter capture → scoring → report
- Trust Judge with parameters
- Real analysis service integration
- Fallback behavior with parameters
- API response generation

### Regression Tests (20+ critical scenarios)
- The ₹5,000 example (bug report)
- All hard floor scenarios
- Risk band boundaries
- Voice scoring at 60%, 72%, 80%, 90%
- Unknown vs verified vs contradicted identities
- Existing test preservation (84/88 must still pass)

### Performance Tests
- Large transcript processing
- Parameter validation overhead
- Scoring engine performance
- Memory usage

---

## Success Criteria

1. **✅ Parameter Capture:** All transcript and audio analysis results captured as validated parameters
2. **✅ Deterministic Scoring:** Risk score computed entirely from parameters using documented rules
3. **✅ Report Consistency:** No contradictory warnings (requests detected vs "no requests", voice available vs "unavailable")
4. **✅ Correct Example:** ₹5,000 transcript produces appropriate risk score and recommendations
5. **✅ No Regressions:** 84/88 existing tests still pass
6. **✅ Frontend Compatible:** React app renders reports without breaking changes
7. **✅ Explainable:** Every score contribution traceable to specific parameter and rule
8. **✅ Maintainable:** Scoring rules configurable, not hardcoded throughout codebase

---

## Risk Assessment

### High Risk Items
- **Breaking API Changes:** Frontend may need updates if response schema changes
- **Test Failures:** Existing tests may expect specific evidence structures
- **Performance Impact:** Parameter validation adds processing overhead
- **Migration Complexity:** Large codebase refactoring introduces bug risk

### Mitigation
- Implement adapter layer for backward compatibility
- Run parallel paths during migration
- Comprehensive regression testing
- Feature flag for gradual rollout
- Monitor production metrics

---

## Implementation Timeline

**Estimated Total: 40-60 hours of focused development**

| Phase | Hours | Priority |
|---|---:|---|
| 1. Parameter Schema | 4-6 | CRITICAL |
| 2. Evidence Adapter | 6-8 | CRITICAL |
| 3. Parameter Scoring | 8-10 | CRITICAL |
| 4. Trust Judge Integration | 4-6 | HIGH |
| 5. Real Analysis Integration | 6-8 | HIGH |
| 6. Report Generation | 4-6 | HIGH |
| 7. Frontend Compatibility | 2-4 | MEDIUM |
| 8. Regression Testing | 4-6 | CRITICAL |
| 9. Documentation | 2-4 | HIGH |
| 10. Code Review & Polish | 4-6 | HIGH |

**Recommended Approach:** Implement in 2-week sprint with daily progress reviews.

---

## Next Steps

1. **Review this specification** with the team
2. **Approve the architecture** and parameter schema design
3. **Create feature branch** `feature/parameter-based-scoring`
4. **Begin Phase 1** (parameter schema implementation)
5. **Daily standups** to track progress and blockers
6. **Mid-sprint review** after Phase 3 completion
7. **Final review** before merging to main

---

## References

- Current scoring engine: `app/trust_engine/scoring.py`
- Current evidence schemas: `app/schemas/evidence.py`
- Trust Judge: `app/trust_engine/judge.py`
- Real analysis service: `app/services/real_analysis_service.py`
- Consistency fix report: `PHASE_REPORT_CONSISTENCY_FIX.md`
- Phase 7-9 implementation: `PHASE7_9_IMPLEMENTATION_REPORT.md`

---

**Document Version:** 1.0  
**Created:** October 14, 2026  
**Author:** Kiro AI  
**Status:** SPECIFICATION - REQUIRES IMPLEMENTATION
