# VISHWAS Full Stack Startup Script
# Starts backend API + React frontend dashboard

Write-Host "🛡️  Starting VISHWAS Full Stack..." -ForegroundColor Cyan
Write-Host ""

# Check Node.js installation
Write-Host "[1/6] Checking Node.js installation..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    Write-Host "  ✓ Found: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Node.js not found. Please install Node.js 18+ first." -ForegroundColor Red
    exit 1
}

# Check Python installation
Write-Host "[2/6] Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  ✓ Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python not found. Please install Python 3.9+ first." -ForegroundColor Red
    exit 1
}

# Check if backend .env exists
Write-Host "[3/6] Checking backend configuration..." -ForegroundColor Yellow
if (-not (Test-Path "backend\.env")) {
    Write-Host "  ! No .env file found. Creating from template..." -ForegroundColor Yellow
    Copy-Item "backend\.env.example" "backend\.env"
    Write-Host "  ✓ Created backend\.env (using mock mode by default)" -ForegroundColor Green
    Write-Host "  ℹ To enable real transcription, edit backend\.env and set ANALYSIS_MODE=real" -ForegroundColor Cyan
} else {
    Write-Host "  ✓ Found backend\.env" -ForegroundColor Green
}

# Check if frontend node_modules exists
Write-Host "[4/6] Checking frontend dependencies..." -ForegroundColor Yellow
if (-not (Test-Path "vishwas-frontend\node_modules")) {
    Write-Host "  ! Dependencies not installed. Running npm install..." -ForegroundColor Yellow
    Push-Location vishwas-frontend
    npm install
    Pop-Location
    Write-Host "  ✓ Frontend dependencies installed" -ForegroundColor Green
} else {
    Write-Host "  ✓ Frontend dependencies found" -ForegroundColor Green
}

# Start backend
Write-Host "[5/6] Starting backend server..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    cd backend
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
}
Write-Host "  ✓ Backend starting (Job ID: $($backendJob.Id))..." -ForegroundColor Green

# Wait for backend to be ready
Write-Host "      Waiting for backend to initialize..." -ForegroundColor Gray
$maxAttempts = 30
$attempt = 0
$backendReady = $false

while ($attempt -lt $maxAttempts -and -not $backendReady) {
    Start-Sleep -Seconds 1
    $attempt++
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $backendReady = $true
            Write-Host "      ✓ Backend ready!" -ForegroundColor Green
        } else {
            Write-Host "      ⏳ Attempt $attempt/$maxAttempts..." -ForegroundColor Gray
        }
    } catch {
        Write-Host "      ⏳ Attempt $attempt/$maxAttempts..." -ForegroundColor Gray
    }
}

if (-not $backendReady) {
    Write-Host "  ✗ Backend failed to start within 30 seconds" -ForegroundColor Red
    Write-Host "  Check logs: Receive-Job $($backendJob.Id)" -ForegroundColor Yellow
    exit 1
}

# Start frontend
Write-Host "[6/6] Starting React frontend..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    cd vishwas-frontend
    npm run dev
}
Write-Host "  ✓ Frontend starting (Job ID: $($frontendJob.Id))..." -ForegroundColor Green

# Wait for frontend
Start-Sleep -Seconds 3

# Summary
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🎉 VISHWAS Full Stack is running!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "📊 React Dashboard:   http://localhost:5173" -ForegroundColor Cyan
Write-Host "🔧 Backend API:       http://localhost:8000" -ForegroundColor Cyan
Write-Host "📖 API Docs:          http://localhost:8000/docs" -ForegroundColor Cyan
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
Write-Host "  .\stop-vishwas-full.ps1" -ForegroundColor Gray
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

