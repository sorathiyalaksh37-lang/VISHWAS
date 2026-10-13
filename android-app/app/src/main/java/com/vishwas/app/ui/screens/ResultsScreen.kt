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

/** Risk-level color mapping — must match Streamlit dashboard exactly. */
private fun riskColor(level: String): Color = when (level.lowercase()) {
    "low"      -> Color(0xFF2E7D32) // green
    "medium"   -> Color(0xFFE65100) // orange
    "high"     -> Color(0xFFB71C1C) // red
    "critical" -> Color(0xFF7B0000) // dark red
    else       -> Color.Gray
}

private fun riskContainerColor(level: String): Color = when (level.lowercase()) {
    "low"      -> Color(0xFFE8F5E9)
    "medium"   -> Color(0xFFFFF3E0)
    "high"     -> Color(0xFFFFEBEE)
    "critical" -> Color(0xFFFCE4EC)
    else       -> Color(0xFFF5F5F5)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ResultsScreen(
    viewModel: VishwasViewModel,
    callId: String,
    onNavigateBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    var metadataExpanded by remember { mutableStateOf(false) }

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
            ) { CircularProgressIndicator() }
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
                            Icons.Default.Error,
                            contentDescription = null,
                            modifier = Modifier.size(64.dp)
                        )
                        Text("Report not found")
                    }
                }
            } else {
                val level          = report.level
                val riskLower      = level.lowercase()
                val primaryColor   = riskColor(level)
                val containerColor = riskContainerColor(level)

                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(paddingValues),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {

                    // 1. Safety warning — HIGH / CRITICAL only (patch-preserved)
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
                                        "⚠ Do NOT send money or share OTPs",
                                        style = MaterialTheme.typography.titleMedium,
                                        color = Color(0xFF8A6D00)
                                    )
                                    Text("• Call back on the number saved in your contacts",
                                        style = MaterialTheme.typography.bodyMedium)
                                    Text("• Ask for the family safe word before acting",
                                        style = MaterialTheme.typography.bodyMedium)
                                    Text("• Never share a PIN, OTP, or bank password",
                                        style = MaterialTheme.typography.bodyMedium)
                                }
                            }
                        }
                    }

                    // 2. Top 3-metric row — RISK LEVEL | LANGUAGE | ANALYSIS MODE
                    item {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            // Risk Level (color-coded)
                            Card(
                                modifier = Modifier.weight(1f),
                                colors   = CardDefaults.cardColors(containerColor = containerColor)
                            ) {
                                Column(
                                    modifier = Modifier
                                        .padding(12.dp)
                                        .fillMaxWidth(),
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                    verticalArrangement = Arrangement.spacedBy(2.dp)
                                ) {
                                    Text(
                                        text  = level.uppercase(),
                                        style = MaterialTheme.typography.titleMedium,
                                        color = primaryColor
                                    )
                                    Text(
                                        text  = "${report.score}/100",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = primaryColor
                                    )
                                    Text(
                                        "RISK LEVEL",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                            // Language
                            Card(
                                modifier = Modifier.weight(1f),
                                colors   = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.surfaceVariant
                                )
                            ) {
                                Column(
                                    modifier = Modifier
                                        .padding(12.dp)
                                        .fillMaxWidth(),
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                    verticalArrangement = Arrangement.spacedBy(2.dp)
                                ) {
                                    Text(
                                        text  = report.language?.uppercase() ?: "N/A",
                                        style = MaterialTheme.typography.titleMedium
                                    )
                                    Text(
                                        "LANGUAGE",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                            // Analysis Mode
                            Card(
                                modifier = Modifier.weight(1f),
                                colors   = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.surfaceVariant
                                )
                            ) {
                                Column(
                                    modifier = Modifier
                                        .padding(12.dp)
                                        .fillMaxWidth(),
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                    verticalArrangement = Arrangement.spacedBy(2.dp)
                                ) {
                                    Text(
                                        text  = report.analysisMode.uppercase(),
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                    Text(
                                        "MODE",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                        }
                    }

                    // 3. v3 evidence cards — kill-chain, scores, verification, voice, rules, counterfactuals
                    v3EvidenceItems(report)

                    // 4. Warnings (st.warning equivalent)
                    if (report.warnings.isNotEmpty()) {
                        item {
                            Card(
                                colors = CardDefaults.cardColors(
                                    containerColor = Color(0xFFFFF3CD)
                                )
                            ) {
                                Column(
                                    modifier = Modifier.padding(16.dp),
                                    verticalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    Text("Warnings:", style = MaterialTheme.typography.titleMedium)
                                    report.warnings.forEach { w ->
                                        Text("• $w", style = MaterialTheme.typography.bodySmall)
                                    }
                                }
                            }
                        }
                    }

                    // 5. 🎯 Risk Factors
                    if (report.reasons.isNotEmpty()) {
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
                                        Text("🎯 Risk Factors",
                                            style = MaterialTheme.typography.titleMedium)
                                    }
                                    report.reasons.forEach { r ->
                                        Text("• $r", style = MaterialTheme.typography.bodyMedium)
                                    }
                                }
                            }
                        }
                    }

                    // 6. ✅ Recommended Actions
                    if (report.recommendedActions.isNotEmpty()) {
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
                                        Text("✅ Recommended Actions",
                                            style = MaterialTheme.typography.titleMedium)
                                    }
                                    report.recommendedActions.forEach { a ->
                                        Text("• $a", style = MaterialTheme.typography.bodyMedium)
                                    }
                                }
                            }
                        }
                    }

                    // 7. 🔍 Detection Findings (one card per agent_finding)
                    if (report.agentFindings.isNotEmpty()) {
                        item {
                            Text("🔍 Detection Findings",
                                style = MaterialTheme.typography.titleLarge)
                        }
                        items(report.agentFindings) { finding ->
                            Card {
                                Column(
                                    modifier = Modifier.padding(16.dp),
                                    verticalArrangement = Arrangement.spacedBy(4.dp)
                                ) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween
                                    ) {
                                        Text(
                                            text  = finding.signal,
                                            style = MaterialTheme.typography.titleMedium,
                                            modifier = Modifier.weight(1f)
                                        )
                                        Text(
                                            text  = finding.severity.uppercase(),
                                            style = MaterialTheme.typography.bodySmall,
                                            color = when (finding.severity.lowercase()) {
                                                "critical", "high" ->
                                                    MaterialTheme.colorScheme.error
                                                else ->
                                                    MaterialTheme.colorScheme.onSurface
                                            }
                                        )
                                    }
                                    Text(
                                        text  = "Agent: ${finding.agent}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                    Text(
                                        text  = finding.evidenceText,
                                        style = MaterialTheme.typography.bodyMedium
                                    )
                                    if (finding.startTime != null) {
                                        Text(
                                            text  = "${finding.startTime}s – ${finding.endTime}s",
                                            style = MaterialTheme.typography.bodySmall
                                        )
                                    }
                                    // source as caption
                                    Text(
                                        text  = finding.source,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                        }
                    }

                    // 8. 📝 Transcript
                    item {
                        Text("📝 Transcript", style = MaterialTheme.typography.titleLarge)
                    }
                    val transcript = report.transcript
                    if (transcript != null && transcript.segments.isNotEmpty()) {
                        items(transcript.segments) { segment ->
                            Card {
                                Column(
                                    modifier = Modifier.padding(12.dp),
                                    verticalArrangement = Arrangement.spacedBy(4.dp)
                                ) {
                                    Text(
                                        text  = "[${segment.start}s - ${segment.end}s]",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                    Text(
                                        text  = segment.text,
                                        style = MaterialTheme.typography.bodyMedium
                                    )
                                }
                            }
                        }
                    } else {
                        item {
                            Card(
                                colors = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.surfaceVariant
                                )
                            ) {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(16.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text("No transcript available",
                                        style = MaterialTheme.typography.bodyMedium)
                                }
                            }
                        }
                    }

                    // 9. 📊 Metadata — collapsible
                    item {
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text("📊 Metadata",
                                        style = MaterialTheme.typography.titleMedium)
                                    IconButton(onClick = {
                                        metadataExpanded = !metadataExpanded
                                    }) {
                                        Icon(
                                            imageVector = if (metadataExpanded)
                                                Icons.Default.ExpandLess
                                            else
                                                Icons.Default.ExpandMore,
                                            contentDescription = null
                                        )
                                    }
                                }
                                if (metadataExpanded) {
                                    HorizontalDivider(
                                        modifier = Modifier.padding(vertical = 8.dp)
                                    )
                                    Column(
                                        verticalArrangement = Arrangement.spacedBy(4.dp)
                                    ) {
                                        MetaRow("Call ID",   report.callId)
                                        MetaRow("Status",    report.status)
                                        MetaRow("Created",   report.createdAt
                                            .take(16).replace("T", " "))
                                        report.completedAt?.let {
                                            MetaRow("Completed", it.take(16).replace("T", " "))
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun MetaRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(value, style = MaterialTheme.typography.bodySmall)
    }
}
