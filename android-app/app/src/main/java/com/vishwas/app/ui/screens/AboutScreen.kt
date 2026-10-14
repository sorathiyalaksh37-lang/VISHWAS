package com.vishwas.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AboutScreen(onOpenDrawer: () -> Unit) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("ℹ️ About VISHWAS") },
                navigationIcon = {
                    IconButton(onClick = onOpenDrawer) {
                        Icon(Icons.Default.Menu, contentDescription = "Open navigation")
                    }
                }
            )
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // What is VISHWAS
            item {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text(
                            "AI-Powered Call Fraud Detection Platform",
                            style = MaterialTheme.typography.headlineSmall
                        )
                        Text(
                            "VISHWAS is an intelligent system designed to analyze authorized call " +
                            "recordings and help identify potential fraud, suspicious requests, " +
                            "impersonation attempts, threats, urgency tactics, and attempts to " +
                            "obtain sensitive information.",
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }
            }

            // Phase 1 status
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.tertiaryContainer
                    )
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text("Current Status: Phase 1", style = MaterialTheme.typography.titleMedium)
                        Text(
                            "Phase 1 establishes the complete project infrastructure with a working " +
                            "end-to-end workflow. Voice-clone detection is experimental and probabilistic. " +
                            "Record screen saves .m4a (AAC) to app cache before upload.",
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }
            }

            // Features
            item {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Text("Features", style = MaterialTheme.typography.titleMedium)
                        Spacer(modifier = Modifier.height(4.dp))
                        listOf(
                            "Audio file upload (WAV, MP3, M4A)",
                            "Live call recording (.m4a / AAC)",
                            "Automated risk analysis workflow",
                            "Kill-chain stage detection",
                            "Category score breakdown (100 pt scale)",
                            "Voice-clone detection (experimental)",
                            "Speaker verification (experimental)",
                            "Transcript generation",
                            "Counterfactual explanations",
                            "Analysis history tracking"
                        ).forEach { feature ->
                            Text("✅ $feature", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }

            // Pipeline
            item {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text("Detection Pipeline", style = MaterialTheme.typography.titleMedium)
                        Text(
                            "Recording Upload → Perception → Evidence Extraction → " +
                            "Content & Knowledge → Adversarial Reasoning → " +
                            "Deterministic Decision → Action → Clients",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }

            // Security & Privacy
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer
                    )
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text("⚠️ Security & Privacy", style = MaterialTheme.typography.titleMedium)
                        Text(
                            "Call recordings may contain sensitive personal information. Files are " +
                            "validated and stored securely. Server-generated filenames prevent path " +
                            "traversal. No execution of uploaded content.",
                            style = MaterialTheme.typography.bodySmall
                        )
                        Text(
                            "Phase 1 Limitations: No authentication, no encryption at rest, HTTP only " +
                            "(no HTTPS), single user (no user accounts). Not production-ready.",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }

            // Copyright
            item {
                Divider()
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    "Copyright © 2026 VISHWAS Team. All rights reserved.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
