param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteHost,

    [string]$RemoteUser = "root",

    [Parameter(Mandatory = $true)]
    [string]$RemotePath,

    [Parameter(Mandatory = $true)]
    [string]$BackupPath,

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

$Target = "${RemoteUser}@${RemoteHost}"
$RemoteScriptPath = "/tmp/senzhiyan-rollback-frontend.sh"
$LocalScriptPath = Join-Path $env:TEMP "senzhiyan-rollback-frontend.sh"

$RemoteScript = @"
set -e
remote_path="$RemotePath"
backup_path="$BackupPath"
if [ ! -d "`$backup_path" ]; then
  echo "Backup path does not exist: `$backup_path" >&2
  exit 1
fi
mkdir -p "`$remote_path"
current_backup="`$remote_path`_rollback_source_`$(date +%Y%m%d_%H%M%S)"
if [ -n "`$(ls -A "`$remote_path" 2>/dev/null)" ]; then
  cp -a "`$remote_path" "`$current_backup"
fi
find "`$remote_path" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
cp -a "`$backup_path"/. "`$remote_path"/
rm -f "$RemoteScriptPath"
echo "Frontend rolled back to `$backup_path"
echo "Previous current copy: `$current_backup"
"@

Set-Content -Path $LocalScriptPath -Value $RemoteScript -Encoding UTF8
try {
    Write-Host "Uploading rollback script..."
    Invoke-NativeChecked -FilePath "scp" -Arguments @("-P", "$SshPort", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", $LocalScriptPath, "${Target}:${RemoteScriptPath}")

    Write-Host "Rolling back frontend on remote server..."
    Invoke-NativeChecked -FilePath "ssh" -Arguments @("-p", "$SshPort", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", $Target, "sh $RemoteScriptPath")
} finally {
    Remove-Item $LocalScriptPath -Force -ErrorAction SilentlyContinue
}
