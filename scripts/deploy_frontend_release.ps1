param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteHost,

    [string]$RemoteUser = "root",

    [Parameter(Mandatory = $true)]
    [string]$RemotePath,

    [string]$PackagePath = "frontend-dist-formal-latest.tar.gz",

    [int]$SshPort = 22
)

$ErrorActionPreference = "Stop"

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$Arguments = @()
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath failed with exit code $LASTEXITCODE"
    }
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Package = if ([System.IO.Path]::IsPathRooted($PackagePath)) { $PackagePath } else { Join-Path $Root $PackagePath }
if (-not (Test-Path $Package)) {
    throw "Package not found: $Package. Run scripts\build_frontend_release.ps1 first."
}

$Target = "${RemoteUser}@${RemoteHost}"
$RemotePackage = "/tmp/senzhiyan-frontend-release.tar.gz"
$RemoteExtract = "/tmp/senzhiyan-frontend-release"
$RemoteScriptPath = "/tmp/senzhiyan-deploy-frontend.sh"
$LocalScriptPath = Join-Path $env:TEMP "senzhiyan-deploy-frontend.sh"

Write-Host "Uploading frontend package to $Target..."
Invoke-NativeChecked -FilePath "scp" -Arguments @("-P", "$SshPort", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", $Package, "${Target}:${RemotePackage}")

$RemoteScript = @"
set -e
remote_path="$RemotePath"
rm -rf "$RemoteExtract"
mkdir -p "$RemoteExtract"
tar -xzf "$RemotePackage" -C "$RemoteExtract"
mkdir -p "`$remote_path"
backup="`$remote_path`_backup_`$(date +%Y%m%d_%H%M%S)"
if [ -n "`$(ls -A "`$remote_path" 2>/dev/null)" ]; then
  cp -a "`$remote_path" "`$backup"
fi
find "`$remote_path" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
cp -a "$RemoteExtract"/. "`$remote_path"/
rm -rf "$RemoteExtract" "$RemotePackage" "$RemoteScriptPath"
echo "Frontend deployed to `$remote_path"
echo "Backup: `$backup"
"@

Set-Content -Path $LocalScriptPath -Value $RemoteScript -Encoding UTF8
try {
    Write-Host "Uploading deploy script..."
    Invoke-NativeChecked -FilePath "scp" -Arguments @("-P", "$SshPort", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", $LocalScriptPath, "${Target}:${RemoteScriptPath}")

    Write-Host "Deploying on remote server..."
    Invoke-NativeChecked -FilePath "ssh" -Arguments @("-p", "$SshPort", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", $Target, "sh $RemoteScriptPath")
} finally {
    Remove-Item $LocalScriptPath -Force -ErrorAction SilentlyContinue
}
