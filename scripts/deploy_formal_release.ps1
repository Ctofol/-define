param(
    [string]$BackendUrl = "http://82.156.50.58:5001",
    [string]$FrontendUrl = "http://82.156.50.58:5002",

    [string]$RemoteHost = "82.156.50.58",
    [string]$RemoteUser = "root",
    [int]$SshPort = 22,

    [string]$RemoteFrontendPath = "",
    [string]$RemoteProjectPath = "",

    [switch]$SkipBuild,
    [switch]$SkipDeploy,
    [switch]$SkipFrontendDeploy,
    [switch]$SkipBackendDataDeploy,
    [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $Root
try {
    if (-not $SkipBuild) {
        Write-Host "== Build release packages =="
        & .\scripts\build_frontend_release.ps1 -BackendUrl $BackendUrl
        & .\scripts\build_backend_data_release.ps1
        & .\scripts\write_release_manifest.ps1 -BackendUrl $BackendUrl
    }

    if (-not $SkipDeploy) {
        if (-not $SkipFrontendDeploy) {
            if (-not $RemoteFrontendPath) {
                throw "RemoteFrontendPath is required for frontend deployment. Use -SkipFrontendDeploy to skip it."
            }
            Write-Host ""
            Write-Host "== Deploy frontend =="
            & .\scripts\deploy_frontend_release.ps1 `
                -RemoteHost $RemoteHost `
                -RemoteUser $RemoteUser `
                -RemotePath $RemoteFrontendPath `
                -SshPort $SshPort
        }

        if (-not $SkipBackendDataDeploy) {
            if (-not $RemoteProjectPath) {
                throw "RemoteProjectPath is required for backend data deployment. Use -SkipBackendDataDeploy to skip it."
            }
            Write-Host ""
            Write-Host "== Deploy backend data =="
            & .\scripts\deploy_backend_data_release.ps1 `
                -RemoteHost $RemoteHost `
                -RemoteUser $RemoteUser `
                -RemoteProjectPath $RemoteProjectPath `
                -SshPort $SshPort
        }
    }

    if (-not $SkipVerify) {
        Write-Host ""
        Write-Host "== Verify remote release =="
        & .\scripts\verify_remote_release.ps1 -BackendUrl $BackendUrl -FrontendUrl $FrontendUrl
    }
} finally {
    Pop-Location
}
