package com.vishwas.app.data

import android.content.Context
import android.net.Uri
import android.util.Log
import com.vishwas.app.models.*
import com.vishwas.app.network.RetrofitClient
import com.vishwas.app.network.TokenManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File

/**
 * Repository for VISHWAS API operations
 */
class VishwasRepository(private val context: Context) {
    
    private val api = RetrofitClient.apiService
    private val TAG = "VishwasRepository"

    // ── Authentication ──────────────────────────────────────────────────

    suspend fun login(email: String, password: String): Result<AuthResponse> =
        withContext(Dispatchers.IO) {
            try {
                val response = api.login(LoginRequest(email, password))
                if (response.isSuccessful && response.body() != null) {
                    val auth = response.body()!!
                    TokenManager.saveToken(auth.accessToken, auth.user.email)
                    Result.success(auth)
                } else {
                    val msg = response.errorBody()?.string() ?: "Login failed (${response.code()})"
                    Result.failure(Exception(msg))
                }
            } catch (e: Exception) {
                Log.e(TAG, "Login error", e)
                Result.failure(e)
            }
        }

    suspend fun register(email: String, password: String, fullName: String? = null): Result<AuthResponse> =
        withContext(Dispatchers.IO) {
            try {
                val response = api.register(RegisterRequest(email, password, fullName))
                if (response.isSuccessful && response.body() != null) {
                    val auth = response.body()!!
                    TokenManager.saveToken(auth.accessToken, auth.user.email)
                    Result.success(auth)
                } else {
                    val msg = response.errorBody()?.string() ?: "Registration failed (${response.code()})"
                    Result.failure(Exception(msg))
                }
            } catch (e: Exception) {
                Log.e(TAG, "Register error", e)
                Result.failure(e)
            }
        }

    fun logout() {
        TokenManager.clear()
    }

    fun isLoggedIn(): Boolean = TokenManager.isLoggedIn()

    suspend fun getCurrentUser(): Result<UserResponse> =
        withContext(Dispatchers.IO) {
            try {
                val response = api.getMe()
                if (response.isSuccessful && response.body() != null) {
                    Result.success(response.body()!!)
                } else {
                    Result.failure(Exception("Failed to get user: ${response.code()}"))
                }
            } catch (e: Exception) {
                Log.e(TAG, "Get current user error", e)
                Result.failure(e)
            }
        }
    
