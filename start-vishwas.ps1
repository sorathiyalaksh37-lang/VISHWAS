# VISHWAS Integration Startup Script
# Starts both backend and frontend services

Write-Host "🛡️  Starting VISHWAS Call Fraud Detection System..." -ForegroundColor Cyan
Write-Host ""

# Check Python installation
Write-Host "[1/5] Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  ✓ Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python not found. Please install Python 3.9+ first." -ForegroundColor Red
    exit 1
}

# Check if backend .env exists
Write-Host "[2/5] Checking backend configuration..." -ForegroundColor Yellow
if (-not (Test-Path "backend\.env")) {
    Write-Host "  ! No .env file found. Creating from template..." -ForegroundColor Yellow
    Copy-Item "backend\.env.example" "backend\.env"
    Write-Host "  ✓ Created backend\.env (using mock mode by default)" -ForegroundColor Green
    Write-Host "  ℹ To enable real transcription, edit backend\.env and set ANALYSIS_MODE=real" -ForegroundColor Cyan
} else {
    Write-Host "  ✓ Found backend\.env" -ForegroundColor Green
}

# Start backend
Write-Host "[3/5] Starting backend server..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    cd backend
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
}
Write-Host "  ✓ Backend starting (Job ID: $($backendJob.Id))..." -ForegroundColor Green

# Wait for backend to be ready
Write-Host "[4/5] Waiting for backend to initialize..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 0
$backendReady = $false

while ($attempt -lt $maxAttempts -and -not $backendReady) {
    Start-Sleep -Seconds 1
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $backendReady = $true
            Write-Host "  ✓ Backend ready!" -ForegroundColor Green
        }
    } catch {
        $attempt++
        Write-Host "  ⏳ Attempt $attempt/$maxAttempts..." -ForegroundColor Gray
    }
}

if (-not $backendReady) {
    Write-Host "  ✗ Backend failed to start within 30 seconds" -ForegroundColor Red
    Write-Host "  Check logs: Receive-Job $($backendJob.Id)" -ForegroundColor Yellow
    exit 1
}

# Start frontend
Write-Host "[5/5] Starting frontend dashboard..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    cd web-dashboard
    $env:VISHWAS_API_URL = "http://localhost:8000/api/v1"
    streamlit run app.py --server.port 8501 --server.headless true
}
Write-Host "  ✓ Frontend starting (Job ID: $($frontendJob.Id))..." -ForegroundColor Green

# Wait for frontend
Start-Sleep -Seconds 3

# Summary
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🎉 VISHWAS is running!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "📊 Frontend Dashboard: http://localhost:8501" -ForegroundColor Cyan
Write-Host "🔧 Backend API:        http://localhost:8000" -ForegroundColor Cyan
Write-Host "📖 API Docs:           http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Background Jobs:" -ForegroundColor Yellow
Write-Host "  Backend:  Job ID $($backendJob.Id)" -ForegroundColor Gray
Write-Host "  Frontend: Job ID $($frontendJob.Id)" -ForegroundColor Gray
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Yellow
Write-Host "  Backend:  Receive-Job $($backendJob.Id)" -ForegroundColor Gray
Write-Host "  Frontend: Receive-Job $($frontendJob.Id)" -ForegroundColor Gray
Write-Host ""
Write-Host "To stop all services:" -ForegroundColor Yellow
Write-Host "  .\stop-vishwas.ps1" -ForegroundColor Gray
Write-Host "  OR manually: Stop-Job $($backendJob.Id), $($frontendJob.Id)" -ForegroundColor Gray
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

# Keep script running and monitor
Write-Host ""
Write-Host "Press Ctrl+C to stop monitoring (services will keep running)" -ForegroundColor Yellow
Write-Host ""

try {
    while ($true) {
        Start-Sleep -Seconds 5
        
        # Check if jobs are still running
        $backendState = (Get-Job -Id $backendJob.Id).State
        $frontendState = (Get-Job -Id $frontendJob.Id).State
        
        if ($backendState -ne "Running") {
            Write-Host "⚠️  Backend job stopped (State: $backendState)" -ForegroundColor Red
            Write-Host "View logs: Receive-Job $($backendJob.Id)" -ForegroundColor Yellow
            break
        }
        
        if ($frontendState -ne "Running") {
            Write-Host "⚠️  Frontend job stopped (State: $frontendState)" -ForegroundColor Red
            Write-Host "View logs: Receive-Job $($frontendJob.Id)" -ForegroundColor Yellow
            break
        }
    }
} catch {
    Write-Host ""
    Write-Host "Monitoring stopped. Services are still running in background." -ForegroundColor Yellow
}
