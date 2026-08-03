param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [string]$BackendUrl = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

New-Item -ItemType Directory -Force -Path (Join-Path $Root "storage\logs") | Out-Null

$BackendOut = Join-Path $Root "storage\logs\formal-backend.out.log"
$BackendErr = Join-Path $Root "storage\logs\formal-backend.err.log"
$FrontendOut = Join-Path $Root "storage\logs\formal-frontend.out.log"
$FrontendErr = Join-Path $Root "storage\logs\formal-frontend.err.log"
$env:YOLO_CONFIG_DIR = Join-Path $Root "storage\ultralytics"
$env:YOLO_AUTOINSTALL = "false"
if (-not $BackendUrl) {
    $BackendUrl = "http://127.0.0.1:$BackendPort"
}

Write-Host "Building frontend..."
Push-Location $Root
try {
    & .\scripts\build_frontend_release.ps1 -BackendUrl $BackendUrl -OutputPath "frontend-dist-formal-latest.zip"
} finally {
    Pop-Location
}

Write-Host "Starting backend on http://127.0.0.1:$BackendPort"
Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort" `
    -WorkingDirectory $Backend `
    -WindowStyle Hidden `
    -RedirectStandardOutput $BackendOut `
    -RedirectStandardError $BackendErr

Write-Host "Starting frontend preview on http://127.0.0.1:$FrontendPort"
Start-Process -FilePath "npm.cmd" `
    -ArgumentList "run", "preview", "--", "--host", "127.0.0.1", "--port", "$FrontendPort" `
    -WorkingDirectory $Frontend `
    -WindowStyle Hidden `
    -RedirectStandardOutput $FrontendOut `
    -RedirectStandardError $FrontendErr

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "Formal URLs:"
Write-Host "  Frontend: http://127.0.0.1:$FrontendPort"
Write-Host "  Backend:  http://127.0.0.1:$BackendPort"
Write-Host "  Frontend API: $BackendUrl"
Write-Host "  Health:   http://127.0.0.1:$BackendPort/api/health"
Write-Host ""
Write-Host "Logs:"
Write-Host "  $BackendOut"
Write-Host "  $BackendErr"
Write-Host "  $FrontendOut"
Write-Host "  $FrontendErr"
