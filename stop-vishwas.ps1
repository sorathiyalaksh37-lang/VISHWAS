# VISHWAS Full Stack Stop Script
# Stops both backend and frontend services

Write-Host "🛑 Stopping VISHWAS Full Stack..." -ForegroundColor Yellow
Write-Host ""

# Get all jobs
$jobs = Get-Job

if ($jobs.Count -eq 0) {
    Write-Host "No background jobs found." -ForegroundColor Gray
    exit 0
}

# Stop all jobs
foreach ($job in $jobs) {
    Write-Host "Stopping job $($job.Id): $($job.Name)..." -ForegroundColor Gray
    Stop-Job -Id $job.Id
    Remove-Job -Id $job.Id -Force
}

Write-Host ""
Write-Host "✓ All services stopped" -ForegroundColor Green

# Kill any remaining processes on ports 8000 and 5173
Write-Host ""
Write-Host "Checking for processes on ports 8000 and 5173..." -ForegroundColor Gray

$port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
$port5173 = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue

if ($port8000) {
    $pid = $port8000.OwningProcess
    Write-Host "  Killing process $pid on port 8000..." -ForegroundColor Gray
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
}

if ($port5173) {
    $pid = $port5173.OwningProcess
    Write-Host "  Killing process $pid on port 5173..." -ForegroundColor Gray
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "✓ VISHWAS Full Stack stopped" -ForegroundColor Green

