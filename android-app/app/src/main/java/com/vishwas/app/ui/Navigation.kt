package com.vishwas.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.vishwas.app.ui.screens.*
import com.vishwas.app.viewmodel.VishwasViewModel
import kotlinx.coroutines.launch

/**
 * Navigation routes
 */
object Routes {
    const val LOGIN    = "login"
    const val DASHBOARD = "dashboard"
    const val UPLOAD    = "upload"
    const val RECORD    = "record"
    const val RESULTS   = "results/{callId}"
    const val HISTORY   = "history"
    const val ABOUT     = "about"
    const val VOICE_DETECTION = "voice-detection"

    fun results(callId: String) = "results/$callId"
}

private data class NavItem(
    val route: String,
    val label: String,
    val icon: ImageVector
)

private val navItems = listOf(
    NavItem(Routes.DASHBOARD, "Dashboard",        Icons.Default.Dashboard),
    NavItem(Routes.UPLOAD,    "Upload Recording", Icons.Default.Upload),
    NavItem(Routes.RECORD,    "Record",           Icons.Default.Mic),
    NavItem(Routes.VOICE_DETECTION, "Live Voice Detection", Icons.Default.GraphicEq),
    NavItem(Routes.HISTORY,   "Analysis History", Icons.Default.History),
    NavItem(Routes.ABOUT,     "About",            Icons.Default.Info)
)

/**
 * Main navigation host with ModalNavigationDrawer shell.
 * The drawer is the Streamlit sidebar equivalent.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VishwasNavHost(
    navController: NavHostController = rememberNavController(),
    viewModel: VishwasViewModel = viewModel()
) {
    val drawerState   = rememberDrawerState(initialValue = DrawerValue.Closed)
    val scope         = rememberCoroutineScope()
    val uiState       by viewModel.uiState.collectAsState()
    val navBackStack  by navController.currentBackStackEntryAsState()
    val currentRoute  = navBackStack?.destination?.route

    // Determine start destination based on login state
    val startDestination = if (uiState.isLoggedIn) Routes.DASHBOARD else Routes.LOGIN

    fun openDrawer()  = scope.launch { drawerState.open() }
    fun closeDrawer() = scope.launch { drawerState.close() }

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ModalDrawerSheet {
                // ── Drawer header ──────────────────────────────────────────────
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(24.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.Security,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(28.dp)
                        )
                        Text(
                            "🛡️ VISHWAS",
                            style = MaterialTheme.typography.headlineSmall,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                    Text(
                        "AI-Powered Call Fraud Detection",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                // ── Backend health ─────────────────────────────────────────────
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = if (uiState.isBackendHealthy)
                            MaterialTheme.colorScheme.primaryContainer
                        else
                            MaterialTheme.colorScheme.errorContainer
                    )
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = if (uiState.isBackendHealthy)
                                Icons.Default.CheckCircle else Icons.Default.Error,
                            contentDescription = null,
                            modifier = Modifier.size(16.dp)
                        )
                        Column {
                            Text(
                                text = if (uiState.isBackendHealthy) "Backend: OK" else "Backend Unavailable",
                                style = MaterialTheme.typography.labelMedium
                            )
                            if (uiState.isBackendHealthy && uiState.backendVersion.isNotBlank()) {
                                Text(
                                    text = "v${uiState.backendVersion}",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))
                HorizontalDivider(modifier = Modifier.padding(horizontal = 16.dp))
                Spacer(modifier = Modifier.height(12.dp))

                // ── Phase 1 persistent banner (ONE place — not in ResultsScreen) ──
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF3CD))
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text("⚠️", style = MaterialTheme.typography.bodyMedium)
                        Text(
                            text = "Phase 1: Mock Analysis — results are for demonstration only.",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFF7A5C00)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))
                HorizontalDivider(modifier = Modifier.padding(horizontal = 16.dp))
                Spacer(modifier = Modifier.height(8.dp))

                // ── Navigation items ───────────────────────────────────────────
                navItems.forEach { item ->
                    NavigationDrawerItem(
                        icon  = { Icon(item.icon, contentDescription = null) },
                        label = { Text(item.label) },
                        selected = currentRoute == item.route,
                        onClick = {
                            closeDrawer()
                            if (currentRoute != item.route) {
                                navController.navigate(item.route) {
                                    popUpTo(Routes.DASHBOARD) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            }
                        },
                        modifier = Modifier.padding(NavigationDrawerItemDefaults.ItemPadding)
                    )
                }

                Spacer(modifier = Modifier.weight(1f))
                HorizontalDivider(modifier = Modifier.padding(horizontal = 16.dp))

                // ── Logged-in user + Logout ────────────────────────────────────
                if (uiState.isLoggedIn) {
                    NavigationDrawerItem(
                        icon  = { Icon(Icons.Default.Logout, contentDescription = null) },
                        label = { Text("Sign Out (${uiState.loggedInEmail})") },
                        selected = false,
                        onClick = {
                            closeDrawer()
                            viewModel.logout()
                            navController.navigate(Routes.LOGIN) {
                                popUpTo(0) { inclusive = true }
                            }
                        },
                        modifier = Modifier.padding(NavigationDrawerItemDefaults.ItemPadding)
                    )
                }
                Spacer(modifier = Modifier.height(8.dp))
            }   // end ModalDrawerSheet
        }       // end drawerContent
    ) {
        NavHost(
            navController    = navController,
            startDestination = startDestination
        ) {
            // ── Auth ──────────────────────────────────────────────────────
            composable(Routes.LOGIN) {
                LoginScreen(
                    viewModel    = viewModel,
                    onLoginSuccess = {
                        navController.navigate(Routes.DASHBOARD) {
                            popUpTo(Routes.LOGIN) { inclusive = true }
                        }
                    }
                )
            }
            composable(Routes.DASHBOARD) {
                DashboardScreen(
                    viewModel          = viewModel,
                    onNavigateToResults = { callId -> navController.navigate(Routes.results(callId)) },
                    onOpenDrawer       = { openDrawer() }
                )
            }

            composable(Routes.UPLOAD) {
                UploadScreen(
                    viewModel          = viewModel,
                    onNavigateBack     = { navController.popBackStack() },
                    onNavigateToResults = { callId ->
                        navController.navigate(Routes.results(callId)) {
                            popUpTo(Routes.UPLOAD) { inclusive = true }
                        }
                    }
                )
            }

            composable(Routes.RECORD) {
                RecordScreen(
                    viewModel          = viewModel,
                    onNavigateBack     = { navController.popBackStack() },
                    onNavigateToResults = { callId ->
                        navController.navigate(Routes.results(callId)) {
                            popUpTo(Routes.RECORD) { inclusive = true }
                        }
                    }
                )
            }
            
            composable(Routes.VOICE_DETECTION) {
                StreamingVoiceDetectionScreen(
                    viewModel      = viewModel,
                    onNavigateBack = { navController.popBackStack() }
                )
            }

            composable(Routes.HISTORY) {
                HistoryScreen(
                    viewModel          = viewModel,
                    onNavigateBack     = { navController.popBackStack() },
                    onNavigateToResults = { callId -> navController.navigate(Routes.results(callId)) }
                )
            }

            composable(Routes.ABOUT) {
                AboutScreen(onOpenDrawer = { openDrawer() })
            }

            composable(Routes.RESULTS) { backStackEntry ->
                val callId = backStackEntry.arguments?.getString("callId") ?: ""
                ResultsScreen(
                    viewModel      = viewModel,
                    callId         = callId,
                    onNavigateBack = { navController.popBackStack() }
                )
            }
        }
    }
}
