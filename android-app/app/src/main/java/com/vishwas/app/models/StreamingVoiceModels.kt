package com.vishwas.app.models

import com.google.gson.annotations.SerializedName

/**
 * Response from POST /api/v1/voice-detection/stream/start
 */
data class StreamSessionResponse(
    @SerializedName("session_id") val sessionId: String,
    @SerializedName("status") val status: String,
    @SerializedName("chunk_size_bytes") val chunkSizeBytes: Int,
    @SerializedName("format") val format: String,
    @SerializedName("max_duration_minutes") val maxDurationMinutes: Int,
    @SerializedName("ttl_minutes") val ttlMinutes: Int
)

/**
 * Response from POST /api/v1/voice-detection/stream/{session_id}/chunk
 */
data class StreamChunkResponse(
    @SerializedName("status") val status: String,
    @SerializedName("label") val label: String,
    @SerializedName("spoof_prob") val spoofProb: Double?,
    @SerializedName("confidence") val confidence: String,
    @SerializedName("duration_analyzed_ms") val durationAnalyzedMs: Int,
    @SerializedName("chunks_processed") val chunksProcessed: Int
)

/**
 * Response from DELETE /api/v1/voice-detection/stream/{session_id}
 */
data class StreamDeleteResponse(
    @SerializedName("session_id") val sessionId: String,
    @SerializedName("status") val status: String,
    @SerializedName("message") val message: String
)
