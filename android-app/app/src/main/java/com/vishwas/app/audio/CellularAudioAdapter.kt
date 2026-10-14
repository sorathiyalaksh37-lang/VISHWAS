package com.vishwas.app.audio

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Log
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Audio capture adapter for cellular voice calls.
 *
 * Implements capability verification and runtime safeguards:
 * 1. Checks system-level permissions and /system/priv-app/ installation.
 * 2. If privileges or caller consent are unavailable, refuses to capture audio and
 *    signals explicit transition to Non-Audio Companion mode.
 * 3. Never mocks or falsifies real cellular audio streaming.
 */
class CellularAudioAdapter(
    private val context: Context,
    private val callerConsentAuthorized: Boolean = false,
    private val onFallbackToNonAudio: (rationale: String) -> Unit = {}
) : AudioCaptureAdapter {

    companion object {
        private const val TAG = "CellularAudioAdapter"
        private const val SAMPLE_RATE = 16000
        private const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
        private const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
    }

    override val mode: AudioCaptureMode
        get() = AudioCaptureMode.CELLULAR_SYSTEM_PRIVILEGED

    private val capabilityChecker = CellularCapabilityChecker(context)
    private val isRunning = AtomicBoolean(false)
    private var audioRecord: AudioRecord? = null
    private var recordingThread: Thread? = null

    override fun checkCapabilities(): CellularCapabilityReport {
        return capabilityChecker.auditFeasibility(callerConsentAuthorized)
    }

    @SuppressLint("MissingPermission")
    override fun startCapture(
        onChunk: (chunk: ByteArray, sequence: Long, timestampMs: Long) -> Unit,
        onError: (message: String) -> Unit
    ) {
        val capability = checkCapabilities()
        Log.i(TAG, "Starting cellular audio capture audit: $capability")

        if (!capability.canCaptureCellularAudio) {
            val msg = "Cellular call audio capture not feasible: ${capability.technicalRationale}"
            Log.w(TAG, msg)
            onError(msg)
            // Trigger automatic fallback to permitted Non-Audio Companion Mode
            onFallbackToNonAudio(capability.technicalRationale)
            return
        }

        try {
            val bufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
                .coerceAtLeast(3200)

            // VOICE_CALL requires android.permission.CAPTURE_AUDIO_OUTPUT (privileged OEM)
            @Suppress("DEPRECATION")
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.VOICE_CALL,
                SAMPLE_RATE,
                CHANNEL_CONFIG,
                AUDIO_FORMAT,
                bufferSize
            )

            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                val initError = "AudioRecord failed to initialize with VOICE_CALL audio source"
                Log.e(TAG, initError)
                onError(initError)
                onFallbackToNonAudio(initError)
                return
            }

            audioRecord?.startRecording()
            isRunning.set(true)

            recordingThread = Thread({
                var sequence: Long = 0
                val buffer = ByteArray(bufferSize)

                while (isRunning.get()) {
                    val bytesRead = audioRecord?.read(buffer, 0, buffer.size) ?: -1
                    if (bytesRead > 0) {
                        sequence++
                        val chunkCopy = buffer.copyOf(bytesRead)
                        val timestampMs = System.currentTimeMillis()
                        onChunk(chunkCopy, sequence, timestampMs)
                    } else if (bytesRead < 0) {
                        Log.e(TAG, "AudioRecord read error code: $bytesRead")
                        break
                    }
                }
            }, "CellularAudioCaptureThread").apply { start() }

        } catch (e: SecurityException) {
            val secMsg = "SecurityException accessing cellular audio source: ${e.message}"
            Log.e(TAG, secMsg, e)
            onError(secMsg)
            onFallbackToNonAudio(secMsg)
        } catch (e: Exception) {
            val err = "Unexpected error starting cellular audio capture: ${e.message}"
            Log.e(TAG, err, e)
            onError(err)
            onFallbackToNonAudio(err)
        }
    }

    override fun stopCapture() {
        isRunning.set(false)
        try {
            recordingThread?.join(500)
            audioRecord?.stop()
            audioRecord?.release()
        } catch (e: Exception) {
            Log.w(TAG, "Error stopping cellular audio capture: ${e.message}")
        } finally {
            audioRecord = null
            recordingThread = null
        }
    }

    override fun isCapturing(): Boolean = isRunning.get()
}
