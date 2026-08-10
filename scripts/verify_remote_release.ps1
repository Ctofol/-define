param(
    [string]$BackendUrl = "http://82.156.50.58:5001",
    [string]$FrontendUrl = "http://82.156.50.58:5002",
    [int]$MinimumSpeciesCount = 400,
    [int]$MinimumReferenceCount = 402,
    [int]$MinimumOpenSetReferenceCount = 12
)

$ErrorActionPreference = "Stop"

$BackendBase = $BackendUrl.TrimEnd("/")
$FrontendBase = $FrontendUrl.TrimEnd("/")

Write-Host "== Remote API check =="
$Health = Invoke-RestMethod -Uri "$BackendBase/api/health" -TimeoutSec 10
$Catalog = Invoke-RestMethod -Uri "$BackendBase/api/species-catalog" -TimeoutSec 20
$PdfRefs = Invoke-RestMethod -Uri "$BackendBase/api/pdf-weak-reference-samples" -TimeoutSec 20
$OpenSetRefs = Invoke-RestMethod -Uri "$BackendBase/api/knowledge-open-set-samples" -TimeoutSec 20
$PdfReferenceCount = @($PdfRefs.species).Count
$OpenSetReferenceCount = @($OpenSetRefs.species).Count
$ReferenceCount = $PdfReferenceCount + $OpenSetReferenceCount

Write-Host ("detector={0}" -f $Health.models.detector)
Write-Host ("classifier={0}" -f $Health.models.classifier)
Write-Host ("assistant={0}" -f $Health.assistant.mode)
Write-Host ("species={0}" -f $Catalog.species_count)
Write-Host ("references={0}" -f $ReferenceCount)
Write-Host ("pdf_references={0}" -f $PdfReferenceCount)
Write-Host ("open_set_references={0}" -f $OpenSetReferenceCount)

if ($Catalog.species_count -lt $MinimumSpeciesCount) {
    throw "Remote species catalog is incomplete: expected at least $MinimumSpeciesCount, got $($Catalog.species_count)."
}

if ($ReferenceCount -lt $MinimumReferenceCount) {
    throw "Remote references are incomplete: expected at least $MinimumReferenceCount, got $ReferenceCount."
}

if ($OpenSetReferenceCount -lt $MinimumOpenSetReferenceCount) {
    throw "Remote open-set references are incomplete: expected at least $MinimumOpenSetReferenceCount, got $OpenSetReferenceCount."
}

Write-Host ""
Write-Host "== Remote frontend bundle check =="
$Index = Invoke-WebRequest -Uri $FrontendBase -TimeoutSec 20 -UseBasicParsing
$Match = [regex]::Match($Index.Content, 'src="([^"]*assets/index-[^"]+\.js)"')
if (-not $Match.Success) {
    throw "Could not find frontend JS bundle in remote index."
}

$BundlePath = $Match.Groups[1].Value
$BundleUrl = if ($BundlePath.StartsWith("http")) { $BundlePath } else { "$FrontendBase/$($BundlePath.TrimStart('/'))" }
$Bundle = Invoke-WebRequest -Uri $BundleUrl -TimeoutSec 30 -UseBasicParsing

$RequiredMarkers = @(
    "400+",
    "species-catalog",
    "pdf-weak-reference-samples",
    "knowledge-open-set-samples",
    "overview",
    "animalKnowledge",
    "gallery"
)

foreach ($Marker in $RequiredMarkers) {
    if (-not $Bundle.Content.Contains($Marker)) {
        throw "Remote frontend bundle is stale or incomplete. Missing marker: $Marker"
    }
}

Write-Host "frontend bundle=formal catalog version"
Write-Host ""
Write-Host "Remote release verification finished."
