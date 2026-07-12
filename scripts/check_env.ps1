$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$env:YOLO_CONFIG_DIR = Join-Path $Root "storage\ultralytics"
$env:YOLO_AUTOINSTALL = "false"

Write-Host "Project: $Root"
Write-Host ""

Write-Host "Runtime:"
python --version
node --version
npm --version

Write-Host ""
Write-Host "Backend dependencies:"
Push-Location (Join-Path $Root "backend")
python -c "import fastapi, pydantic_settings, PIL, cv2; print('base backend deps: ok')"
python -c "import importlib.util as u; print('PytorchWildlife:', 'ok' if u.find_spec('PytorchWildlife') else 'missing'); print('transformers:', 'ok' if u.find_spec('transformers') else 'missing'); print('torch:', 'ok' if u.find_spec('torch') else 'missing')"
Pop-Location

Write-Host ""
Write-Host "Frontend dependencies:"
if (Test-Path (Join-Path $Root "frontend\node_modules")) {
    Write-Host "node_modules: ok"
} else {
    Write-Host "node_modules: missing; run npm install in frontend/"
}

Write-Host ""
Write-Host "Model folders:"
foreach ($Path in @("models", "models\megadetector", "models\megadetector\md_v6.pt", "models\species-classifier", "models\species-classifier\amazon_v2.ckpt")) {
    $FullPath = Join-Path $Root $Path
    if (Test-Path $FullPath) {
        Write-Host "$($Path): present"
    } else {
        Write-Host "$($Path): missing"
    }
}
