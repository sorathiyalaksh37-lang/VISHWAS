package com.vishwas.app.data

import android.content.Context
import android.net.Uri
import android.util.Log
import com.vishwas.app.models.*
import com.vishwas.app.network.RetrofitClient
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
                val resolvedName = run {
                    var displayName: String? = null
                    context.contentResolver.query(uri, null, null, null, null)?.use { c ->
                        val idx = c.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
                        if (idx >= 0 && c.moveToFirst()) displayName = c.getString(idx)
                    }
                    val base = displayName ?: filename
                    if (base.contains('.')) base else {
                        val ext = android.webkit.MimeTypeMap.getSingleton()
                            .getExtensionFromMimeType(context.contentResolver.getType(uri)) ?: "mp3"
                        "$base.$ext"
                    }
                }
                val tempFile = File(context.cacheDir, "upload_$resolvedName")
                context.contentResolver.openInputStream(uri)?.use { input ->
                    tempFile.outputStream().use { output ->
                        input.copyTo(output)
                    }
                }
                
                // Create multipart body
                val requestBody = tempFile.asRequestBody("audio/*".toMediaTypeOrNull())
                val filePart = MultipartBody.Part.createFormData("file", resolvedName, requestBody)
                
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
}
