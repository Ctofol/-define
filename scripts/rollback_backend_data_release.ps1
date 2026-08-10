param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteHost,

    [string]$RemoteUser = "root",

    [Parameter(Mandatory = $true)]
    [string]$RemoteProjectPath,

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
$RemoteScriptPath = "/tmp/senzhiyan-rollback-backend-data.sh"
$LocalScriptPath = Join-Path $env:TEMP "senzhiyan-rollback-backend-data.sh"

$RemoteScript = @"
set -e
project_path="$RemoteProjectPath"
backup_path="$BackupPath"
if [ ! -d "`$project_path" ]; then
  echo "Remote project path does not exist: `$project_path" >&2
  exit 1
fi
if [ ! -d "`$backup_path" ]; then
  echo "Backup path does not exist: `$backup_path" >&2
  exit 1
fi
current_backup="`$project_path/data_rollback_source_`$(date +%Y%m%d_%H%M%S)"
mkdir -p "`$current_backup"
if [ -d "`$project_path/reference_species/_supplement_candidates" ]; then
  mkdir -p "`$current_backup/reference_species"
  cp -a "`$project_path/reference_species/_supplement_candidates" "`$current_backup/reference_species/"
fi
if [ -f "`$project_path/docs/viverrid_source_verification/knowledge_open_set_candidates.csv" ]; then
  mkdir -p "`$current_backup/docs/viverrid_source_verification"
  cp -a "`$project_path/docs/viverrid_source_verification/knowledge_open_set_candidates.csv" "`$current_backup/docs/viverrid_source_verification/"
fi
if [ -d "`$backup_path/reference_species/_supplement_candidates" ]; then
  mkdir -p "`$project_path/reference_species"
  rm -rf "`$project_path/reference_species/_supplement_candidates"
  cp -a "`$backup_path/reference_species/_supplement_candidates" "`$project_path/reference_species/"
fi
if [ -f "`$backup_path/docs/viverrid_source_verification/knowledge_open_set_candidates.csv" ]; then
  mkdir -p "`$project_path/docs/viverrid_source_verification"
  cp -a "`$backup_path/docs/viverrid_source_verification/knowledge_open_set_candidates.csv" "`$project_path/docs/viverrid_source_verification/"
fi
rm -f "$RemoteScriptPath"
echo "Backend data rolled back from `$backup_path"
echo "Previous current data copy: `$current_backup"
"@

Set-Content -Path $LocalScriptPath -Value $RemoteScript -Encoding UTF8
try {
    Write-Host "Uploading rollback script..."
    Invoke-NativeChecked -FilePath "scp" -Arguments @("-P", "$SshPort", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", $LocalScriptPath, "${Target}:${RemoteScriptPath}")

    Write-Host "Rolling back backend data on remote server..."
    Invoke-NativeChecked -FilePath "ssh" -Arguments @("-p", "$SshPort", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", $Target, "sh $RemoteScriptPath")
} finally {
    Remove-Item $LocalScriptPath -Force -ErrorAction SilentlyContinue
}
