package com.vishwas.app.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import android.media.MediaRecorder
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.vishwas.app.models.ProcessingStatus
import com.vishwas.app.viewmodel.VishwasViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import java.io.File
import java.util.Locale

private enum class RecordState {
    IDLE,
    RECORDING,
    RECORDED,
    UPLOADING
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RecordScreen(
    viewModel: VishwasViewModel,
    onNavigateBack: () -> Unit,
    onNavigateToResults: (String) -> Unit
) {
    val context = LocalContext.current
    val uiState by viewModel.uiState.collectAsState()

    var hasPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.RECORD_AUDIO
            ) == PackageManager.PERMISSION_GRANTED
        )
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        hasPermission = isGranted
    }

    var recordState by remember { mutableStateOf(RecordState.IDLE) }
    var mediaRecorder by remember { mutableStateOf<MediaRecorder?>(null) }
    var outputFile by remember { mutableStateOf<File?>(null) }
    var elapsedSeconds by remember { mutableStateOf(0) }
    var recordedDurationSeconds by remember { mutableStateOf(0) }
    var recordErrorMessage by remember { mutableStateOf<String?>(null) }

    // Check if analysis completed (matching UploadScreen.kt logic)
    LaunchedEffect(uiState.uploadProgress) {
        val progress = uiState.uploadProgress
        if (progress != null && progress.status == ProcessingStatus.COMPLETED) {
            val id = progress.callId
            viewModel.clearUploadProgress()
            onNavigateToResults(id)
        }
    }

    // If upload/analysis fails, drop back to RECORDED so the user can retry
    LaunchedEffect(uiState.errorMessage) {
        if (uiState.errorMessage != null && recordState == RecordState.UPLOADING) {
            recordState = RecordState.RECORDED
        }
    }

    // Elapsed-time timer during RECORDING state
    LaunchedEffect(recordState) {
        if (recordState == RecordState.RECORDING) {
            elapsedSeconds = 0
            while (isActive) {
                delay(1000)
                elapsedSeconds++
            }
        }
    }

    // Release MediaRecorder on dispose so mic is never left open
    DisposableEffect(Unit) {
        onDispose {
            try {
                mediaRecorder?.apply {
                    stop()
                    release()
                }
            } catch (_: Exception) {}
            mediaRecorder = null
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Record Call") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            if (!hasPermission) {
                Spacer(modifier = Modifier.height(32.dp))
                Icon(
                    imageVector = Icons.Default.MicOff,
                    contentDescription = null,
                    modifier = Modifier.size(64.dp),
                    tint = MaterialTheme.colorScheme.error
                )
                Text(
                    text = "Microphone permission is required to record",
                    style = MaterialTheme.typography.bodyLarge,
                    textAlign = TextAlign.Center
                )
                Button(
                    onClick = { permissionLauncher.launch(Manifest.permission.RECORD_AUDIO) },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Request Permission")
                }
            } else {
                when (recordState) {
                    RecordState.IDLE -> {
                        Text(
                            text = "Record audio from your device's microphone to analyze for fraud indicators.",
                            style = MaterialTheme.typography.bodyLarge,
                            textAlign = TextAlign.Center
                        )

                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(
                                containerColor = MaterialTheme.colorScheme.secondaryContainer
                            )
                        ) {
                            Column(
                                modifier = Modifier.padding(16.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Text("Recording Format:", style = MaterialTheme.typography.titleSmall)
                                Text("• Audio format: MPEG-4 / AAC (.m4a)", style = MaterialTheme.typography.bodySmall)
                                Text("• Stored in app cache for analysis", style = MaterialTheme.typography.bodySmall)
                            }
                        }

                        Spacer(modifier = Modifier.height(16.dp))

                        Button(
                            onClick = {
                                try {
                                    recordErrorMessage = null
                                    val outputDir = File(context.cacheDir, "recordings").apply { mkdirs() }
                                    val file = File(outputDir, "recording_${System.currentTimeMillis()}.m4a")
                                    val recorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                                        MediaRecorder(context)
                                    } else {
                                        @Suppress("DEPRECATION")
                                        MediaRecorder()
                                    }
                                    recorder.apply {
                                        setAudioSource(MediaRecorder.AudioSource.MIC)
                                        setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
                                        setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
                                        setOutputFile(file.absolutePath)
                                        prepare()
                                        start()
                                    }
                                    mediaRecorder = recorder
                                    outputFile = file
                                    recordState = RecordState.RECORDING
                                } catch (e: Exception) {
                                    try {
                                        mediaRecorder?.release()
                                    } catch (_: Exception) {}
                                    mediaRecorder = null
                                    outputFile = null
                                    recordErrorMessage = "Failed to start recording: ${e.message}"
                                    recordState = RecordState.IDLE
                                }
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Icon(Icons.Default.Mic, contentDescription = null)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Start Recording")
                        }
                    }

                    RecordState.RECORDING -> {
                        val minutes = elapsedSeconds / 60
                        val seconds = elapsedSeconds % 60
                        val timeFormatted = String.format(Locale.US, "%02d:%02d", minutes, seconds)

                        Spacer(modifier = Modifier.height(32.dp))

                        Icon(
                            imageVector = Icons.Default.RadioButtonChecked,
                            contentDescription = "Recording",
                            modifier = Modifier.size(64.dp),
                            tint = MaterialTheme.colorScheme.error
                        )

                        Text(
                            text = "Recording in progress...",
                            style = MaterialTheme.typography.titleMedium
                        )

                        Text(
                            text = timeFormatted,
                            style = MaterialTheme.typography.displayMedium,
                            color = MaterialTheme.colorScheme.primary
                        )

                        Spacer(modifier = Modifier.height(24.dp))

                        Button(
                            onClick = {
                                try {
                                    mediaRecorder?.apply {
                                        stop()
                                        release()
                                    }
                                    mediaRecorder = null
                                    recordedDurationSeconds = elapsedSeconds
                                    recordState = RecordState.RECORDED
                                } catch (e: Exception) {
                                    try {
                                        mediaRecorder?.release()
                                    } catch (_: Exception) {}
                                    mediaRecorder = null
                                    recordErrorMessage = "Failed to stop recording: ${e.message}"
                                    recordState = RecordState.IDLE
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = MaterialTheme.colorScheme.error
                            )
                        ) {
                            Icon(Icons.Default.Stop, contentDescription = null)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Stop Recording")
                        }
                    }

                    RecordState.RECORDED -> {
                        val minutes = recordedDurationSeconds / 60
                        val seconds = recordedDurationSeconds % 60
                        val durationFormatted = String.format(Locale.US, "%02d:%02d", minutes, seconds)

                        Card(
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Column(
                                modifier = Modifier.padding(16.dp),
                                verticalArrangement = Arrangement.spacedBy(4.dp)
                            ) {
                                Text("Recorded File:", style = MaterialTheme.typography.titleSmall)
                                Text(outputFile?.name ?: "Unknown", style = MaterialTheme.typography.bodyMedium)
                                Spacer(modifier = Modifier.height(4.dp))
                                Text("Duration:", style = MaterialTheme.typography.titleSmall)
                                Text(durationFormatted, style = MaterialTheme.typography.bodyMedium)
                            }
                        }

                        Button(
                            onClick = {
                                outputFile?.let { file ->
                                    recordState = RecordState.UPLOADING
                                    val uri = FileProvider.getUriForFile(
                                        context,
                                        "com.vishwas.app.fileprovider",
                                        file
                                    )
                                    viewModel.uploadRecording(uri, file.name)
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                            enabled = !uiState.isLoading
                        ) {
                            Icon(Icons.Default.Upload, contentDescription = null)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Analyze This Recording")
                        }

                        OutlinedButton(
                            onClick = {
                                outputFile?.delete()
                                outputFile = null
                                recordState = RecordState.IDLE
                            },
                            modifier = Modifier.fillMaxWidth(),
                            enabled = !uiState.isLoading
                        ) {
                            Icon(Icons.Default.Delete, contentDescription = null)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Discard")
                        }
                    }

                    RecordState.UPLOADING -> {
                        // Upload progress matching UploadScreen.kt
                        uiState.uploadProgress?.let { progress ->
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                colors = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.primaryContainer
                                )
                            ) {
                                Column(
                                    modifier = Modifier.padding(16.dp),
                                    verticalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    Row(
                                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        when (progress.status) {
                                            ProcessingStatus.QUEUED -> CircularProgressIndicator(modifier = Modifier.size(24.dp))
                                            ProcessingStatus.PROCESSING -> CircularProgressIndicator(modifier = Modifier.size(24.dp))
                                            ProcessingStatus.COMPLETED -> Icon(Icons.Default.CheckCircle, contentDescription = null)
                                            ProcessingStatus.FAILED -> Icon(Icons.Default.Error, contentDescription = null)
                                            else -> {}
                                        }
                                        Text(
                                            text = progress.message,
                                            style = MaterialTheme.typography.bodyMedium
                                        )
                                    }

                                    if (progress.status == ProcessingStatus.PROCESSING) {
                                        LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                                    }
                                }
                            }
                        }

                        if (uiState.isLoading && uiState.uploadProgress == null) {
                            CircularProgressIndicator(modifier = Modifier.padding(16.dp))
                        }
                    }
                }
            }

            // Local recording error message
            recordErrorMessage?.let { error ->
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer
                    )
                ) {
                    Text(
                        text = error,
                        modifier = Modifier.padding(16.dp),
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }

            // ViewModel upload error message
            uiState.errorMessage?.let { error ->
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer
                    )
                ) {
                    Text(
                        text = error,
                        modifier = Modifier.padding(16.dp),
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
        }
    }
}
