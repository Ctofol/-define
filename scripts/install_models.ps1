$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"

Push-Location $Backend

Write-Host "Installing core model packages..."
python -m pip install transformers torch

Write-Host "Installing PytorchWildlife without forcing OpenCV replacement..."
python -m pip install PytorchWildlife --no-deps

Write-Host "Installing PytorchWildlife import dependencies without dependency rewrites..."
python -m pip install supervision==0.23.0 torchvision timm yolov5 ultralytics lightning lightning-utilities torchmetrics pytorch-lightning omegaconf tensorboard absl-py grpcio protobuf tensorboard-data-server --no-deps

Write-Host "Installing audio import dependencies required by PytorchWildlife package init..."
python -m pip install soundfile librosa

Pop-Location

Write-Host ""
Write-Host "Model dependencies installed. Run:"
Write-Host "  .\scripts\check_env.ps1"
