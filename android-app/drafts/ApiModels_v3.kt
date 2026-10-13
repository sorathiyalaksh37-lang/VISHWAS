@'
package com.vishwas.app.models

import com.google.gson.annotations.SerializedName

// Draft v3 models, matching the contract frozen in Task 1.
// Every field is nullable because the backend does not return all of them yet.
// Fields marked CONFIRM are not fully specified in the contract; check with M2.

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
    @SerializedName("safe_word_prompt") val safeWordPrompt: String? = null
)

data class SpeakerMatch(
    @SerializedName("matched") val matched: Boolean? = null,        // CONFIRM
    @SerializedName("similarity") val similarity: Double? = null    // CONFIRM
)

data class VoiceEvidence(
    @SerializedName("status") val status: String? = null,           // CONFIRM values
    @SerializedName("spoof_prob") val spoofProb: Double? = null,
    @SerializedName("speaker_match") val speakerMatch: SpeakerMatch? = null
)

data class Counterfactual(
    @SerializedName("description") val description: String? = null, // CONFIRM
    @SerializedName("score_change") val scoreChange: Int? = null    // CONFIRM
)

data class TimelinePoint(
    @SerializedName("t") val t: Double? = null,                     // CONFIRM
    @SerializedName("score") val score: Int? = null,                // CONFIRM
    @SerializedName("event") val event: String? = null              // CONFIRM
)

data class AnalysisReportResponse(
    @SerializedName("call_id") val callId: String? = null,
    @SerializedName("status") val status: String? = null,
    @SerializedName("analysis_mode") val analysisMode: String? = null,
    @SerializedName("is_mock") val isMock: Boolean? = null,

    // v3 fields
    @SerializedName("score") val score: Int? = null,
    @SerializedName("level") val level: String? = null,             // LOW, MEDIUM, HIGH, CRITICAL
    @SerializedName("category_scores") val categoryScores: CategoryScores? = null,
    @SerializedName("fired_rules") val firedRules: List<String>? = null,
    @SerializedName("reasons") val reasons: List<String>? = null,
    @SerializedName("killchain_stage") val killchainStage: String? = null,
    @SerializedName("verification") val verification: Verification? = null,
    @SerializedName("voice") val voice: VoiceEvidence? = null,
    @SerializedName("counterfactuals") val counterfactuals: List<Counterfactual>? = null,
    @SerializedName("timeline") val timeline: List<TimelinePoint>? = null,

    // Legacy fields the current mock still sends. Remove after M2 upgrades the backend.
    @SerializedName("risk_level") val riskLevel: String? = null,
    @SerializedName("risk_score") val riskScore: Double? = null,
    @SerializedName("recommended_actions") val recommendedActions: List<String>? = null,
    @SerializedName("warnings") val warnings: List<String>? = null,
    @SerializedName("created_at") val createdAt: String? = null,
    @SerializedName("completed_at") val completedAt: String? = null
)
'@ | Set-Content -Path android-app\drafts\ApiModels_v3.kt -Encoding utf8