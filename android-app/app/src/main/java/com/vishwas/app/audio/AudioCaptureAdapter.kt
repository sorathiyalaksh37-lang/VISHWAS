package com.vishwas.app.audio

/**
 * Capture source mode for VISHWAS call fraud analysis.
 */
enum class AudioCaptureMode {
    /** Internet / WebRTC call prototype where two-way audio streaming is permitted with RECORD_AUDIO. */
    WEBRTC_INTERNET_CALL,

    /** Cellular audio stream requiring privileged OEM / system service access (/system/priv-app/). */
    CELLULAR_SYSTEM_PRIVILEGED,

    /** Non-audio fallback companion when cellular audio capture or remote caller consent is unavailable. */
    NON_AUDIO_COMPANION
}

/**
 * Diagnostic report on cellular call audio capture feasibility for the current device.
 */
data class CellularCapabilityReport(
    val isSystemApp: Boolean,
    val isPrivilegedApp: Boolean,
    val hasCaptureAudioOutputPermission: Boolean,
    val hasRecordAudioPermission: Boolean,
    val isTelephonyDownlinkSupported: Boolean,
    val isConsentAuthorized: Boolean,
    val recommendedMode: AudioCaptureMode,
    val technicalRationale: String
) {
    /** True if real hardware cellular downstream audio capture is feasible. */
    val canCaptureCellularAudio: Boolean
        get() = isPrivilegedApp && hasCaptureAudioOutputPermission && isConsentAuthorized
}

/**
 * Common interface for audio capture sources in the VISHWAS mobile client.
 */
interface AudioCaptureAdapter {
    val mode: AudioCaptureMode

    /** Check if this capture source is feasible on the current device and environment. */
    fun checkCapabilities(): CellularCapabilityReport

    /** Start streaming audio frames. */
    fun startCapture(
        onChunk: (chunk: ByteArray, sequence: Long, timestampMs: Long) -> Unit,
        onError: (message: String) -> Unit
    )

    /** Stop capturing audio. */
    fun stopCapture()

    /** Returns true if capture is currently active. */
    fun isCapturing(): Boolean
}
