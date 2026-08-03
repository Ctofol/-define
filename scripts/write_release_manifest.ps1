param(
    [string]$BackendUrl = "http://82.156.50.58:5001",
    [string]$FrontendPackagePath = "frontend-dist-formal-latest.tar.gz",
    [string]$BackendDataPackagePath = "backend-data-formal-latest.tar.gz",
    [string]$OutputPath = "release-manifest.json"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

function Resolve-ProjectPath([string]$Path) {
    if ([System.IO.Path]::IsPathRooted($Path)) { return $Path }
    return (Join-Path $Root $Path)
}

function Get-FileManifest([string]$Path) {
    $Item = Get-Item $Path
    $Hash = Get-FileHash -Algorithm SHA256 -Path $Path
    return [ordered]@{
        path = $Item.FullName
        size = $Item.Length
        sha256 = $Hash.Hash.ToLowerInvariant()
        lastWriteTime = $Item.LastWriteTimeUtc.ToString("o")
    }
}

$FrontendPackage = Resolve-ProjectPath $FrontendPackagePath
$BackendDataPackage = Resolve-ProjectPath $BackendDataPackagePath

foreach ($Path in @($FrontendPackage, $BackendDataPackage)) {
    if (-not (Test-Path $Path)) {
        throw "Release package not found: $Path"
    }
}

$Manifest = [ordered]@{
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    backend_url = $BackendUrl
    frontend_package = Get-FileManifest $FrontendPackage
    backend_data_package = Get-FileManifest $BackendDataPackage
}

$Output = Resolve-ProjectPath $OutputPath
$Manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $Output -Encoding UTF8
Get-Item $Output | Select-Object FullName, Length
