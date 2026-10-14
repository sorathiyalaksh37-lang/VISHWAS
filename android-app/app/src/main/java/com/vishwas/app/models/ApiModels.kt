package com.vishwas.app.models

import com.google.gson.annotations.SerializedName

/**
 * Auth — login request
 */
data class LoginRequest(
    val email: String,
    val password: String
)

/**
 * Auth — register request
 */
data class RegisterRequest(
    val email: String,
    val password: String,
    @SerializedName("full_name") val fullName: String? = null
)

/**
 * Auth — user profile
 */
data class UserResponse(
    val id: String,
    val email: String,
    @SerializedName("full_name") val fullName: String?,
    @SerializedName("is_active") val isActive: Boolean,
    @SerializedName("created_at") val createdAt: String
)

/**
 * Auth — login / register response
 */
data class AuthResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("token_type") val tokenType: String,
    val user: UserResponse
)

/**
 * Health check response
 */
data class HealthResponse(
    val status: String,
    val service: String,
    val version: String
)

/**
 * Upload response
 */
data class UploadResponse(
    @SerializedName("call_id") val callId: String,
    val status: String,
    val message: String,
    @SerializedName("analysis_mode") val analysisMode: String
)

/**
 * Call status response — v3 contract.
 * Job-level failure is reported via `error` (nullable string), not `error_message`.
 */
data class CallStatusResponse(
    @SerializedName("call_id") val callId: String,
    val status: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String,
    @SerializedName("completed_at") val completedAt: String?,
    @SerializedName("error") val error: String?          // v3: was error_message
)

/**
 * Call list item
 */
data class CallListItem(
    @SerializedName("call_id") val callId: String,
    @SerializedName("original_filename") val originalFilename: String,
    val status: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String
)

/**
 * Pagination info
 */
data class PaginationInfo(
    val page: Int,
    @SerializedName("page_size") val pageSize: Int,
    val total: Int,
    val pages: Int
)

/**
 * Call list response
 */
data class CallListResponse(
    val calls: List<CallListItem>,
    val pagination: PaginationInfo
)

/**
 * Transcript segment
 */
data class TranscriptSegment(
    val start: Float,
    val end: Float,
    val speaker: String?,
    val text: String,
    val language: String?
)

/**
 * Transcript response
 */
data class TranscriptResponse(
    @SerializedName("call_id") val callId: String,
    val language: String?,
    @SerializedName("transcription_status") val transcriptionStatus: String,
    val segments: List<TranscriptSegment>
)

/**
 * Agent finding (legacy — kept for backward compat with current backend)
 */
data class AgentFinding(
    val agent: String,
    val signal: String,
    val severity: String,
    @SerializedName("evidence_text") val evidenceText: String,
    @SerializedName("start_time") val startTime: Float?,
    @SerializedName("end_time") val endTime: Float?,
    val confidence: Float?,
    val source: String
)

// ── v3 nested models ───────────────────────────────────────────────────────────

/**
 * Per-category risk score breakdown
 * Caps: identity 25, request 30, behavior 20, channel 15, voice 10
 */
data class CategoryScores(
    @SerializedName("identity") val identity: Int? = null,
    @SerializedName("request") val request: Int? = null,
    @SerializedName("behavior") val behavior: Int? = null,
    @SerializedName("channel") val channel: Int? = null,
    @SerializedName("voice") val voice: Int? = null
)

/**
 * Suggested verification action for the user
 */
data class Verification(
    @SerializedName("action") val action: String? = null,
    @SerializedName("target") val target: String? = null,
    @SerializedName("safe_word_prompt") val safeWordPrompt: Boolean? = null
)

/**
 * Speaker match result from voice layer
 */
data class SpeakerMatch(
    @SerializedName("claimed_contact") val claimedContact: String? = null,
    @SerializedName("similarity") val similarity: Double? = null,
    @SerializedName("enrolled") val enrolled: Boolean? = null
)

/**
 * Audio quality metadata from voice layer
 */
data class VoiceQuality(
    @SerializedName("duration_s") val durationS: Double? = null,
    @SerializedName("snr_db") val snrDb: Double? = null
)

/**
 * Voice layer analysis result
 */
data class VoiceEvidence(
    @SerializedName("status") val status: String? = null,       // ok | inconclusive | unavailable
    @SerializedName("spoof_prob") val spoofProb: Double? = null,
    @SerializedName("windows_analyzed") val windowsAnalyzed: Int? = null,
    @SerializedName("speaker_match") val speakerMatch: SpeakerMatch? = null,
    @SerializedName("quality") val quality: VoiceQuality? = null,
    @SerializedName("model") val model: String? = null
)

/**
 * Counterfactual: "what would lower the risk score?"
 */
data class Counterfactual(
    @SerializedName("change") val change: String? = null,
    @SerializedName("new_score") val newScore: Int? = null
)

/**
 * Analysis report response — v3 contract.
 * `level` replaces `risk_level`; `score` (Int 0-100) replaces `risk_score` (Float).
 * Uppercase enum: LOW | MEDIUM | HIGH | CRITICAL (normalised by backend validator).
 */
data class AnalysisReportResponse(
    @SerializedName("call_id") val callId: String,
    val status: String,
    @SerializedName("analysis_mode") val analysisMode: String,
    val language: String?,
    val transcript: TranscriptResponse?,

    // ── v3 primary fields ──────────────────────────────────────────────────────
    @SerializedName("level") val level: String,                             // HIGH | CRITICAL | MEDIUM | LOW
    @SerializedName("score") val score: Int,                                // 0-100
    @SerializedName("category_scores") val categoryScores: CategoryScores? = null,
    @SerializedName("fired_rules") val firedRules: List<String> = emptyList(),
    @SerializedName("killchain_stage") val killchainStage: String? = null,
    @SerializedName("verification") val verification: Verification? = null,
    @SerializedName("voice") val voice: VoiceEvidence? = null,
    @SerializedName("counterfactuals") val counterfactuals: List<Counterfactual> = emptyList(),

    // ── legacy / backward-compat fields ────────────────────────────────────────
    @SerializedName("agent_findings") val agentFindings: List<AgentFinding> = emptyList(),
    @SerializedName("reasons") val reasons: List<String> = emptyList(),
    @SerializedName("recommended_actions") val recommendedActions: List<String> = emptyList(),
    @SerializedName("warnings") val warnings: List<String> = emptyList(),
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("completed_at") val completedAt: String?
)

/**
 * UI state for processing status
 */
enum class ProcessingStatus {
    QUEUED,
    PROCESSING,
    COMPLETED,
    FAILED,
    UNKNOWN
}

fun String.toProcessingStatus(): ProcessingStatus {
    return when (this.lowercase()) {
        "queued" -> ProcessingStatus.QUEUED
        "processing" -> ProcessingStatus.PROCESSING
        "completed" -> ProcessingStatus.COMPLETED
        "failed" -> ProcessingStatus.FAILED
        else -> ProcessingStatus.UNKNOWN
    }
}
