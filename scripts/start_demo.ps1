param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

New-Item -ItemType Directory -Force -Path (Join-Path $Root "storage\logs") | Out-Null

$BackendOut = Join-Path $Root "storage\logs\backend.out.log"
$BackendErr = Join-Path $Root "storage\logs\backend.err.log"
$FrontendOut = Join-Path $Root "storage\logs\frontend.out.log"
$FrontendErr = Join-Path $Root "storage\logs\frontend.err.log"
$env:YOLO_CONFIG_DIR = Join-Path $Root "storage\ultralytics"
$env:YOLO_AUTOINSTALL = "false"

Write-Host "Starting backend on http://127.0.0.1:$BackendPort"
Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort" `
    -WorkingDirectory $Backend `
    -WindowStyle Hidden `
    -RedirectStandardOutput $BackendOut `
    -RedirectStandardError $BackendErr

Write-Host "Starting frontend on http://127.0.0.1:$FrontendPort"
Start-Process -FilePath "npm.cmd" `
    -ArgumentList "run", "dev", "--", "--host", "127.0.0.1", "--port", "$FrontendPort" `
    -WorkingDirectory $Frontend `
    -WindowStyle Hidden `
    -RedirectStandardOutput $FrontendOut `
    -RedirectStandardError $FrontendErr

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "Demo URLs:"
Write-Host "  Frontend: http://127.0.0.1:$FrontendPort"
Write-Host "  Backend:  http://127.0.0.1:$BackendPort"
Write-Host "  Health:   http://127.0.0.1:$BackendPort/api/health"
Write-Host ""
Write-Host "Logs:"
Write-Host "  $BackendOut"
Write-Host "  $BackendErr"
Write-Host "  $FrontendOut"
Write-Host "  $FrontendErr"
