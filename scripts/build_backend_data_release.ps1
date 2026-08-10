param(
    [string]$OutputPath = "backend-data-formal-latest.tar.gz"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Output = if ([System.IO.Path]::IsPathRooted($OutputPath)) { $OutputPath } else { Join-Path $Root $OutputPath }

Write-Host "Packing backend data release: $Output"
Push-Location $Root
try {
    python .\scripts\build_backend_data_release.py --output $Output
} finally {
    Pop-Location
}
Get-Item $Output | Select-Object FullName, Length
