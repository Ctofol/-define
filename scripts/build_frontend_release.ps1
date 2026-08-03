param(
    [string]$BackendUrl = "http://82.156.50.58:5001",
    [string]$OutputPath = "frontend-dist-formal-latest.tar.gz"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Frontend = Join-Path $Root "frontend"
$Output = if ([System.IO.Path]::IsPathRooted($OutputPath)) { $OutputPath } else { Join-Path $Root $OutputPath }
$Dist = Join-Path $Frontend "dist"
$AdminDist = Join-Path $Frontend "dist-admin"

if (Test-Path $Dist) {
    $ResolvedFrontend = (Resolve-Path $Frontend).Path
    $ResolvedDist = (Resolve-Path $Dist).Path
    if (-not $ResolvedDist.StartsWith($ResolvedFrontend)) {
        throw "Refusing to remove unexpected dist path: $ResolvedDist"
    }
    Write-Host "Cleaning previous frontend dist..."
    Remove-Item -LiteralPath $ResolvedDist -Recurse -Force
}

Write-Host "Building frontend for backend: $BackendUrl"
Push-Location $Frontend
try {
    $env:VITE_API_BASE = $BackendUrl
    npm run build:all
    $AdminTarget = Join-Path $Dist "admin"
    if (Test-Path $AdminTarget) {
        Remove-Item -LiteralPath $AdminTarget -Recurse -Force
    }
    Copy-Item -LiteralPath $AdminDist -Destination $AdminTarget -Recurse
} finally {
    Pop-Location
}

if (Test-Path $Output) {
    Remove-Item $Output -Force
}

Write-Host "Packing frontend dist: $Output"
Push-Location $Dist
try {
    tar -czf $Output .
} finally {
    Pop-Location
}
Get-Item $Output | Select-Object FullName, Length
