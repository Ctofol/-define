param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteHost,

    [string]$RemoteUser = "root",

    [Parameter(Mandatory = $true)]
    [string]$RemoteProjectPath,

    [string]$PackagePath = "backend-data-formal-latest.tar.gz",

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
    throw "Package not found: $Package. Run scripts\build_backend_data_release.ps1 first."
}

$Target = "${RemoteUser}@${RemoteHost}"
$RemotePackage = "/tmp/senzhiyan-backend-data-release.tar.gz"
$RemoteExtract = "/tmp/senzhiyan-backend-data-release"
$RemoteScriptPath = "/tmp/senzhiyan-deploy-backend-data.sh"
$LocalScriptPath = Join-Path $env:TEMP "senzhiyan-deploy-backend-data.sh"

Write-Host "Uploading backend data package to $Target..."
Invoke-NativeChecked -FilePath "scp" -Arguments @("-P", "$SshPort", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", $Package, "${Target}:${RemotePackage}")

$RemoteScript = @"
set -e
project_path="$RemoteProjectPath"
if [ ! -d "`$project_path" ]; then
  echo "Remote project path does not exist: `$project_path" >&2
  exit 1
fi
rm -rf "$RemoteExtract"
mkdir -p "$RemoteExtract"
tar -xzf "$RemotePackage" -C "$RemoteExtract"
backup="`$project_path/data_backup_`$(date +%Y%m%d_%H%M%S)"
mkdir -p "`$backup"
if [ -d "`$project_path/reference_species/_supplement_candidates" ]; then
  mkdir -p "`$backup/reference_species"
  cp -a "`$project_path/reference_species/_supplement_candidates" "`$backup/reference_species/"
fi
if [ -d "`$project_path/reference_species/pdf_guangxi_species_images_v2" ]; then
  mkdir -p "`$backup/reference_species"
  cp -a "`$project_path/reference_species/pdf_guangxi_species_images_v2" "`$backup/reference_species/"
fi
for species in "豹猫" "大灵猫" "野猪" "黑熊" "梅花鹿" "水鹿" "中华斑羚"; do
  if [ -d "`$project_path/reference_species/`$species" ]; then
    mkdir -p "`$backup/reference_species"
    cp -a "`$project_path/reference_species/`$species" "`$backup/reference_species/"
  fi
done
if [ -f "`$project_path/storage/training/species_manifest_v20_round5_cleaned.csv" ]; then
  mkdir -p "`$backup/storage/training"
  cp -a "`$project_path/storage/training/species_manifest_v20_round5_cleaned.csv" "`$backup/storage/training/"
fi
if [ -f "`$project_path/docs/viverrid_source_verification/knowledge_open_set_candidates.csv" ]; then
  mkdir -p "`$backup/docs/viverrid_source_verification"
  cp -a "`$project_path/docs/viverrid_source_verification/knowledge_open_set_candidates.csv" "`$backup/docs/viverrid_source_verification/"
fi
mkdir -p "`$project_path/reference_species" "`$project_path/docs/viverrid_source_verification" "`$project_path/storage/training"
rm -rf "`$project_path/reference_species/_supplement_candidates"
cp -a "$RemoteExtract/reference_species/_supplement_candidates" "`$project_path/reference_species/"
rm -rf "`$project_path/reference_species/pdf_guangxi_species_images_v2"
cp -a "$RemoteExtract/reference_species/pdf_guangxi_species_images_v2" "`$project_path/reference_species/"
for species in "豹猫" "大灵猫" "野猪" "黑熊" "梅花鹿" "水鹿" "中华斑羚"; do
  rm -rf "`$project_path/reference_species/`$species"
  cp -a "$RemoteExtract/reference_species/`$species" "`$project_path/reference_species/"
done
cp -a "$RemoteExtract/storage/training/species_manifest_v20_round5_cleaned.csv" "`$project_path/storage/training/"
cp -a "$RemoteExtract/docs/viverrid_source_verification/knowledge_open_set_candidates.csv" "`$project_path/docs/viverrid_source_verification/"
rm -rf "$RemoteExtract" "$RemotePackage" "$RemoteScriptPath"
echo "Backend data deployed to `$project_path"
echo "Backup: `$backup"
"@

Set-Content -Path $LocalScriptPath -Value $RemoteScript -Encoding UTF8
try {
    Write-Host "Uploading deploy script..."
    Invoke-NativeChecked -FilePath "scp" -Arguments @("-P", "$SshPort", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", $LocalScriptPath, "${Target}:${RemoteScriptPath}")

    Write-Host "Deploying backend data on remote server..."
    Invoke-NativeChecked -FilePath "ssh" -Arguments @("-p", "$SshPort", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", $Target, "sh $RemoteScriptPath")
} finally {
    Remove-Item $LocalScriptPath -Force -ErrorAction SilentlyContinue
}
