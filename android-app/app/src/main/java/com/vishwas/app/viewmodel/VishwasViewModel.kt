package com.vishwas.app.viewmodel

import android.app.Application
import android.net.Uri
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.vishwas.app.data.VishwasRepository
import com.vishwas.app.models.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * UI State for the main app
 */
data class VishwasUiState(
    val isBackendHealthy: Boolean = false,
    val backendVersion: String = "",
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val uploadProgress: UploadProgress? = null,
    val calls: List<CallListItem> = emptyList(),
    val selectedCall: AnalysisReportResponse? = null,
    val currentStatus: CallStatusResponse? = null
)

/**
 * Upload progress state
 */
data class UploadProgress(
    val callId: String,
    val filename: String,
    val status: ProcessingStatus,
    val message: String
)

/**
 * ViewModel for VISHWAS app
 */
class VishwasViewModel(application: Application) : AndroidViewModel(application) {
    
    private val repository = VishwasRepository(application)
    private val TAG = "VishwasViewModel"
    
    private val _uiState = MutableStateFlow(VishwasUiState())
    val uiState: StateFlow<VishwasUiState> = _uiState.asStateFlow()
    
    init {
        checkBackendHealth()
    }
    
    /**
     * Check backend health
     */
    fun checkBackendHealth() {
        viewModelScope.launch {
            repository.checkHealth().fold(
                onSuccess = { health ->
                    _uiState.value = _uiState.value.copy(
                        isBackendHealthy = health.status == "ok",
                        backendVersion = health.version
                    )
                },
                onFailure = { error ->
                    Log.e(TAG, "Health check failed", error)
                    _uiState.value = _uiState.value.copy(
                        isBackendHealthy = false,
                        errorMessage = "Backend unavailable: ${error.message}"
                    )
                }
            )
        }
    }
    
    /**
     * Upload a recording file
     */
    fun uploadRecording(uri: Uri, filename: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
            
            repository.uploadRecording(uri, filename).fold(
                onSuccess = { response ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        uploadProgress = UploadProgress(
                            callId = response.callId,
                            filename = filename,
                            status = response.status.toProcessingStatus(),
                            message = response.message
                        )
                    )
                    
                    // Start polling for status
                    pollCallStatus(response.callId)
                },
                onFailure = { error ->
                    Log.e(TAG, "Upload failed", error)
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = "Upload failed: ${error.message}"
                    )
                }
            )
        }
    }
    
    /**
     * Poll call status until complete or failed
     */
    private fun pollCallStatus(callId: String, maxAttempts: Int = 30) {
        viewModelScope.launch {
            var attempts = 0
            while (attempts < maxAttempts) {
                delay(1000) // Poll every second
                attempts++
                
                repository.getCallStatus(callId).fold(
                    onSuccess = { status ->
                        val processingStatus = status.status.toProcessingStatus()
                        _uiState.value = _uiState.value.copy(
                            currentStatus = status,
                            uploadProgress = _uiState.value.uploadProgress?.copy(
                                status = processingStatus,
                                message = "Status: ${status.status}"
                            )
                        )
                        
                        when (processingStatus) {
                            ProcessingStatus.COMPLETED -> {
                                // Load full report
                                loadReport(callId)
                                return@launch
                            }
                            ProcessingStatus.FAILED -> {
                                _uiState.value = _uiState.value.copy(
                                    errorMessage = "Analysis failed: ${status.errorMessage}"
                                )
                                return@launch
                            }
                            else -> {
                                // Continue polling
                            }
                        }
                    },
                    onFailure = { error ->
                        Log.e(TAG, "Status check failed", error)
                        // Continue polling unless it's a fatal error
                    }
                )
            }
            
            // Timeout
            _uiState.value = _uiState.value.copy(
                errorMessage = "Analysis timeout. Check history for results."
            )
        }
    }
    
    /**
     * Load analysis report
     */
    fun loadReport(callId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
            
            repository.getReport(callId).fold(
                onSuccess = { report ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        selectedCall = report
                    )
                },
                onFailure = { error ->
                    Log.e(TAG, "Load report failed", error)
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = "Failed to load report: ${error.message}"
                    )
                }
            )
        }
    }
    
    /**
     * Load call history
     */
    fun loadHistory() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
            
            repository.listCalls(page = 1, pageSize = 50).fold(
                onSuccess = { response ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        calls = response.calls
                    )
                },
                onFailure = { error ->
                    Log.e(TAG, "Load history failed", error)
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = "Failed to load history: ${error.message}"
                    )
                }
            )
        }
    }
    
    /**
     * Clear selected call
     */
    fun clearSelectedCall() {
        _uiState.value = _uiState.value.copy(selectedCall = null)
    }
    
    /**
     * Clear error message
     */
    fun clearError() {
        _uiState.value = _uiState.value.copy(errorMessage = null)
    }
    
    /**
     * Clear upload progress
     */
    fun clearUploadProgress() {
        _uiState.value = _uiState.value.copy(uploadProgress = null)
    }
}