    /**
     * Check backend health
     */
    suspend fun checkHealth(): Result<HealthResponse> = withContext(Dispatchers.IO) {
        try {
            val response = api.healthCheck()
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Health check failed: ${response.code()}"))
            }
        } catch (e: Exception) {
            Log.e(TAG, "Health check error", e)
            Result.failure(e)
        }
    }
    
    /**
     * Upload a recording file
     */
    suspend fun uploadRecording(uri: Uri, filename: String): Result<UploadResponse> = 
        withContext(Dispatchers.IO) {
            try {
                // Copy URI content to temp file
                val tempFile = File(context.cacheDir, "upload_$filename")
                context.contentResolver.openInputStream(uri)?.use { input ->
                    tempFile.outputStream().use { output ->
                        input.copyTo(output)
                    }
                }
                
                // Create multipart body
                val requestBody = tempFile.asRequestBody("audio/*".toMediaTypeOrNull())
                val filePart = MultipartBody.Part.createFormData("file", filename, requestBody)
                
                // Upload
                val response = api.uploadRecording(filePart)
                
                // Cleanup temp file
                tempFile.delete()
                
                if (response.isSuccessful && response.body() != null) {
                    Result.success(response.body()!!)
                } else {
                    Result.failure(Exception("Upload failed: ${response.code()} - ${response.errorBody()?.string()}"))
                }
            } catch (e: Exception) {
                Log.e(TAG, "Upload error", e)
                Result.failure(e)
            }
        }
    
    /**
     * List all calls
     */
    suspend fun listCalls(page: Int = 1, pageSize: Int = 20): Result<CallListResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val response = api.listCalls(page, pageSize)
                if (response.isSuccessful && response.body() != null) {
                    Result.success(response.body()!!)
                } else {
                    Result.failure(Exception("Failed to list calls: ${response.code()}"))
                }
            } catch (e: Exception) {
                Log.e(TAG, "List calls error", e)
                Result.failure(e)
            }
        }
    
    /**
     * Get call status
     */
    suspend fun getCallStatus(callId: String): Result<CallStatusResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val response = api.getCallStatus(callId)
                if (response.isSuccessful && response.body() != null) {
                    Result.success(response.body()!!)
                } else {
                    Result.failure(Exception("Failed to get status: ${response.code()}"))
                }
            } catch (e: Exception) {
                Log.e(TAG, "Get status error", e)
                Result.failure(e)
            }
        }
    
    /**
     * Get transcript
     */
    suspend fun getTranscript(callId: String): Result<TranscriptResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val response = api.getTranscript(callId)
                if (response.isSuccessful && response.body() != null) {
                    Result.success(response.body()!!)
                } else {
                    Result.failure(Exception("Failed to get transcript: ${response.code()}"))
                }
            } catch (e: Exception) {
                Log.e(TAG, "Get transcript error", e)
                Result.failure(e)
            }
        }
    
    /**
     * Get analysis report
     */
    suspend fun getReport(callId: String): Result<AnalysisReportResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val response = api.getReport(callId)
                if (response.isSuccessful && response.body() != null) {
                    Result.success(response.body()!!)
                } else if (response.code() == 425) {
                    Result.failure(Exception("Analysis in progress"))
                } else {
                    Result.failure(Exception("Failed to get report: ${response.code()}"))
                }
            } catch (e: Exception) {
                Log.e(TAG, "Get report error", e)
                Result.failure(e)
            }
        }
    
    // ── Streaming Voice Detection methods ─────────────────────────────────────
    
    /**
     * Start streaming voice detection session
     */
    suspend fun startVoiceStream(): Result<StreamSessionResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val response = api.startVoiceStream()
                if (response.isSuccessful && response.body() != null) {
                    Result.success(response.body()!!)
                } else {
                    Result.failure(Exception("Failed to start voice stream: ${response.code()} - ${response.errorBody()?.string()}"))
                }
            } catch (e: Exception) {
                Log.e(TAG, "Start voice stream error", e)
                Result.failure(e)
            }
        }
    
    /**
     * Send audio chunk to streaming voice detection session
     */
    suspend fun sendVoiceChunk(sessionId: String, chunkBytes: ByteArray): Result<StreamChunkResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val requestBody = okhttp3.RequestBody.create(
                    "audio/raw".toMediaTypeOrNull(),
                    chunkBytes
                )
                val chunkPart = MultipartBody.Part.createFormData("chunk", "audio.raw", requestBody)
                
                val response = api.sendVoiceChunk(sessionId, chunkPart)
                
                when {
                    response.isSuccessful && response.body() != null -> {
                        Result.success(response.body()!!)
                    }
                    response.code() == 404 -> {
                        Result.failure(Exception("Session expired - please restart"))
                    }
                    response.code() == 503 -> {
                        Result.failure(Exception("Voice detection service unavailable"))
                    }
                    else -> {
                        Result.failure(Exception("Failed to send chunk: ${response.code()} - ${response.errorBody()?.string()}"))
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Send voice chunk error", e)
                Result.failure(e)
            }
        }
    
    /**
     * Delete streaming voice detection session
     */
    suspend fun deleteVoiceStream(sessionId: String): Result<StreamDeleteResponse> = 
        withContext(Dispatchers.IO) {
            try {
                val response = api.deleteVoiceStream(sessionId)
                if (response.isSuccessful && response.body() != null) {
                    Result.success(response.body()!!)
                } else {
                    Result.failure(Exception("Failed to delete voice stream: ${response.code()}"))
                }
            } catch (e: Exception) {
                Log.e(TAG, "Delete voice stream error", e)
                Result.failure(e)
            }
        }
}
