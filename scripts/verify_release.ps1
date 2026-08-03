$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendTests = @(
  "backend/tests/test_species_catalog_service.py",
  "backend/tests/test_species_service.py",
  "backend/tests/test_reference_sample_service.py",
  "backend/tests/test_inference_result_structure.py"
)
$MinimumSpeciesCount = 400
$MinimumReferenceCount = 350

Write-Host "== Backend core tests =="
Push-Location $Root
try {
  python -m pytest @BackendTests
} finally {
  Pop-Location
}

Write-Host ""
Write-Host "== Frontend catalog wiring check =="
$FrontendMain = Get-Content (Join-Path $Root "frontend/src/main.tsx") -Raw -Encoding UTF8
if ($FrontendMain -match "ANIMAL_CATEGORIES" -or $FrontendMain -match "isAnimalCatalogSpecies") {
  throw "Frontend still contains the old animal-only catalog filter. Use the unified wildlife catalog filter instead."
}
if ($FrontendMain -notmatch "WILDLIFE_CATEGORIES" -or $FrontendMain -notmatch "catalogEntries") {
  throw "Frontend gallery is not wired to the unified species catalog."
}
Write-Host "wildlife catalog wiring=ok"

Write-Host ""
Write-Host "== Frontend build =="
Push-Location (Join-Path $Root "frontend")
try {
  npm run build
} finally {
  Pop-Location
}

Write-Host ""
Write-Host "== Runtime API check =="
try {
  $Health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 5
  $Catalog = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/species-catalog" -TimeoutSec 5
  $PdfRefs = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/pdf-weak-reference-samples" -TimeoutSec 5
  $OpenSetRefs = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/knowledge-open-set-samples" -TimeoutSec 5
  $ReferenceCount = @($PdfRefs.species).Count + @($OpenSetRefs.species).Count

  Write-Host ("detector={0}" -f $Health.models.detector)
  Write-Host ("classifier={0}" -f $Health.models.classifier)
  Write-Host ("species={0}" -f $Catalog.species_count)
  Write-Host ("references={0}" -f $ReferenceCount)

  if ($Catalog.species_count -lt $MinimumSpeciesCount) {
    throw "Species catalog is incomplete: expected at least $MinimumSpeciesCount species, got $($Catalog.species_count)."
  }

  if ($ReferenceCount -lt $MinimumReferenceCount) {
    throw "Reference sample set is incomplete: expected at least $MinimumReferenceCount references, got $ReferenceCount."
  }
} catch {
  if ($_.Exception.Message -like "Species catalog is incomplete:*" -or $_.Exception.Message -like "Reference sample set is incomplete:*") {
    throw
  }

  Write-Host "Runtime API check skipped or failed. Start backend on http://127.0.0.1:8000 to verify live endpoints."
  Write-Host $_.Exception.Message
}

Write-Host ""
Write-Host "Release verification finished."
