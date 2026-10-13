package com.vishwas.app.models

import com.google.gson.annotations.SerializedName

// v3 models per docs/INTEGRATION.md FINAL v2.0 — see that file for field semantics.

data class CategoryScores(
    @SerializedName("identity") val identity: Int? = null,
    @SerializedName("request") val request: Int? = null,
    @SerializedName("behavior") val behavior: Int? = null,
    @SerializedName("channel") val channel: Int? = null,
    @SerializedName("voice") val voice: Int? = null
)

data class Verification(
    @SerializedName("action") val action: String? = null,
    @SerializedName("target") val target: String? = null,
    @SerializedName("safe_word_prompt") val safeWordPrompt: Boolean? = null
)

data class SpeakerMatch(
    @SerializedName("claimed_contact") val claimedContact: String? = null,
    @SerializedName("similarity") val similarity: Double? = null,
    @SerializedName("enrolled") val enrolled: Boolean? = null
)

data class VoiceQuality(
    @SerializedName("duration_s") val durationS: Double? = null,
    @SerializedName("snr_db") val snrDb: Double? = null
)

data class VoiceEvidence(
    @SerializedName("status") val status: String? = null,
    @SerializedName("spoof_prob") val spoofProb: Double? = null,
    @SerializedName("windows_analyzed") val windowsAnalyzed: Int? = null,
    @SerializedName("speaker_match") val speakerMatch: SpeakerMatch? = null,
    @SerializedName("quality") val quality: VoiceQuality? = null,
    @SerializedName("model") val model: String? = null
)

data class Counterfactual(
    @SerializedName("change") val change: String? = null,
    @SerializedName("new_score") val newScore: Int? = null
)

// Exact shape is unconfirmed; contract section 2 only says "risk-over-time series", no field spec given
data class TimelinePoint(
    @SerializedName("t") val t: Double? = null,
    @SerializedName("score") val score: Int? = null,
    @SerializedName("event") val event: String? = null
)

data class TranscriptSegment(
    @SerializedName("t") val t: Double? = null,
    @SerializedName("text") val text: String? = null
)

data class AnalysisReportResponse(
    @SerializedName("call_id") val callId: String? = null,
    @SerializedName("status") val status: String? = null,
    @SerializedName("score") val score: Int? = null,
    @SerializedName("level") val level: String? = null,
    @SerializedName("category_scores") val categoryScores: CategoryScores? = null,
    @SerializedName("fired_rules") val firedRules: List<String>? = null,
    @SerializedName("reasons") val reasons: List<String>? = null,
    @SerializedName("killchain_stage") val killchainStage: String? = null,
    @SerializedName("verification") val verification: Verification? = null,
    @SerializedName("voice") val voice: VoiceEvidence? = null,
    @SerializedName("counterfactuals") val counterfactuals: List<Counterfactual>? = null,
    @SerializedName("transcript") val transcript: List<TranscriptSegment>? = null,
    @SerializedName("timeline") val timeline: List<TimelinePoint>? = null,
    @SerializedName("rag_citations") val ragCitations: List<String>? = null,
    @SerializedName("limitations") val limitations: List<String>? = null,
    @SerializedName("audit_hash") val auditHash: String? = null
)