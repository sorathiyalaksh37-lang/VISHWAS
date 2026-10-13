package com.vishwas.app.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.vishwas.app.models.ProcessingStatus
import com.vishwas.app.viewmodel.VishwasViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UploadScreen(
    viewModel: VishwasViewModel,
    onNavigateBack: () -> Unit,
    onNavigateToResults: (String) -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    var selectedUri by remember { mutableStateOf<Uri?>(null) }
    var selectedFilename by remember { mutableStateOf<String?>(null) }
    
    val launcher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        selectedUri = uri
        uri?.lastPathSegment?.let { path ->
            selectedFilename = path.substringAfterLast('/')
        }
    }
    
    // Check if analysis completed
    LaunchedEffect(uiState.uploadProgress) {
        val progress = uiState.uploadProgress
        if (progress != null && progress.status == ProcessingStatus.COMPLETED) {
            val id = progress.callId
            viewModel.clearUploadProgress()
            onNavigateToResults(id)
        }
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Upload Recording") },
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
            Text(
                text = "Select an audio recording to analyze for potential fraud patterns.",
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
                    Text("Supported Formats:", style = MaterialTheme.typography.titleSmall)
                    Text("• WAV (.wav)", style = MaterialTheme.typography.bodySmall)
                    Text("• MP3 (.mp3)", style = MaterialTheme.typography.bodySmall)
                    Text("• M4A (.m4a)", style = MaterialTheme.typography.bodySmall)
                    Text("Maximum size: 50 MB", style = MaterialTheme.typography.bodySmall)
                }
            }
            
            Spacer(modifier = Modifier.height(16.dp))
            
            Button(
                onClick = { launcher.launch("audio/*") },
                modifier = Modifier.fillMaxWidth(),
                enabled = !uiState.isLoading
            ) {
                Icon(Icons.Default.AttachFile, contentDescription = null)
                Spacer(modifier = Modifier.width(8.dp))
                Text("Select Audio File")
            }
            
            selectedFilename?.let { filename ->
                Card(
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Text("Selected File:", style = MaterialTheme.typography.titleSmall)
                        Text(filename, style = MaterialTheme.typography.bodyMedium)
                    }
                }
                
                Button(
                    onClick = {
                        selectedUri?.let { uri ->
                            viewModel.uploadRecording(uri, filename)
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !uiState.isLoading
                ) {
                    Icon(Icons.Default.Upload, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Upload and Analyze")
                }
            }
            
            // Upload progress
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
            
            // Error message
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
