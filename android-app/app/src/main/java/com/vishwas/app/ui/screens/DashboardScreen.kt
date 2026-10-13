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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.vishwas.app.viewmodel.VishwasViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    viewModel: VishwasViewModel,
    onNavigateToResults: (String) -> Unit,
    onOpenDrawer: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.loadHistory()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("📊 Dashboard") },
                navigationIcon = {
                    IconButton(onClick = onOpenDrawer) {
                        Icon(Icons.Default.Menu, contentDescription = "Open navigation")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.loadHistory() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    titleContentColor = MaterialTheme.colorScheme.onPrimaryContainer
                )
            )
        }
    ) { paddingValues ->
        if (uiState.isLoading && uiState.calls.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues),
                contentAlignment = Alignment.Center
            ) { CircularProgressIndicator() }
        } else {
            val calls = uiState.calls
            val totalCompleted = calls.count { it.status == "completed" }
            val totalInProgress = calls.count { it.status == "processing" || it.status == "queued" }
            val totalFailed = calls.count { it.status == "failed" }

            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // Four stat cards
                item {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            StatCard(
                                modifier = Modifier.weight(1f),
                                label = "Total",
                                value = "${calls.size}",
                                containerColor = MaterialTheme.colorScheme.surfaceVariant
                            )
                            StatCard(
                                modifier = Modifier.weight(1f),
                                label = "Completed",
                                value = "$totalCompleted",
                                containerColor = MaterialTheme.colorScheme.primaryContainer
                            )
                        }
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            StatCard(
                                modifier = Modifier.weight(1f),
                                label = "In Progress",
                                value = "$totalInProgress",
                                containerColor = MaterialTheme.colorScheme.tertiaryContainer
                            )
                            StatCard(
                                modifier = Modifier.weight(1f),
                                label = "Failed",
                                value = "$totalFailed",
                                containerColor = MaterialTheme.colorScheme.errorContainer
                            )
                        }
                    }
                }

                // Recent Analyses header
                item {
                    HorizontalDivider()
                    Spacer(modifier = Modifier.height(4.dp))
                    Text("Recent Analyses", style = MaterialTheme.typography.titleMedium)
                }

                if (calls.isEmpty()) {
                    item {
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(32.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    "No analyses yet. Upload a recording to get started!",
                                    style = MaterialTheme.typography.bodyMedium
                                )
                            }
                        }
                    }
                } else {
                    items(calls.take(5)) { call ->
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Row(
                                modifier = Modifier
                                    .padding(12.dp)
                                    .fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = call.originalFilename,
                                        style = MaterialTheme.typography.bodyMedium,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                    Text(
                                        text = "ID: ${call.callId.take(8)}…",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                    Text(
                                        text = call.createdAt.take(16).replace("T", " "),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                Spacer(modifier = Modifier.width(8.dp))
                                Column(horizontalAlignment = Alignment.End) {
                                    StatusChip(call.status)
                                    if (call.status == "completed") {
                                        Spacer(modifier = Modifier.height(4.dp))
                                        TextButton(onClick = { onNavigateToResults(call.callId) }) {
                                            Text("View")
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Error message
                uiState.errorMessage?.let { err ->
                    item {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(
                                containerColor = MaterialTheme.colorScheme.errorContainer
                            )
                        ) {
                            Text(
                                text = err,
                                modifier = Modifier.padding(16.dp),
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StatCard(
    label: String,
    value: String,
    containerColor: Color,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = containerColor)
    ) {
        Column(
            modifier = Modifier
                .padding(16.dp)
                .fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Text(value, style = MaterialTheme.typography.headlineMedium)
            Text(label, style = MaterialTheme.typography.labelMedium)
        }
    }
}

/**
 * Shared status chip used by DashboardScreen and HistoryScreen (same package — no import needed).
 */
@Composable
internal fun StatusChip(status: String) {
    val (chipColor, label) = when (status) {
        "completed"  -> MaterialTheme.colorScheme.primary  to "✓ Completed"
        "processing" -> MaterialTheme.colorScheme.tertiary to "⟳ Processing"
        "queued"     -> MaterialTheme.colorScheme.secondary to "⏳ Queued"
        "failed"     -> MaterialTheme.colorScheme.error    to "✗ Failed"
        else         -> MaterialTheme.colorScheme.onSurfaceVariant to status
    }
    Surface(
        shape = MaterialTheme.shapes.small,
        color = chipColor.copy(alpha = 0.15f)
    ) {
        Text(
            text = label,
            color = chipColor,
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
        )
    }
}
