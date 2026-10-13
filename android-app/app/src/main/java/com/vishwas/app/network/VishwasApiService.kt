package com.vishwas.app.network

import com.vishwas.app.models.*
import okhttp3.MultipartBody
import retrofit2.Response
import retrofit2.http.*

/**
 * Retrofit API service for VISHWAS backend
 */
interface VishwasApiService {
    
    @GET("health")
    suspend fun healthCheck(): Response<HealthResponse>
    
    @Multipart
    @POST("calls")
    suspend fun uploadRecording(
        @Part file: MultipartBody.Part
    ): Response<UploadResponse>
    
    @GET("calls")
    suspend fun listCalls(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 20
    ): Response<CallListResponse>
    
    @GET("calls/{call_id}/status")
    suspend fun getCallStatus(
        @Path("call_id") callId: String
    ): Response<CallStatusResponse>
    
    @GET("calls/{call_id}/transcript")
    suspend fun getTranscript(
        @Path("call_id") callId: String
    ): Response<TranscriptResponse>
    
    @GET("calls/{call_id}/report")
    suspend fun getReport(
        @Path("call_id") callId: String
    ): Response<AnalysisReportResponse>
    
    // ── Streaming Voice Detection endpoints ───────────────────────────────────
    
    @POST("voice-detection/stream/start")
    suspend fun startVoiceStream(): Response<StreamSessionResponse>
    
    @Multipart
    @POST("voice-detection/stream/{session_id}/chunk")
    suspend fun sendVoiceChunk(
        @Path("session_id") sessionId: String,
        @Part chunk: MultipartBody.Part
    ): Response<StreamChunkResponse>
    
    @DELETE("voice-detection/stream/{session_id}")
    suspend fun deleteVoiceStream(
        @Path("session_id") sessionId: String
    ): Response<StreamDeleteResponse>
}
