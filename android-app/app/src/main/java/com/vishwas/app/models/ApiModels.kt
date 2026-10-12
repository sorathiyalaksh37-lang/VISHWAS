package com.vishwas.app.models

import com.google.gson.annotations.SerializedName

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
 * Call status response
 */
data class CallStatusResponse(
    @SerializedName("call_id") val callId: String,
    val status: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String,
    @SerializedName("completed_at") val completedAt: String?,
    @SerializedName("error_message") val errorMessage: String?
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
    val segments: List<TranscriptSegment>,
    @SerializedName("is_mock") val isMock: Boolean
)

/**
 * Agent finding
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

/**
 * Analysis report response
 */
data class AnalysisReportResponse(
    @SerializedName("call_id") val callId: String,
    val status: String,
    @SerializedName("analysis_mode") val analysisMode: String,
    val language: String?,
    val transcript: TranscriptResponse?,
    @SerializedName("agent_findings") val agentFindings: List<AgentFinding>,
    @SerializedName("risk_level") val riskLevel: String,
    @SerializedName("risk_score") val riskScore: Float?,
    val reasons: List<String>,
    @SerializedName("recommended_actions") val recommendedActions: List<String>,
    val warnings: List<String>,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("completed_at") val completedAt: String?,
    @SerializedName("is_mock") val isMock: Boolean
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
