package com.vishwas.app.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.vishwas.app.viewmodel.StreamingVoiceState
import com.vishwas.app.viewmodel.VishwasViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.math.abs

private const val SAMPLE_RATE = 16000
private const val CHUNK_SIZE_BYTES = 48000

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StreamingVoiceDetectionScreen(
    viewModel: VishwasViewModel,
    onNavigateBack: () -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val voiceState by viewModel.streamingVoiceState.collectAsState()
    
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
    
    var isRecording by remember { mutableStateOf(false) }
    var audioRecord by remember { mutableStateOf<AudioRecord?>(null) }
    var waveformData by remember { mutableStateOf(FloatArray(100) { 0f }) }
    var currentSessionId by remember { mutableStateOf<String?>(null) }
    
    // Cleanup on dispose
    DisposableEffect(Unit) {
        onDispose {
            isRecording = false
            audioRecord?.let {
                try {
                    it.stop()
                    it.release()
                } catch (_: Exception) {}
            }
            audioRecord = null
            currentSessionId?.let { sessionId ->
                scope.launch {
                    viewModel.stopVoiceStreaming(sessionId)
                }
            }
        }
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Live Voice Detection") },
                navigationIcon = {
                    IconButton(onClick = {
                        isRecording = false
                        audioRecord?.let {
                            try {
                                it.stop()
                                it.release()
                            } catch (_: Exception) {}
                        }
                        audioRecord = null
                        currentSessionId?.let { sessionId ->
                            scope.launch {
                                viewModel.stopVoiceStreaming(sessionId)
                            }
                        }
                        onNavigateBack()
                    }) {
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
                    text = "Microphone permission required",
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
                // Status Card
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = when (voiceState) {
                            is StreamingVoiceState.Listening -> MaterialTheme.colorScheme.primaryContainer
                            is StreamingVoiceState.Analyzing -> MaterialTheme.colorScheme.tertiaryContainer
                            is StreamingVoiceState.Complete -> MaterialTheme.colorScheme.secondaryContainer
                            is StreamingVoiceState.Error -> MaterialTheme.colorScheme.errorContainer
                            else -> MaterialTheme.colorScheme.surfaceVariant
                        }
                    )
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = when (voiceState) {
                                is StreamingVoiceState.Listening -> Icons.Default.Mic
                                is StreamingVoiceState.Analyzing -> Icons.Default.GraphicEq
                                is StreamingVoiceState.Complete -> Icons.Default.CheckCircle
                                is StreamingVoiceState.Error -> Icons.Default.Error
                                else -> Icons.Default.MicNone
                            },
                            contentDescription = null,
                            modifier = Modifier.size(32.dp)
                        )
                        Column {
                            Text(
                                text = when (voiceState) {
                                    is StreamingVoiceState.Idle -> "Ready"
                                    is StreamingVoiceState.RequestingPermission -> "Requesting Permission"
                                    is StreamingVoiceState.Listening -> "Listening..."
                                    is StreamingVoiceState.Analyzing -> "Analyzing..."
                                    is StreamingVoiceState.Complete -> "Complete"
                                    is StreamingVoiceState.Error -> "Error"
                                },
                                style = MaterialTheme.typography.titleMedium
                            )
                            when (voiceState) {
                                is StreamingVoiceState.Listening -> {
                                    val state = voiceState as StreamingVoiceState.Listening
                                    Text(
                                        text = "Chunks: ${state.chunksProcessed} • Confidence: ${state.confidence}",
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                }
                                is StreamingVoiceState.Analyzing -> {
                                    val state = voiceState as StreamingVoiceState.Analyzing
                                    Text(
                                        text = "Chunks: ${state.chunksProcessed} • Confidence: ${state.confidence}",
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                }
                                is StreamingVoiceState.Error -> {
                                    val state = voiceState as StreamingVoiceState.Error
                                    Text(
                                        text = state.message,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.error
                                    )
                                }
                                else -> {}
                            }
                        }
                    }
                }
                
                // Spoof Probability Gauge
                if (voiceState is StreamingVoiceState.Analyzing || voiceState is StreamingVoiceState.Complete) {
                    val spoofProb = when (voiceState) {
                        is StreamingVoiceState.Analyzing -> (voiceState as StreamingVoiceState.Analyzing).spoofProb
                        is StreamingVoiceState.Complete -> (voiceState as StreamingVoiceState.Complete).spoofProb
                        else -> 0.0
                    }
                    val confidence = when (voiceState) {
                        is StreamingVoiceState.Analyzing -> (voiceState as StreamingVoiceState.Analyzing).confidence
                        is StreamingVoiceState.Complete -> (voiceState as StreamingVoiceState.Complete).confidence
                        else -> ""
                    }
                    
                    Card(
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(
                            modifier = Modifier.padding(16.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Text(
                                text = "Spoof Probability",
                                style = MaterialTheme.typography.titleMedium
                            )
                            
                            Box(
                                contentAlignment = Alignment.Center,
                                modifier = Modifier.size(150.dp)
                            ) {
                                CircularProgressIndicator(
                                    progress = spoofProb.toFloat(),
                                    modifier = Modifier.fillMaxSize(),
                                    strokeWidth = 12.dp,
                                    color = when {
                                        spoofProb < 0.3 -> Color(0xFF4CAF50) // Green
                                        spoofProb < 0.6 -> Color(0xFFFFC107) // Yellow
                                        else -> Color(0xFFF44336) // Red
                                    },
                                    trackColor = MaterialTheme.colorScheme.surfaceVariant
                                )
                                Column(
                                    horizontalAlignment = Alignment.CenterHorizontally
                                ) {
                                    Text(
                                        text = "${(spoofProb * 100).toInt()}%",
                                        style = MaterialTheme.typography.displayMedium,
                                        color = MaterialTheme.colorScheme.primary
                                    )
                                    Text(
                                        text = confidence,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                        }
                    }
                }
                
                // Waveform Visualization
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(120.dp)
                ) {
                    Canvas(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(8.dp)
                    ) {
                        val width = size.width
                        val height = size.height
                        val centerY = height / 2
                        
                        if (isRecording && waveformData.any { it != 0f }) {
                            val path = Path()
                            val step = width / waveformData.size
                            
                            waveformData.forEachIndexed { index, amplitude ->
                                val x = index * step
                                val y = centerY - (amplitude * centerY * 0.8f)
                                if (index == 0) {
                                    path.moveTo(x, y)
                                } else {
                                    path.lineTo(x, y)
                                }
                            }
                            
                            drawPath(
                                path = path,
                                color = Color(0xFF2196F3), // Blue
                                style = Stroke(width = 3f, cap = StrokeCap.Round)
                            )
                        } else {
                            // Draw flat line when idle
                            drawLine(
                                color = Color.Gray,
                                start = Offset(0f, centerY),
                                end = Offset(width, centerY),
                                strokeWidth = 2f
                            )
                        }
                    }
                }
                
                Spacer(modifier = Modifier.height(8.dp))
                
                // Control Buttons
                if (!isRecording) {
                    Button(
                        onClick = {
                            scope.launch {
                                // Start session
                                val result = viewModel.startVoiceStreaming()
                                result.onSuccess { sessionId ->
                                    currentSessionId = sessionId
                                    isRecording = true
                                    
                                    // Start audio recording
                                    withContext(Dispatchers.Default) {
                                        val channelConfig = AudioFormat.CHANNEL_IN_MONO
                                        val audioFormat = AudioFormat.ENCODING_PCM_16BIT
                                        val minBufferSize = AudioRecord.getMinBufferSize(
                                            SAMPLE_RATE,
                                            channelConfig,
                                            audioFormat
                                        )
                                        val bufferSize = minBufferSize * 2
                                        
                                        val recorder = AudioRecord(
                                            MediaRecorder.AudioSource.MIC,
                                            SAMPLE_RATE,
                                            channelConfig,
                                            audioFormat,
                                            bufferSize
                                        )
                                        
                                        audioRecord = recorder
                                        recorder.startRecording()
                                        
                                        val readBuffer = ByteArray(bufferSize)
                                        var accumulated = ByteArray(0)
                                        
                                        while (isRecording && isActive) {
                                            val bytesRead = recorder.read(readBuffer, 0, readBuffer.size)
                                            if (bytesRead > 0) {
                                                // Update waveform visualization
                                                val samples = ShortArray(bytesRead / 2)
                                                for (i in samples.indices) {
                                                    samples[i] = ((readBuffer[i * 2].toInt() and 0xFF) or 
                                                                 (readBuffer[i * 2 + 1].toInt() shl 8)).toShort()
                                                }
                                                val newWaveform = FloatArray(100)
                                                val sampleStep = samples.size / 100
                                                for (i in 0 until 100) {
                                                    val sampleIndex = i * sampleStep
                                                    if (sampleIndex < samples.size) {
                                                        newWaveform[i] = samples[sampleIndex] / 32768f
                                                    }
                                                }
                                                waveformData = newWaveform
                                                
                                                // Accumulate bytes for chunking
                                                accumulated += readBuffer.copyOfRange(0, bytesRead)
                                                
                                                // Send chunk when we have enough data
                                                if (accumulated.size >= CHUNK_SIZE_BYTES) {
                                                    val chunk = accumulated.copyOfRange(0, CHUNK_SIZE_BYTES)
                                                    accumulated = accumulated.copyOfRange(CHUNK_SIZE_BYTES, accumulated.size)
                                                    
                                                    viewModel.sendAudioChunk(sessionId, chunk)
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.PlayArrow, contentDescription = null)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Start Detection")
                    }
                } else {
                    Button(
                        onClick = {
                            isRecording = false
                            audioRecord?.let {
                                try {
                                    it.stop()
                                    it.release()
                                } catch (_: Exception) {}
                            }
                            audioRecord = null
                            currentSessionId?.let { sessionId ->
                                scope.launch {
                                    viewModel.stopVoiceStreaming(sessionId)
                                }
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.error
                        )
                    ) {
                        Icon(Icons.Default.Stop, contentDescription = null)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Stop Detection")
                    }
                }
                
                // Reset button for Complete/Error states
                if (voiceState is StreamingVoiceState.Complete || voiceState is StreamingVoiceState.Error) {
                    OutlinedButton(
                        onClick = {
                            viewModel.resetVoiceStreamingState()
                            currentSessionId = null
                            waveformData = FloatArray(100) { 0f }
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.Refresh, contentDescription = null)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Start New Session")
                    }
                }
                
                // Info Card
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.secondaryContainer
                    )
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Info,
                            contentDescription = null
                        )
                        Text(
                            text = "Real-time voice spoofing detection analyzes your microphone input in ~1.5 second chunks. Results update continuously as you speak.",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }
        }
    }
}
