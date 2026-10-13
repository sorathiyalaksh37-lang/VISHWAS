package com.vishwas.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.vishwas.app.viewmodel.VishwasViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ResultsScreen(
    viewModel: VishwasViewModel,
    callId: String,
    onNavigateBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    
    LaunchedEffect(callId) {
        viewModel.loadReport(callId)
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Analysis Report") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { paddingValues ->
        if (uiState.isLoading) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator()
            }
        } else {
            val report = uiState.selectedCall
            if (report == null) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(paddingValues),
                    contentAlignment = Alignment.Center
                ) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Error,
                            contentDescription = null,
                            modifier = Modifier.size(64.dp)
                        )
                        Text("Report not found")
                    }
                }
            } else {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(paddingValues),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    // Mock indicator
                    if (report.isMock) {
                        item {
                            Card(
                                colors = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.secondaryContainer
                                )
                            ) {
                                Row(
                                    modifier = Modifier.padding(16.dp),
                                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    Icon(Icons.Default.Info, contentDescription = null)
                                    Text(
                                        text = "Mock Analysis Mode\n\nThis is demonstration data, not real fraud detection.",
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                }
                            }
                        }
                    }

                    // Safety warning card for HIGH / CRITICAL results
                    val riskLower = report.level.lowercase()
                    if (riskLower == "high" || riskLower == "critical") {
                        item {
                            Card(
                                colors = CardDefaults.cardColors(
                                    containerColor = Color(0xFFFFF3CD)
                                )
                            ) {
                                Column(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(16.dp),
                                    verticalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    Text(
                                        text = "⚠ Do NOT send money or share OTPs",
                                        style = MaterialTheme.typography.titleMedium,
                                        color = Color(0xFF8A6D00)
                                    )
                                    Text(
                                        text = "• Call back on the number saved in your contacts",
                                        style = MaterialTheme.typography.bodyMedium
                                    )
                                    Text(
                                        text = "• Ask for the family safe word before acting",
                                        style = MaterialTheme.typography.bodyMedium
                                    )
                                    Text(
                                        text = "• Never share a PIN, OTP, or bank password",
                                        style = MaterialTheme.typography.bodyMedium
                                    )
                                }
                            }
                        }
                    }

                    // Risk level
                    item {
                        Card(
                            colors = CardDefaults.cardColors(
                                containerColor = when (report.level.lowercase()) {
                                    "high", "critical" -> MaterialTheme.colorScheme.errorContainer
                                    "medium" -> MaterialTheme.colorScheme.tertiaryContainer
                                    else -> MaterialTheme.colorScheme.primaryContainer
                                }
                            )
                        ) {
                            Column(
                                modifier = Modifier.padding(16.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Text(
                                    text = "Risk Level: ${report.level} (score: ${report.score}/100)",
                                    style = MaterialTheme.typography.titleLarge
                                )
                                Text(
                                    text = "Language: ${report.language?.uppercase() ?: "Unknown"}",
                                    style = MaterialTheme.typography.bodyMedium
                                )
                            }
                        }
                    }
                    
                    // Warnings
                    if (report.warnings.isNotEmpty()) {
                        item {
                            Card {
                                Column(
                                    modifier = Modifier.padding(16.dp),
                                    verticalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    Text("Warnings:", style = MaterialTheme.typography.titleMedium)
                                    report.warnings.forEach { warning ->
                                        Text("• $warning", style = MaterialTheme.typography.bodySmall)
                                    }
                                }
                            }
                        }
                    }
                    
                    // Risk factors
                    item {
                        Card {
                            Column(
                                modifier = Modifier.padding(16.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Row(
                                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(Icons.Default.Warning, contentDescription = null)
                                    Text("Risk Factors", style = MaterialTheme.typography.titleMedium)
                                }
                                report.reasons.forEach { reason ->
                                    Text("• $reason", style = MaterialTheme.typography.bodyMedium)
                                }
                            }
                        }
                    }
                    
                    // Recommended actions
                    item {
                        Card(
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
                                    Icon(Icons.Default.CheckCircle, contentDescription = null)
                                    Text("Recommended Actions", style = MaterialTheme.typography.titleMedium)
                                }
                                report.recommendedActions.forEach { action ->
                                    Text("• $action", style = MaterialTheme.typography.bodyMedium)
                                }
                            }
                        }
                    }
                    
                    // Agent findings
                    if (report.agentFindings.isNotEmpty()) {
                        item {
                            Text(
                                "Detection Findings",
                                style = MaterialTheme.typography.titleLarge
                            )
                        }
                        items(report.agentFindings) { finding ->
                            Card {
                                Column(
                                    modifier = Modifier.padding(16.dp),
                                    verticalArrangement = Arrangement.spacedBy(4.dp)
                                ) {
                                    Text(
                                        text = finding.signal,
                                        style = MaterialTheme.typography.titleMedium
                                    )
                                    Text(
                                        text = "Severity: ${finding.severity.uppercase()}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = when (finding.severity.lowercase()) {
                                            "critical", "high" -> MaterialTheme.colorScheme.error
                                            else -> MaterialTheme.colorScheme.onSurface
                                        }
                                    )
                                    Text(
                                        text = "Evidence: ${finding.evidenceText}",
                                        style = MaterialTheme.typography.bodyMedium
                                    )
                                    if (finding.startTime != null) {
                                        Text(
                                            text = "Time: ${finding.startTime}s - ${finding.endTime}s",
                                            style = MaterialTheme.typography.bodySmall
                                        )
                                    }
                                    Text(
                                        text = "Source: ${finding.source}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                        }
                    }
                    
                    // Transcript
                    val transcript = report.transcript
                    if (transcript != null && transcript.segments.isNotEmpty()) {
                        item {
                            Text(
                                "Transcript",
                                style = MaterialTheme.typography.titleLarge
                            )
                        }
                        items(transcript.segments) { segment ->
                            Card {
                                Column(
                                    modifier = Modifier.padding(12.dp),
                                    verticalArrangement = Arrangement.spacedBy(4.dp)
                                ) {
                                    Text(
                                        text = "[${segment.start}s - ${segment.end}s]",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                    Text(
                                        text = segment.text,
                                        style = MaterialTheme.typography.bodyMedium
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
