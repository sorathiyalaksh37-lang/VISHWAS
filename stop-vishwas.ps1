# VISHWAS Shutdown Script
# Stops all VISHWAS services

Write-Host "🛑 Stopping VISHWAS services..." -ForegroundColor Yellow
Write-Host ""

# Find running jobs
$jobs = Get-Job | Where-Object { $_.Command -like "*uvicorn*" -or $_.Command -like "*streamlit*" }

if ($jobs.Count -eq 0) {
    Write-Host "No VISHWAS jobs found running." -ForegroundColor Gray
} else {
    foreach ($job in $jobs) {
        Write-Host "Stopping Job ID $($job.Id): $($job.Name)" -ForegroundColor Yellow
        Stop-Job -Id $job.Id
        Remove-Job -Id $job.Id -Force
    }
    Write-Host ""
    Write-Host "✓ All VISHWAS jobs stopped" -ForegroundColor Green
}

# Additionally, kill processes on ports 8000 and 8501
Write-Host ""
Write-Host "Checking for processes on ports 8000 and 8501..." -ForegroundColor Yellow

# Port 8000 (backend)
$port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($port8000) {
    $pid = $port8000.OwningProcess
    Write-Host "  Killing process on port 8000 (PID: $pid)" -ForegroundColor Yellow
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
}

# Port 8501 (frontend)
$port8501 = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue
if ($port8501) {
    $pid = $port8501.OwningProcess
    Write-Host "  Killing process on port 8501 (PID: $pid)" -ForegroundColor Yellow
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "✓ VISHWAS services stopped" -ForegroundColor Green
