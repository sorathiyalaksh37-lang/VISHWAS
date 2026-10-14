package com.vishwas.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Lightbulb
import androidx.compose.material.icons.filled.Security
import androidx.compose.material3.Card
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.vishwas.app.models.AnalysisReportResponse
import com.vishwas.app.models.CategoryScores
import com.vishwas.app.models.VoiceEvidence

/**
 * v3 contract cards (docs/INTEGRATION.md §2).
 * Every field is nullable/optional per the degradation rule: a card is simply
 * skipped when its data is missing, and nothing here can throw.
 */
fun LazyListScope.v3EvidenceItems(report: AnalysisReportResponse) {

    // Kill-chain stage
    report.killchainStage?.takeIf { it.isNotBlank() }?.let { stage ->
        item {
            Card(modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.Security, contentDescription = null)
                    Column {
                        Text("Scam stage", style = MaterialTheme.typography.labelMedium)
                        Text(stage, style = MaterialTheme.typography.titleMedium)
                    }
                }
            }
        }
    }

    // Category score breakdown
    report.categoryScores?.let { scores ->
        item { CategoryScoresCard(scores) }
    }

    // Verification action
    report.verification?.let { v ->
        if (v.action != null || v.target != null) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = androidx.compose.material3.CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.tertiaryContainer
                    )
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        Row(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Default.Call, contentDescription = null)
                            Text("Verify before acting", style = MaterialTheme.typography.titleMedium)
                        }
                        v.action?.let {
                            Text(
                                text = it.replace('_', ' ').replaceFirstChar { c -> c.uppercase() },
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }
                        v.target?.let {
                            Text(it, style = MaterialTheme.typography.bodyMedium)
                        }
                        if (v.safeWordPrompt == true) {
                            Text(
                                "Ask for the family safe word.",
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }
                    }
                }
            }
        }
    }

    // Voice evidence
    report.voice?.let { voice ->
        item { VoiceCard(voice) }
    }

    // Fired rules
    if (report.firedRules.isNotEmpty()) {
        item {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Text("Rules triggered", style = MaterialTheme.typography.titleMedium)
                    report.firedRules.forEach { rule ->
                        Text("• $rule", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }

    // Counterfactuals
    if (report.counterfactuals.isNotEmpty()) {
        item {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Default.Lightbulb, contentDescription = null)
                        Text("What would lower the score", style = MaterialTheme.typography.titleMedium)
                    }
                    report.counterfactuals.forEach { cf ->
                        val change = cf.change ?: return@forEach
                        val suffix = cf.newScore?.let { " → $it/100" } ?: ""
                        Text("• $change$suffix", style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }
    }
}

@Composable
private fun CategoryScoresCard(scores: CategoryScores) {
    // Caps per contract: identity 25, request 30, behavior 20, channel 15, voice 10
    val rows = listOf(
        Triple("Identity", scores.identity, 25),
        Triple("Request", scores.request, 30),
        Triple("Behavior", scores.behavior, 20),
        Triple("Channel", scores.channel, 15),
        Triple("Voice", scores.voice, 10)
    )
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text("Score breakdown", style = MaterialTheme.typography.titleMedium)
            rows.forEach { (label, value, cap) ->
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(label, style = MaterialTheme.typography.bodyMedium)
                        Text(
                            text = if (value == null) "n/a" else "$value / $cap",
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                    LinearProgressIndicator(
                        progress = ((value ?: 0).toFloat() / cap).coerceIn(0f, 1f),
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            }
        }
    }
}

@Composable
private fun VoiceCard(voice: VoiceEvidence) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(Icons.Default.GraphicEq, contentDescription = null)
                Text("Voice analysis (experimental)", style = MaterialTheme.typography.titleMedium)
            }
            when (voice.status) {
                "ok" -> {
                    voice.spoofProb?.let {
                        Text(
                            "Synthetic-voice likelihood: ${(it * 100).toInt()}%",
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                    voice.speakerMatch?.let { m ->
                        val who = m.claimedContact ?: "claimed contact"
                        when {
                            m.enrolled == false ->
                                Text("No saved voiceprint for $who.", style = MaterialTheme.typography.bodySmall)
                            m.similarity != null ->
                                Text(
                                    "Match with $who: ${(m.similarity * 100).toInt()}%",
                                    style = MaterialTheme.typography.bodySmall
                                )
                        }
                    }
                }
                "inconclusive" -> Text(
                    "Inconclusive — not enough clear speech to decide.",
                    style = MaterialTheme.typography.bodyMedium
                )
                else -> Text(
                    "Voice check unavailable for this call. Text-based analysis still applies.",
                    style = MaterialTheme.typography.bodyMedium
                )
            }
            voice.quality?.let { q ->
                val parts = listOfNotNull(
                    q.durationS?.let { "%.1fs audio".format(it) },
                    q.snrDb?.let { "SNR %.1f dB".format(it) }
                )
                if (parts.isNotEmpty()) {
                    Text(
                        parts.joinToString(" · "),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}
 
