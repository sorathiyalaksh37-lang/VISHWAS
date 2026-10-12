package com.vishwas.app.ui

import androidx.compose.runtime.Composable
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.vishwas.app.ui.screens.*
import com.vishwas.app.viewmodel.VishwasViewModel

/**
 * Navigation routes
 */
object Routes {
    const val HOME = "home"
    const val UPLOAD = "upload"
    const val RESULTS = "results/{callId}"
    const val HISTORY = "history"
    
    fun results(callId: String) = "results/$callId"
}

/**
 * Main navigation host
 */
@Composable
fun VishwasNavHost(
    navController: NavHostController = rememberNavController(),
    viewModel: VishwasViewModel = viewModel()
) {
    NavHost(
        navController = navController,
        startDestination = Routes.HOME
    ) {
        composable(Routes.HOME) {
            HomeScreen(
                viewModel = viewModel,
                onNavigateToUpload = { navController.navigate(Routes.UPLOAD) },
                onNavigateToHistory = { navController.navigate(Routes.HISTORY) },
                onNavigateToResults = { callId ->
                    navController.navigate(Routes.results(callId))
                }
            )
        }
        
        composable(Routes.UPLOAD) {
            UploadScreen(
                viewModel = viewModel,
                onNavigateBack = { navController.popBackStack() },
                onNavigateToResults = { callId ->
                    navController.navigate(Routes.results(callId))
                }
            )
        }
        
        composable(Routes.HISTORY) {
            HistoryScreen(
                viewModel = viewModel,
                onNavigateBack = { navController.popBackStack() },
                onNavigateToResults = { callId ->
                    navController.navigate(Routes.results(callId))
                }
            )
        }
        
        composable(Routes.RESULTS) { backStackEntry ->
            val callId = backStackEntry.arguments?.getString("callId") ?: ""
            ResultsScreen(
                viewModel = viewModel,
                callId = callId,
                onNavigateBack = { navController.popBackStack() }
            )
        }
    }
}
