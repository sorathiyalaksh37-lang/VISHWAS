package com.vishwas.app.audio

import android.Manifest
import android.content.Context
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.os.Build

/**
 * Feasibility auditor and capability checker for cellular call audio capture on Android.
 *
 * Evaluates whether the host app possesses the required system-level privileges
 * and legal consent to capture downstream cellular call audio.
 */
class CellularCapabilityChecker(private val context: Context) {

    companion object {
        const val PERMISSION_CAPTURE_AUDIO_OUTPUT = "android.permission.CAPTURE_AUDIO_OUTPUT"
        const val PRIVILEGED_PATH_INDICATOR = "/system/priv-app"
    }

    /**
     * Audit device environment and determine whether cellular audio capture is possible.
     */
    fun auditFeasibility(callerConsentAuthorized: Boolean = false): CellularCapabilityReport {
        val appInfo = context.applicationInfo
        val isSystem = (appInfo.flags and ApplicationInfo.FLAG_SYSTEM) != 0
        val isUpdatedSystem = (appInfo.flags and ApplicationInfo.FLAG_UPDATED_SYSTEM_APP) != 0
        val isPrivileged = (isSystem || isUpdatedSystem) || appInfo.sourceDir.contains(PRIVILEGED_PATH_INDICATOR)

        val hasCaptureAudioOutput = context.checkCallingOrSelfPermission(PERMISSION_CAPTURE_AUDIO_OUTPUT) ==
                PackageManager.PERMISSION_GRANTED
        val hasRecordAudio = context.checkCallingOrSelfPermission(Manifest.permission.RECORD_AUDIO) ==
                PackageManager.PERMISSION_GRANTED

        // Android 10+ (API 29+) explicitly prohibits 3rd party apps from capturing USAGE_VOICE_COMMUNICATION
        // without OEM signature or system privilege.
        val isTelephonyDownlinkFeasible = isPrivileged && hasCaptureAudioOutput

        val rationale = buildString {
            if (!isPrivileged) {
                append("Running as standard user-space APK. Android security model restricts cellular call audio (VOICE_DOWNLINK) ")
                append("to system apps installed in /system/priv-app/. ")
            }
            if (!hasCaptureAudioOutput) {
                append("Missing privileged permission 'android.permission.CAPTURE_AUDIO_OUTPUT' (protection level: signature|privileged). ")
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                append("Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT}) AudioPlaybackCaptureConfiguration restricts telephony audio capture. ")
            }
            if (!callerConsentAuthorized) {
                append("Remote party legal consent not authorized. Two-party consent laws require consent before voice capture. ")
            }
            if (isTelephonyDownlinkFeasible && callerConsentAuthorized) {
                append("Device possesses OEM system privileges and legal authorization for cellular downlink audio capture.")
            } else {
                append("Falling back safely to permitted non-audio companion detection.")
            }
        }

        val recommendedMode = if (isTelephonyDownlinkFeasible && callerConsentAuthorized) {
            AudioCaptureMode.CELLULAR_SYSTEM_PRIVILEGED
        } else {
            AudioCaptureMode.NON_AUDIO_COMPANION
        }

        return CellularCapabilityReport(
            isSystemApp = isSystem,
            isPrivilegedApp = isPrivileged,
            hasCaptureAudioOutputPermission = hasCaptureAudioOutput,
            hasRecordAudioPermission = hasRecordAudio,
            isTelephonyDownlinkSupported = isTelephonyDownlinkFeasible,
            isConsentAuthorized = callerConsentAuthorized,
            recommendedMode = recommendedMode,
            technicalRationale = rationale.trim()
        )
    }
}
