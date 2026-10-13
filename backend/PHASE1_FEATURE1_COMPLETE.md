# Phase 1 Feature 1: Committed vs Partial Transcript Support - COMPLETE

**Status**: ✅ COMPLETE  
**Date**: 2026-10-13  
**Tests**: 236 passing (19 new), 17 skipped, 0 failed

## Overview

Implemented support for handling committed vs partial transcripts in streaming ASR scenarios. The system now differentiates between final (committed) and provisional (partial) transcript segments, adjusting signal severity and confidence accordingly.

## Changes Made

### 1. Schema Extension (`app/schemas/report.py`)
- Added **optional** fields to `TranscriptSegment`:
  - `is_final: Optional[bool]` - Indicates if text is committed/final
  - `confidence: Optional[float]` - ASR confidence score (0.0-1.0)
  - `session_id: Optional[str]` - Session tracking for streaming
- Backward compatible: All fields default to `None`

### 2. Tier1Classifier Updates (`app/extractors/tier1_classifier.py`)

#### Core Logic
- Added `_is_committed_text()` method: Safe default treats `None` as partial
- Updated `classify()` to check finality before signal generation
- Modified `_detect_segment_signals()` to accept `is_committed` parameter

#### Detection Methods
All detection methods updated to handle finality:
- `_detect_credential_requests()`: Generates provisional warnings for partial text
- `_detect_money_requests()`: Adjusts severity high→medium for partial
- `_detect_urgency()`: Adjusts severity based on finality
- `_detect_secrecy()`: Adjusts severity medium→low for partial

#### Extraction Methods
- `extract_claims()`: **Only extracts from committed text** (skips partial)
- `extract_requests()`: **Only extracts from committed text** (skips partial)
- `extract_behavior()`: Processes both, marks partial with `[PARTIAL]` tag

### 3. Signal Type Naming
- Committed text: `CREDENTIAL_REQUEST_OTP`, `MONEY_REQUEST`, etc.
- Partial text: `PROVISIONAL_CREDENTIAL_REQUEST_OTP`, `PROVISIONAL_MONEY_REQUEST`, etc.
- Clear distinction enables filtering and debugging

### 4. Confidence and Severity Adjustments

| Original | Partial Adjustment |
|----------|-------------------|
| Critical → Medium | 60% confidence |
| High → Medium | 60% confidence |
| Medium → Low | 60% confidence |

## Tests

### New Tests (`tests/test_tier1_finality.py`)
Created comprehensive test suite with **19 tests**:

1. **TestCommittedVsPartialDetection** (9 tests)
   - Credential requests (committed, partial, unknown finality)
   - Money requests (committed, partial)
   - Urgency (committed, partial)
   - Secrecy (committed, partial)

2. **TestExtractionMethodsFinality** (7 tests)
   - Claims extraction (committed only)
   - Requests extraction (committed only)
   - Behavior extraction (both, with markers)

3. **TestMixedFinalityStream** (2 tests)
   - Progressive finalization (partial → committed)
   - Mixed segments in same call

4. **TestConfidenceAdjustment** (1 test)
   - Confidence reduction for partial text

All 19 tests **PASSING** ✅

### Backward Compatibility
Updated existing test files to explicitly set `is_final=True`:
- `tests/test_tier1_classifier.py` - 36 tests (all passing)
- `tests/test_evidence_pipeline.py` - 15 tests (all passing)

## Behavior Summary

### Committed Text (`is_final=True`)
- Generates **definitive** signals with original severity
- Triggers full evidence extraction (claims, requests, behavior)
- Full confidence scores
- Examples:
  - "Tell me your OTP" → `CREDENTIAL_REQUEST_OTP` (critical, 0.95)
  - "Send 50000 rupees" → `MONEY_REQUEST` (high, 0.9)

### Partial Text (`is_final=False` or `None`)
- Generates **provisional** warnings with reduced severity
- **Skips** claim and request extraction (unreliable from partial)
- Includes in behavior extraction with `[PARTIAL]` marker
- 60% confidence multiplier
- Examples:
  - "Tell me your OTP" → `PROVISIONAL_CREDENTIAL_REQUEST_OTP` (medium, 0.57)
  - "Send 50000 rupees" → `PROVISIONAL_MONEY_REQUEST` (medium, 0.54)

### Rationale for Conservative Defaults
- **Unknown finality treated as partial**: Prevents false positives
- **Claims/requests require committed text**: Identity claims and sensitive requests need high confidence
- **Behavior patterns more permissive**: Urgency/secrecy useful even from partial (early warning)

## Integration Points

### Upstream (ASR Services)
ASR services should populate:
- `is_final=False` for intermediate results
- `is_final=True` when text is committed
- `confidence` with ASR confidence score
- `session_id` for deduplication across updates

### Downstream (Trust Engine, Judge)
- Can filter on `PROVISIONAL_` prefix to ignore provisional signals
- Can use severity thresholds (e.g., only critical/high for actions)
- Can track signal upgrades (provisional → definitive)

## Limitations

1. **No automatic upgrade**: If partial text generates provisional signal, committed version generates separate signal (deduplication prevents duplicates)
2. **No temporal linking**: System doesn't track which provisional signals correspond to which committed signals
3. **Behavior markers are strings**: `[PARTIAL]` is text prefix, not structured field

## Future Enhancements (Not in Scope)

- Signal upgrade tracking (provisional → definitive mapping)
- Temporal windowing for deduplication across finality updates
- Structured partial indicator in BehaviorEvidence schema
- Confidence-based thresholding (reject low-confidence partial signals)

## Files Modified

1. `/Users/lakshsorathiya/VISHWAS/backend/app/schemas/report.py`
2. `/Users/lakshsorathiya/VISHWAS/backend/app/extractors/tier1_classifier.py`
3. `/Users/lakshsorathiya/VISHWAS/backend/tests/test_tier1_classifier.py`
4. `/Users/lakshsorathiya/VISHWAS/backend/tests/test_evidence_pipeline.py`

## Files Created

1. `/Users/lakshsorathiya/VISHWAS/backend/tests/test_tier1_finality.py`
2. `/Users/lakshsorathiya/VISHWAS/backend/PHASE1_FEATURE1_COMPLETE.md`

## Test Results

```
Backend Test Suite Status: 236 passed, 17 skipped, 0 failed
- Phase 5 tests: 217 passing
- Phase 1 Feature 1 tests: 19 new passing
- Regression tests: All passing (backward compatible)
```

## Next Steps

Proceed to **Feature 2: Evidence Validation** (Phase 1 continued)
